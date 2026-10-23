"""Download pinned upstream dependencies; no credentials or paid API calls."""
import hashlib,json,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parent.parent
for name, entry in json.loads((root/'upstream-lock.json').read_text()).items():
    target=root/'scripts'/name
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest()!=entry['sha256']:
            raise SystemExit('Existing dependency differs; preserve or move it first: '+name)
        print('Already verified:',name)
        continue
    data=urllib.request.urlopen(entry['url'],timeout=30).read()
    if hashlib.sha256(data).hexdigest()!=entry['sha256']:
        raise SystemExit('Dependency hash mismatch: '+name)
    target.write_bytes(data)
    print('Installed and verified:',name)
