import argparse
import logging
from pathlib import Path
from .parser import SENDER, parse_message
from .render import render
from .worker import process_queue


def main():
    parser = argparse.ArgumentParser(description='Publish public SMOPS pass times from Mail.app.')
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('build', help='Validate one saved email and generate a local preview.')
    build.add_argument('email', type=Path)
    build.add_argument('--output', type=Path, default=Path('preview'))
    build.add_argument('--allow-sender', action='append', default=[SENDER],
                       help='Explicitly allow a forwarded sample sender for this build only.')
    worker = commands.add_parser('process', help='Process the local Mail queue and publish changes.')
    worker.add_argument('--repo', type=Path, required=True)
    worker.add_argument('--state', type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    if args.command == 'build':
        schedule = parse_message(args.email.read_bytes(), args.allow_sender)
        render(schedule, args.output)
        print('Built {} passes in {}'.format(len(schedule['passes']), args.output.resolve()))
    else:
        process_queue(args.repo, args.state)


if __name__ == '__main__':
    main()
