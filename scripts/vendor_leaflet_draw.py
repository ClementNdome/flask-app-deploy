"""
Download and vendor Leaflet.draw assets into `static/vendor/leaflet-draw/` and compute SRI (sha512) hashes.
Run this script from the project root. It requires `requests` and `hashlib` (both included in requirements).

This script will:
- create static/vendor/leaflet-draw/
- download leaflet.draw.css and leaflet.draw.js from unpkg.com
- save files locally
- compute sha512 integrity values and write integrity.json

Use the vendored files in production for deterministic assets. The app will auto-detect vendored files and prefer them.
"""

import os
import sys
import hashlib
import base64

try:
    import requests
except ImportError:
    print('requests is required. Install with: pip install requests')
    sys.exit(1)

ASSET_BASE = 'https://unpkg.com/leaflet-draw@1.0.4/dist'
FILES = {
    'css': 'leaflet.draw.css',
    'js': 'leaflet.draw.js'
}

OUT_DIR = os.path.join('static', 'vendor', 'leaflet-draw')


def sha512_sri(data: bytes) -> str:
    h = hashlib.sha512(data).digest()
    return 'sha512-' + base64.b64encode(h).decode('ascii')


def download(url: str) -> bytes:
    print('Downloading', url)
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.content


def ensure_out_dir():
    os.makedirs(OUT_DIR, exist_ok=True)


def main():
    ensure_out_dir()
    integrity = {}
    for key, fname in FILES.items():
        url = f"{ASSET_BASE}/{fname}"
        try:
            data = download(url)
            out_path = os.path.join(OUT_DIR, fname)
            with open(out_path, 'wb') as f:
                f.write(data)
            integrity[key] = sha512_sri(data)
            print(f'Wrote {out_path} (SRI: {integrity[key]})')
        except Exception as e:
            print('Failed to download', url, e)

    # write integrity.json
    import json
    try:
        with open(os.path.join(OUT_DIR, 'integrity.json'), 'w', encoding='utf-8') as f:
            json.dump(integrity, f, indent=2)
        print('Wrote integrity.json')
    except Exception as e:
        print('Failed to write integrity.json', e)

    print('\nDone. Add static/vendor/leaflet-draw to your version control for reproducible builds.')


if __name__ == '__main__':
    main()
