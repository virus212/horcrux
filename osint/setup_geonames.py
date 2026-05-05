"""Helper per scaricare il dataset geonames cities1000 (~5 MB).

Utilizzo:
    python -m osint.setup_geonames

Scarica https://download.geonames.org/export/dump/cities1000.zip,
estrae cities1000.txt e lo salva in ~/.horcrux/cities1000.tsv.

Dopo l'esecuzione, reverse_geocode() user automaticamente il dataset esteso
(~150k citta' del mondo) invece dei 70 embedded.

Override path: env HORCRUX_CITIES_DATASET=/percorso/custom.tsv
"""
from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = "https://download.geonames.org/export/dump/cities1000.zip"


def main() -> int:
    target_dir = Path.home() / ".horcrux"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "cities1000.tsv"

    print(f"→ scarico {URL}")
    try:
        with urllib.request.urlopen(URL, timeout=60) as resp:
            data = resp.read()
    except Exception as e:
        print(f"errore download: {e}", file=sys.stderr)
        return 1

    print(f"→ scompatto ({len(data) // 1024} KB)")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            with zf.open("cities1000.txt") as src:
                target.write_bytes(src.read())
    except (zipfile.BadZipFile, KeyError) as e:
        print(f"errore unzip: {e}", file=sys.stderr)
        return 1

    size_mb = target.stat().st_size / (1024 * 1024)
    print(f"✓ salvato in {target} ({size_mb:.1f} MB)")
    print("  reverse_geocode() ora usa cities1000 (~150k città mondiali)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
