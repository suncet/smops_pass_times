# SMOPS pass times

[Public schedule](https://suncet.github.io/smops_pass_times/)

A small, standard-library Python tool that turns the daily **SMOPS Pass Times and Shift Schedule** email into a public GitHub Pages table. Mail.app on the receiving Mac supplies the email. No Microsoft/Exchange API, LASP VPN, WordPress updates, or email forwarding service is needed.

The public page includes all missions, sortable columns, mission/search filters, UTC, Mountain (America/Denver), and browser-local time, upcoming-only filtering, and CSV/JSON downloads. Dates use **YYYY-MM-DD**, converting the email's year/day-of-year format. It uses a native HTML table rather than a Plotly hosting account. Source priority flags and S-band candidate markers are preserved.

## How it works

1. A Mail rule matches the LASP account, the subject phrase, and sender `gs-ops@lasp.colorado.edu`.
2. `macos/SMOPS Schedule.applescript` writes the raw email atomically to a private local queue.
3. A user launch agent checks the queue every five minutes while the Mac is awake and the user is logged in.
4. Python validates every pass and generates only public schedule artifacts in `docs/`.
5. The worker commits and pushes those artifacts using the Mac's existing Git authentication. GitHub Pages serves `main:/docs` at a stable URL.

Mail must be running to receive messages and execute its rule. Updates resume when Mail receives messages after sleep. An offline push leaves the email queued for retry. GitHub continues serving the last published table while the Mac is off. The page displays the schedule email timestamp and warns after 36 hours or when the schedule has ended. Refresh the page to load a newly published schedule; the open page updates its countdown and freshness warning every 30 seconds.

## Privacy and validation

Only mission, AOS/LOS, elevation, S-band candidate marker, and UHF/S-band priority are published, along with the email Date timestamp and source-file generation timestamp. The CC/staff column, shift assignments, contact list, recipients, signatures, source paths, and raw message headers are excluded. Local raw emails are stored outside the repository with private directory permissions. Successfully processed and rejected emails remain locally available for troubleshooting; they are not uploaded.

The parser accepts MIME plain text or HTML-only messages, checks the expected eight-column schema, UTC/Mountain consistency (including DST), valid day of year, elevation, priority flags, durations, duplicates, and a closing separator. Unknown formats are rejected in full. A rejected email does not replace the published table. Newer email Date timestamps win; duplicates and older emails are archived locally without a new publication. A stale source-file generation timestamp is displayed separately; its timezone is not specified in the email and is not guessed.

The visible table is a copy of the published schedule, not a real-time ground station status display.

## Local setup (macOS)

Requires Python 3.9+ with timezone data (macOS provides it), Git with working GitHub push credentials, and Mail.app receiving the LASP account. No Python package installation is required.

```sh
git clone https://github.com/suncet/smops_pass_times.git
cd smops_pass_times
python3 -m unittest discover -s tests -v
python3 macos/install.py
```

The installer creates a separate publishing checkout in `~/Library/Application Support/SMOPS Pass Times/publisher` so automated commits do not touch your development checkout. It compiles the AppleScript into Mail's application scripts folder and registers `org.suncet.smops-pass-times` in `~/Library/LaunchAgents`.

In **Mail → Settings → Rules**, create a rule named **Publish SMOPS pass times** with **all** conditions:

- Subject contains `SMOPS Pass Times and Shift Schedule`
- From is equal to `gs-ops@lasp.colorado.edu`
- Account is `LASP`

Action: **Run AppleScript → SMOPS Schedule**. Keep the rule enabled. Place it above rules that move these messages or stop evaluating rules. Do not move/delete messages as part of this rule. If the sender changes, update both the Mail rule and `SENDER` in `smops/parser.py`, then update the publishing checkout and reinstall the compiled script as appropriate.

The initial sample was forwarded; daily automation accepts the original ground-station sender only. Reapplying the rule manually to a matching original message is safe: the worker ignores already-published timestamps.

## GitHub setup

Create a public repository under `suncet`, push `main`, and configure **Settings → Pages → Deploy from a branch → main → /docs**. Only `docs/` is served as the website. The source repository itself is also public. Credentials are managed by the local Git credential helper, not written into this repository or the launch-agent plist. GitHub Actions runs the test suite for source changes.

## Preview a saved email

In Mail, save the message using **File → Save As → Raw Message Source**. Keep that `.eml` outside this repository.

```sh
python3 -m smops build /path/to/schedule.eml --output preview
python3 -m http.server 8080 --directory preview
```

Visit http://localhost:8080. To validate a forwarded sample, explicitly add `--allow-sender sender@example.com` to the build command. This override is only for that manual preview/build; it does not broaden the automated publisher's sender allowlist.

## Maintenance

Local paths are beneath `~/Library/Application Support/SMOPS Pass Times/`:

- `queue/`: mail awaiting processing
- `processed/`: successfully processed or superseded mail
- `rejected/`: mail that failed validation
- `status.json`: most recent nonempty queue-processing result
- `publisher.log`: activity and errors
- `publisher/`: isolated Git checkout used to publish

To process queued mail immediately:

```sh
cd "$HOME/Library/Application Support/SMOPS Pass Times/publisher"
python3 -m smops process --repo "$PWD" --state "$HOME/Library/Application Support/SMOPS Pass Times"
```

If updates stop, check the Mail rule, sender, network connection, `status.json`, and `publisher.log`. Test `git push` interactively inside the publishing checkout if credentials need refreshing. A divergent Git history or unexpected source changes are not automatically overwritten; resolve them in that checkout. To update the installed code, ensure the queue is idle and use `git pull --ff-only` inside the publisher checkout (the worker also pulls before processing queued messages). Re-run the installer after changes to the Mail action or launch-agent configuration. Raw mail/logs are local and can be cleaned up manually once no longer needed.

To pause automatic publishing:

```sh
launchctl bootout "gui/$(id -u)/org.suncet.smops-pass-times"
```

Also disable the Mail rule to stop queueing. Re-run `macos/install.py` and re-enable the rule to resume. The public site remains available.
