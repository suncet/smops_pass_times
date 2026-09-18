import json
from email.message import EmailMessage
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from smops.parser import ScheduleError, parse_message, parse_table, parse_utc
from smops.render import render
from smops import worker

HEADER = 'Mission | Local AOS | UTC AOS | UTC LOS | El | UHF? | SBD? | CC'
ROW = 'DEMO | 2025-12-31 16:58:00MT | 2025/365-23:58:00 | 2026/001-00:08:00 | 35.20* | Keep_Conflict | Delete | Private Staff'
BODY = HEADER + '\n' + ROW + '\n----------------\nContact List\nPrivate Name | 555-555-1234 | person@example.com\n'


def email(body=BODY, date='Thu, 01 Jan 2026 08:00:00 +0000', sender='gs-ops@lasp.colorado.edu', html=False):
    message = EmailMessage()
    message['Subject'] = 'SMOPS Pass Times and Shift Schedule'
    message['From'] = sender
    message['Date'] = date
    message.set_content(body, subtype='html' if html else 'plain')
    return message.as_bytes()


class ParseTests(unittest.TestCase):
    def test_dates_and_cross_year_pass(self):
        result = parse_message(email())
        row = result['passes'][0]
        self.assertEqual(row['aos_utc'], '2025-12-31T23:58:00Z')
        self.assertEqual(row['los_utc'], '2026-01-01T00:08:00Z')
        self.assertTrue(row['s_band_candidate'])
        self.assertNotIn('Private', json.dumps(result))
        self.assertNotIn('555', json.dumps(result))
        self.assertNotIn('person@example.com', json.dumps(result))

    def test_html_only_and_nonbreaking_spaces(self):
        html = '<div>' + BODY.replace(' ', '&nbsp;').replace('\n', '<br>') + '</div>'
        self.assertEqual(parse_message(email(html, html=True))['passes'], parse_message(email())['passes'])

    def test_authorized_forward_preserves_public_fields(self):
        raw = email(sender='Elisabeth van Reijendam <Elisabeth.vanReijendam@lasp.colorado.edu>')
        raw = raw.replace(b'Subject: SMOPS', b'Subject: FW: SMOPS')
        result = parse_message(raw)
        self.assertEqual(result, parse_message(email()))
        self.assertNotIn('Elisabeth', json.dumps(result))
        self.assertEqual(parse_message(email(sender='elva7682@laspcolorado.mail.onmicrosoft.com')), result)
        with self.assertRaises(ScheduleError):
            parse_message(email(sender='Elisabeth van Reijendam <other@example.com>'))

    def test_bad_sender_rejected(self):
        with self.assertRaises(ScheduleError):
            parse_message(email(sender='other@example.com'))

    def test_bad_day_of_year_rejected(self):
        with self.assertRaises(ScheduleError):
            parse_utc('2025/366-00:00:00')
        self.assertEqual(parse_utc('2024/366-00:00:00').isoformat(), '2024-12-31T00:00:00+00:00')

    def test_incomplete_and_ambiguous_tables_rejected(self):
        for text in [HEADER+'\n'+ROW, HEADER+'\n----------------', BODY+'\n'+BODY,
                     BODY.replace('35.20*', 'NaN'), BODY.replace('Keep_Conflict', 'Unexpected'),
                     BODY.replace('16:58:00MT', '17:58:00MT'),
                     BODY.replace(ROW, ROW+'\nBROKEN | ROW'),
                     BODY.replace(ROW, ROW+'\n'+ROW)]:
            with self.subTest(text=text[:40]), self.assertRaises(ScheduleError):
                parse_table(text)

    def test_output_has_no_private_email_data(self):
        with tempfile.TemporaryDirectory() as directory:
            render(parse_message(email()), directory)
            content = '\n'.join(path.read_text() for path in Path(directory).iterdir())
            for private in ['Private Staff','Private Name','555-555-1234','person@example.com']:
                self.assertNotIn(private, content)
            self.assertIn('2025-12-31T23:58:00Z', content)
            self.assertNotIn('2025/365', content)

    def test_timestamp_orders_latest_without_date_format_ambiguity(self):
        early = parse_message(email(date='Thu, 01 Jan 2026 01:00:00 -0700'))
        late = parse_message(email(date='Thu, 01 Jan 2026 09:00:00 +0000'))
        self.assertTrue(worker.newer(late, early))
        self.assertFalse(worker.newer(early, late))
        self.assertFalse(worker.newer(late, late))


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.repo, self.remote, self.state = root/'repo', root/'remote.git', root/'state'
        self.repo.mkdir()
        self.state.mkdir()
        (self.state/'queue').mkdir()
        self.run_git('init', '--bare', str(self.remote))
        self.run_git('init', '-b', 'main', str(self.repo))
        worker.git(self.repo, 'config', 'user.name', 'Test Publisher')
        worker.git(self.repo, 'config', 'user.email', 'test@example.com')
        worker.git(self.repo, 'remote', 'add', 'origin', str(self.remote))
        render(parse_message(email()), self.repo/'docs')
        worker.git(self.repo, 'add', 'docs')
        worker.git(self.repo, 'commit', '-m', 'Initial schedule')
        worker.git(self.repo, 'push', '-u', 'origin', 'main')

    def run_git(self, *args):
        subprocess.run(['git',*args], check=True, capture_output=True)

    def enqueue(self, name, raw):
        path=self.state/'queue'/name
        path.write_bytes(raw)
        return path

    def test_old_mail_cannot_replace_current(self):
        before=(self.repo/'docs/schedule.json').read_bytes()
        self.enqueue('old.eml',email(date='Wed, 31 Dec 2025 08:00:00 +0000'))
        worker.process_queue(self.repo,self.state)
        self.assertEqual(before,(self.repo/'docs/schedule.json').read_bytes())
        self.assertTrue((self.state/'processed/old.eml').exists())

    def test_rejection_preserves_current_publication(self):
        before=(self.repo/'docs/schedule.json').read_bytes()
        self.enqueue('broken.eml',email(BODY.replace('35.20*','ERROR')))
        worker.process_queue(self.repo,self.state)
        self.assertEqual(before,(self.repo/'docs/schedule.json').read_bytes())
        self.assertTrue((self.state/'rejected/broken.eml').exists())
        self.assertFalse(json.loads((self.state/'status.json').read_text())['ok'])

    def test_remote_readme_edit_does_not_block_updates(self):
        other=Path(self.temp.name)/'other'
        self.run_git('clone','--branch','main',str(self.remote),str(other))
        worker.git(other,'config','user.name','Test')
        worker.git(other,'config','user.email','test@example.com')
        (other/'README.md').write_text('Minimal README\n')
        worker.git(other,'add','README.md')
        worker.git(other,'commit','-m','Edit README')
        worker.git(other,'push','origin','main')
        self.enqueue('new.eml',email(date='Fri, 02 Jan 2026 08:00:00 +0000'))
        worker.process_queue(self.repo,self.state)
        self.assertEqual((self.repo/'README.md').read_text(),'Minimal README\n')
        self.assertTrue((self.state/'processed/new.eml').exists())

    def test_failed_push_keeps_queue_and_retries(self):
        path=self.enqueue('new.eml',email(date='Fri, 02 Jan 2026 08:00:00 +0000'))
        original=worker.git
        calls=0
        def fail_first_push(repo,*args):
            nonlocal calls
            if args[0]=='push':
                calls+=1
                if calls==1:
                    raise subprocess.CalledProcessError(1, 'git push')
            return original(repo,*args)
        with patch.object(worker,'git',side_effect=fail_first_push):
            with self.assertRaises(subprocess.CalledProcessError):
                worker.process_queue(self.repo,self.state)
        self.assertTrue(path.exists())
        worker.process_queue(self.repo,self.state)
        self.assertFalse(path.exists())
        self.assertTrue((self.state/'processed/new.eml').exists())
        remote_json=subprocess.check_output(['git','--git-dir',str(self.remote),'show','main:docs/schedule.json'],text=True)
        self.assertEqual(json.loads(remote_json)['message_at'],'2026-01-02T08:00:00Z')
        files=worker.git(self.repo,'ls-files').stdout
        self.assertNotIn('.eml',files)


if __name__ == '__main__':
    unittest.main()
