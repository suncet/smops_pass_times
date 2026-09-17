"""Strict parsing of the SMOPS pipe-separated pass table (no email contacts)."""
import re
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime, parseaddr
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

SUBJECT = 'SMOPS Pass Times and Shift Schedule'
SENDER = 'gs-ops@lasp.colorado.edu'
HEADER = ['Mission', 'Local AOS', 'UTC AOS', 'UTC LOS', 'El', 'UHF?', 'SBD?', 'CC']
PRIORITIES = {'Keep', 'Delete', 'Keep_Conflict', 'Delete_Conflict'}
UTC = timezone.utc


class ScheduleError(ValueError):
    """An email is not a complete, recognized SMOPS schedule."""


class TextFromHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag in ('br', 'p', 'div', 'tr', 'pre'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        if tag in ('p', 'div', 'tr', 'pre'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def iso(value):
    return value.astimezone(UTC).isoformat(timespec='seconds').replace('+00:00', 'Z')


def parse_utc(value):
    if not re.fullmatch(r'\d{4}/\d{3}-\d{2}:\d{2}:\d{2}', value):
        raise ScheduleError('Unrecognized UTC timestamp.')
    try:
        result = datetime.strptime(value, '%Y/%j-%H:%M:%S').replace(tzinfo=UTC)
    except ValueError as error:
        raise ScheduleError('Invalid UTC timestamp.') from error
    if result.strftime('%Y/%j-%H:%M:%S') != value:
        raise ScheduleError('Invalid day of year.')
    return result


def parse_row(cells):
    if len(cells) != 8:
        raise ScheduleError('A pass row does not have eight columns.')
    mission, local, aos_text, los_text, elevation, uhf, sbd, _staff = cells
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,31}', mission):
        raise ScheduleError('Unrecognized mission name.')
    aos, los = parse_utc(aos_text), parse_utc(los_text)
    if not timedelta(0) < los - aos <= timedelta(hours=2):
        raise ScheduleError('Invalid pass duration.')
    expected = aos.astimezone(ZoneInfo('America/Denver')).strftime('%Y-%m-%d %H:%M:%SMT')
    if local != expected:
        raise ScheduleError('Local and UTC acquisition times disagree.')
    if not re.fullmatch(r'\d+(?:\.\d+)?\*?', elevation):
        raise ScheduleError('Invalid elevation.')
    degrees = float(elevation.rstrip('*'))
    if not 0 <= degrees <= 90 or uhf not in PRIORITIES or sbd not in PRIORITIES:
        raise ScheduleError('Invalid elevation or priority flag.')
    return dict(mission=mission, aos_utc=iso(aos), los_utc=iso(los),
                elevation_deg=degrees, s_band_candidate=elevation.endswith('*'),
                uhf=uhf, s_band=sbd)


def parse_table(text):
    lines = [line.replace('\xa0', ' ').strip().lstrip('>').strip()
             for line in text.splitlines()]
    headers = [i for i, line in enumerate(lines)
               if [cell.strip() for cell in line.split('|')] == HEADER]
    if len(headers) != 1:
        raise ScheduleError('Expected exactly one SMOPS table header.')
    rows, ended = [], False
    for line in lines[headers[0] + 1:]:
        if not line:
            continue
        if re.fullmatch(r'-{8,}', line):
            ended = True
            break
        rows.append(parse_row([cell.strip() for cell in line.split('|')]))
    if not ended or not rows:
        raise ScheduleError('Schedule is empty or missing its closing separator.')
    keys = {(row['mission'], row['aos_utc']) for row in rows}
    if len(keys) != len(rows):
        raise ScheduleError('Duplicate passes found.')
    rows.sort(key=lambda row: (row['aos_utc'], row['mission']))
    # Deliberately extract only the timestamp, never the source filesystem path.
    generated = re.search(r'generated at ([A-Za-z]{3} [A-Za-z]{3}\s+\d{1,2} \d{2}:\d{2}:\d{2} \d{4})\.', text)
    source_generated = None
    if generated:
        try:
            source_generated = datetime.strptime(generated[1], '%a %b %d %H:%M:%S %Y').isoformat(sep=' ')
        except ValueError as error:
            raise ScheduleError('Invalid source generation timestamp.') from error
    return rows, source_generated


def parse_message(raw, allowed_senders=(SENDER,)):
    message = BytesParser(policy=policy.default).parsebytes(raw)
    if SUBJECT.casefold() not in str(message.get('Subject', '')).casefold():
        raise ScheduleError('Email subject does not match.')
    sender = parseaddr(str(message.get('From', '')))[1].casefold()
    if sender not in {value.casefold() for value in allowed_senders}:
        raise ScheduleError('Email sender is not allowed.')
    try:
        sent = parsedate_to_datetime(str(message['Date']))
        if sent.tzinfo is None:
            raise ValueError('No time zone')
    except (ValueError, TypeError) as error:
        raise ScheduleError('Email needs a valid dated, time-zoned Date header.') from error
    if sent > datetime.now(UTC) + timedelta(minutes=10):
        raise ScheduleError('Email timestamp is in the future.')
    body = message.get_body(preferencelist=('plain', 'html'))
    if body is None:
        raise ScheduleError('No email text body.')
    text = body.get_content()
    if body.get_content_type() == 'text/html':
        converter = TextFromHTML()
        converter.feed(text)
        text = ''.join(converter.parts)
    rows, source_generated = parse_table(text)
    return dict(schema_version=1, message_at=iso(sent),
                source_generated=source_generated, passes=rows)
