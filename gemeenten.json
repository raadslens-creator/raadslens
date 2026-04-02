#!/usr/bin/env python3
"""
scrape_raadsleden.py — haalt raadsleden, fracties en commissieleden op van iBabs
voor elke gemeente die op iBabs draait.

Schaalbaar: je hoeft alleen de gemeente toe te voegen aan gemeenten.json.
De scraper vindt automatisch de juiste profielpagina's via /People.
"""

import json, re, sys, time, urllib.request, urllib.error
from pathlib import Path
from html.parser import HTMLParser
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "nl-NL,nl;q=0.9",
}
IBABS_PATTERN = "https://{id}.bestuurlijkeinformatie.nl"


def log(msg): print(msg, flush=True)


def fetch(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            log(f"  HTTP {e.code}: {url}")
            if e.code in (403, 404): return None
            time.sleep(2 ** attempt)
        except Exception as e:
            log(f"  Fout ({attempt+1}): {e}")
            time.sleep(2 ** attempt)
    return None


class PeopleIndexParser(HTMLParser):
    """Haalt profiel-UUID's op van /People."""
    def __init__(self):
        super().__init__()
        self.profiles = {}  # label_lower -> uuid
        self._href = None
        self._buf = ""
        self._in = False

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href", "")
            m = re.search(r"/People/Profiles/([a-f0-9\-]{36})", href)
            if m:
                self._href = m.group(1)
                self._buf = ""
                self._in = True

    def handle_data(self, data):
        if self._in: self._buf += data

    def handle_endtag(self, tag):
        if tag == "a" and self._in and self._href:
            label = self._buf.strip()
            if label:
                self.profiles[label.lower()] = self._href
                log(f"    Profiel: '{label}' → {self._href}")
            self._in = False
            self._href = None


class ProfileParser(HTMLParser):
    """Parseert een /People/Profiles/{uuid} pagina naar fracties + leden."""
    def __init__(self):
        super().__init__()
        self.fracties = {}
        self.raw = ""
        self._stack = []
        self._fractie = None
        self._buf = ""
        self._in_h = False
        self._in_person = False
        self._in_name = False
        self._in_role = False
        self._person = {}

    def handle_starttag(self, tag, attrs):
        self._stack.append(tag)
        cls = dict(attrs).get("class", "").lower()

        if tag in ("h2","h3","h4"):
            self._in_h = True; self._buf = ""

        if tag in ("div","article","li","section") and any(
                c in cls for c in ["person","member","raadslid","people-item","profile-item","contact","card"]):
            self._in_person = True
            self._person = {"naam": None, "rol": None}

        if self._in_person and tag in ("h3","h4","h5","span","strong","a","p","div") and any(
                c in cls for c in ["name","naam","title","fullname","person-name","card-title"]):
            self._in_name = True; self._buf = ""

        if self._in_person and tag in ("span","div","p","small") and any(
                c in cls for c in ["role","rol","function","functie","subtitle","position","card-subtitle"]):
            self._in_role = True; self._buf = ""

    def handle_data(self, data):
        self.raw += data
        t = data.strip()
        if (self._in_h or self._in_name or self._in_role) and t:
            self._buf += t

    def handle_endtag(self, tag):
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()

        if tag in ("h2","h3","h4") and self._in_h:
            f = self._buf.strip()
            if f and len(f) < 80:
                self._fractie = f
                if f not in self.fracties: self.fracties[f] = []
            self._in_h = False; self._buf = ""

        if self._in_name:
            naam = self._buf.strip()
            if naam and not self._person.get("naam"):
                self._person["naam"] = naam
            self._in_name = False; self._buf = ""

        if self._in_role:
            rol = self._buf.strip()
            if rol: self._person["rol"] = rol
            self._in_role = False; self._buf = ""

        if self._in_person and tag in ("div","article","li","section"):
            naam = self._person.get("naam")
            if naam and self._fractie:
                bestaand = [p["naam"] for p in self.fracties.get(self._fractie, [])]
                if naam not in bestaand:
                    self.fracties[self._fractie].append({
                        "naam": naam,
                        "rol": self._person.get("rol", "Raadslid"),
                    })
            self._in_person = False
            self._person = {}

    def fallback(self):
        """Patroon-matching op ruwe tekst als class-parser niets vindt."""
        fracties = {}
        lines = [l.strip() for l in self.raw.split("\n") if l.strip()]
        naam_re = re.compile(
            r"\b([A-Z][a-zéëïöüàáâ]+(?:[\s\-][a-z]{1,4}[\s\-])?[A-Z][a-zéëïöüàáâ\-]+(?:\s[A-Z][a-zéëïöüàáâ\-]+)?)\b"
        )
        skip = {"Raadslid","Commissielid","Wethouder","Burgemeester","Voorzitter",
                "Griffier","De heer","Mevrouw","Griffie","Rekenkamer","Raad","Commissie"}
        fractie = None
        for line in lines:
            if (re.match(r"^[A-Z][A-Za-z0-9\s\-\'\.]{2,50}$", line)
                    and line not in skip
                    and not any(kw in line.lower() for kw in ["http","menu","login","zoek","home"])):
                fractie = line
                if fractie not in fracties: fracties[fractie] = []
                continue
            if fractie:
                for naam in naam_re.findall(line):
                    if naam not in skip and len(naam) > 5:
                        if not any(p["naam"] == naam for p in fracties[fractie]):
                            fracties[fractie].append({"naam": naam, "rol": "Raadslid"})
        return fracties


def find_uuid(profiles, keywords):
    for kw in keywords:
        for label, uuid in profiles.items():
            if kw in label: return uuid
    return None


def scrape_profile(base, uuid, label=""):
    url = f"{base}/People/Profiles/{uuid}"
    log(f"  Scrapen ({label}): {url}")
    html = fetch(url)
    if not html: return {}
    p = ProfileParser()
    p.feed(html)
    fracties = p.fracties
    if not fracties:
        log("    Fallback parser")
        fracties = p.fallback()
    fracties = {k: v for k, v in fracties.items() if v and len(k) > 2}
    log(f"    {len(fracties)} fracties, {sum(len(v) for v in fracties.values())} personen")
    return fracties


def scrape_gemeente(gemeente_id, config):
    log(f"\n=== {gemeente_id.upper()} ===")
    base = config.get("ibabs_url") or IBABS_PATTERN.format(id=gemeente_id)
    log(f"  Base: {base}")

    # Stap 1: vind profielpagina's via /People
    html = fetch(f"{base}/People")
    if not html:
        log("  /People niet bereikbaar"); return None

    idx = PeopleIndexParser()
    idx.feed(html)
    profiles = idx.profiles
    if not profiles:
        log("  Geen profielen gevonden"); return None

    # Stap 2: raadsleden
    raad_uuid = config.get("raad_profile_uuid") or find_uuid(profiles, ["gemeenteraad","raadsleden","raad"])
    if not raad_uuid:
        log("  Geen raadsprofiel gevonden"); return None
    raadsleden = scrape_profile(base, raad_uuid, "Raad")

    # Stap 3: commissieleden
    time.sleep(1)
    comm_uuid = config.get("commissie_profile_uuid") or find_uuid(profiles, ["commissie","raads- en commissie"])
    commissieleden = {}
    if comm_uuid and comm_uuid != raad_uuid:
        commissieleden = scrape_profile(base, comm_uuid, "Commissie")

    return {
        "gemeente": gemeente_id,
        "ibabs_base": base,
        "raadsperiode": config.get("raadsperiode", "2026-2030"),
        "burgemeester": config.get("burgemeester"),
        "raadsleden": raadsleden,
        "commissieleden": commissieleden,
        "coalitie": config.get("coalitie"),       # handmatig, wordt niet overschreven
        "wethouders": config.get("wethouders", []), # handmatig, wordt niet overschreven
        "scrape_timestamp": datetime.utcnow().isoformat() + "Z",
    }


def load_config():
    path = Path("gemeenten.json")
    if not path.exists(): return {}
    raw = json.loads(path.read_text())
    result = {}
    for g in raw.get("gemeenten", []):
        gid = g["id"]
        result[gid] = {
            "ibabs_url": g.get("ibabs_url"),
            "raad_profile_uuid": g.get("ibabs_raad_profile_uuid"),
            "commissie_profile_uuid": g.get("ibabs_commissie_profile_uuid"),
            "raadsperiode": g.get("raadsperiode", "2026-2030"),
            "burgemeester": g.get("burgemeester"),
            "coalitie": g.get("coalitie"),
            "wethouders": g.get("wethouders", []),
        }
    return result


def main():
    configs = load_config()
    ids = sys.argv[1:] if len(sys.argv) > 1 else list(configs.keys())

    for gid in ids:
        config = configs.get(gid, {})
        data = scrape_gemeente(gid, config)

        if data:
            out = Path(f"docs/{gid}/gemeente_data.json")
            out.parent.mkdir(parents=True, exist_ok=True)
            # Bewaar handmatige velden uit bestaand bestand
            if out.exists():
                existing = json.loads(out.read_text())
                for field in ("coalitie", "wethouders"):
                    if not data.get(field) and existing.get(field):
                        data[field] = existing[field]
            out.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            log(f"  Opgeslagen: {out}")
        else:
            log(f"  Geen data — bestaand bestand behouden")


if __name__ == "__main__":
    main()
