#!/usr/bin/env python3
"""Print alle actieve gemeente-IDs, één per regel."""
import json
from pathlib import Path

config = json.loads(Path("gemeenten.json").read_text())
for g in config["gemeenten"]:
    if g.get("actief", True):
        print(g["id"])
