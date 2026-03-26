#!/usr/bin/env python3
"""
Voert check_officiele_transcriptie uit voor alle actieve gemeenten,
of voor één specifieke gemeente via GEMEENTE_ID environment variabele.
"""
import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    gemeente_id = os.environ.get("GEMEENTE_ID", "").strip()

    config = json.loads(Path("gemeenten.json").read_text())
    gemeenten = [g for g in config["gemeenten"] if g.get("actief", True)]

    if gemeente_id:
        gemeenten = [g for g in gemeenten if g["id"] == gemeente_id]
        if not gemeenten:
            print(f"Gemeente '{gemeente_id}' niet gevonden")
            sys.exit(1)

    for gemeente in gemeenten:
        print(f"\n=== Check: {gemeente['naam']} ===")
        env = os.environ.copy()
        env["GEMEENTE_ID"] = gemeente["id"]
        result = subprocess.run(
            [sys.executable, "check_officiele_transcriptie.py"],
            env=env
        )
        if result.returncode != 0:
            print(f"Check mislukt voor {gemeente['naam']}")


if __name__ == "__main__":
    main()
