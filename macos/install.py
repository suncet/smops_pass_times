#!/usr/bin/env python3
"""Install a private publishing checkout, Mail action, and per-user launch agent."""
import os
from pathlib import Path
import plistlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
STATE = Path.home() / 'Library/Application Support/SMOPS Pass Times'
PUBLISHER = STATE / 'publisher'
LABEL = 'org.suncet.smops-pass-times'


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def main():
    os.umask(0o077)
    for name in ('queue', 'processed', 'rejected'):
        (STATE / name).mkdir(parents=True, exist_ok=True, mode=0o700)
    if not PUBLISHER.exists():
        run('git', 'clone', 'https://github.com/suncet/smops_pass_times.git', PUBLISHER)
    run('git', '-C', PUBLISHER, 'config', 'user.name', 'SMOPS schedule publisher')
    run('git', '-C', PUBLISHER, 'config', 'user.email', 'smops-publisher@users.noreply.github.com')
    scripts = Path.home() / 'Library/Application Scripts/com.apple.mail'
    scripts.mkdir(parents=True, exist_ok=True)
    run('/usr/bin/osacompile', '-o', scripts / 'SMOPS Schedule.scpt', ROOT / 'macos/SMOPS Schedule.applescript')
    agent = dict(Label=LABEL, ProgramArguments=[sys.executable, '-m', 'smops', 'process', '--repo', str(PUBLISHER), '--state', str(STATE)],
                 WorkingDirectory=str(PUBLISHER), StartInterval=300, RunAtLoad=True,
                 StandardOutPath=str(STATE / 'publisher.log'), StandardErrorPath=str(STATE / 'publisher.log'),
                 EnvironmentVariables={'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'GIT_TERMINAL_PROMPT': '0'},
                 ProcessType='Background')
    plist = Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_bytes(plistlib.dumps(agent))
    subprocess.run(['/bin/launchctl', 'bootout', 'gui/{}/{}'.format(os.getuid(), LABEL)], capture_output=True)
    run('/bin/launchctl', 'bootstrap', 'gui/{}'.format(os.getuid()), plist)
    print('Installed. In Mail > Settings > Rules, add three ALL-conditions rules:')
    print('  Subject contains: SMOPS Pass Times and Shift Schedule')
    print('  From is equal to: gs-ops@lasp.colorado.edu (first rule)')
    print('  From is equal to: elisabeth.vanreijendam@lasp.colorado.edu (second rule)')
    print('  From is equal to: elva7682@laspcolorado.mail.onmicrosoft.com (third rule)')
    print('  Account: LASP')
    print('  Action: Run AppleScript > SMOPS Schedule')
    print('Local status:', STATE / 'status.json')


if __name__ == '__main__':
    main()
