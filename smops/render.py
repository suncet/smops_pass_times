"""Build standalone public artifacts using only whitelisted schedule fields."""
import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def render(schedule, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    data = dict(schedule, published_at=datetime.now(timezone.utc).isoformat(timespec='seconds'))
    encoded = json.dumps(data, indent=2, allow_nan=False)
    (output / 'schedule.json').write_text(encoded + '\n', encoding='utf-8')
    embedded = encoded.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    template = (ROOT / 'web/index.html').read_text(encoding='utf-8')
    for asset in ('pass-status.js', 'app.js', 'style.css'):
        version = hashlib.sha256((ROOT / 'web' / asset).read_bytes()).hexdigest()[:12]
        template = template.replace(asset + '"', asset + '?v=' + version + '"')
    (output / 'index.html').write_text(template.replace('__SCHEDULE_JSON__', embedded), encoding='utf-8')
    for filename in ('pass-status.js', 'app.js', 'style.css'):
        shutil.copyfile(ROOT / 'web' / filename, output / filename)
    (output / '.nojekyll').touch()
    with (output / 'passes.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(data['passes'][0]))
        writer.writeheader()
        writer.writerows(data['passes'])
