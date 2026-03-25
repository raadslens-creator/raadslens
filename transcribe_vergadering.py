#!/usr/bin/env python3
"""
Raadslens - Transcriptie script
Features:
- Transcriptie met faster-whisper + custom vocabulary
- Post-processing correctielijst
- Twijfelgevallen detector via edit distance
- GitHub Issue aanmaken met twijfelgevallen
- Naam-cache systeem (leert namen uit API)
- Historische ondertiteling scraper (bestuurlijkeinformatie.nl)
- Timing-correctie voor intro en schorsingen
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROYALCAST_API = "https://channel.royalcast.com/portal/api/1.0/gemeentetexel/webcasts/gemeentetexel"
IBABS_BASE = "https://texel.bestuurlijkeinformatie.nl"
REPO = os.environ.get("GITHUB_REPOSITORY", "")
GITHUB_TOKEN = os.environ.get("GH_TOKEN", "")
DATE_ID = os.environ.get("DATE_ID", "")
TRANSCRIPTIES_DIR = Path("docs/transcripties")
NAMEN_CACHE_FILE = Path("docs/namen_cache.json")
VOCABULARY_CACHE_FILE = Path("docs/vocabulary_cache.json")

MAANDEN = {
    1: "januari", 2: "februari", 3: "maart", 4: "april",
    5: "mei", 6: "juni", 7: "juli", 8: "augustus",
    9: "september", 10: "oktober", 11: "november", 12: "december"
}

# ============================================================
# POST-PROCESSING CORRECTIELIJST
# Gevalideerde correcties op basis van transcriptie-analyse
# ============================================================
CORRECTIES = {
    # Plaatsnamen
    "Tesla": "Texel",
    "Tessel": "Texel",
    "Tesselse": "Texelse",
    "Tesselaars": "Texelaars",
    "teselaza": "Texelaars",
    "Tesla-rebuest": "Texelse",
    "Schiemonenkoog": "Schiermonnikoog",
    "Schiemelde Kog": "Schiermonnikoog",
    "Schiemelde Kooge": "Schiermonnikoog",
    "Schimmonenkoog": "Schiermonnikoog",
    "Schirmelenkoog": "Schiermonnikoog",
    "Schimmelenkoog": "Schiermonnikoog",
    "Schimonekoog": "Schiermonnikoog",
    "Scheldingen": "Terschelling",
    "Wadderijlanden": "Waddeneilanden",
    "Wadderijland": "Waddeneiland",
    "Wadde dijk": "Waddendijk",
    "Noord-Wolland-Noord": "Noord-Holland-Noord",
    "Noordeland Noord": "Noord-Holland Noord",
    "Dijken-Tessel": "Dijken Texel",

    # Namen
    "Herkoles": "Hercules",
    "Herkler": "Hercules",
    "Herklus": "Hercules",
    "Herkles": "Hercules",
    "Hartvertesel": "Hart voor Texel",
    "Kormann": "Kooiman",
    "Kuiman": "Kooiman",
    "Zweijer": "Soyer",
    "Swajain": "Soyer",
    "Svallier": "Soyer",
    "Svaljei": "Soyer",
    "Swaye": "Soyer",
    "Zaier": "Soyer",
    "De Ros": "Dros",
    "Hogeheide": "Hoogerheide",
    "Hoogheide": "Hoogerheide",
    "Hoogharde": "Hoogerheide",
    "Holgaarden": "Hoogerheide",
    "Oogheide": "Hoogerheide",
    "Huiflom": "Huisman",
    "Gerand": "Rand",
    "van der Belth": "van de Belt",

    # Begrippen
    "Juice": "Deuce",
    "Sientwijs": "Zienswijze",
    "synswijze": "zienswijze",
    "zinswijze": "zienswijze",
    "Kaaldernota": "Kadernota",
    "kadelnota": "kadernota",
    "Kiescompass": "Kieskompas",
    "watkabel": "Wadkabel",
    "Westvrieze": "Westfriese",
    "Gaantafel": "Ga aan tafel",
    "volwaden": "voorwaarden",
    "vrij blijvond": "vrijblijvend",
    "vrijblijventijd": "vrijblijvendheid",
    "amitieuzer": "ambitieuzer",
    "energie-congrestie": "energiecongestie",
    "dijkversvaringstraject": "dijkversterkingstraject",
    "dijkversvaringen": "dijkversterkingen",
    "tusserappertage": "tussenrapportage",
    "handhavenkantie": "handhavingsstrategie",
    "raastvergadering": "raadsvergadering",
    "raastraan": "raad zijn",
    "portafiljouder": "portefeuillehouder",
    "portafouder": "portefeuillehouder",
    "portevaar": "portefeuillehouder",
    "sloopvormaalige": "sloop voormalige",
    "korthalde": "karthal De",
    "pipowagos": "pipowagens",
    "fjordtrekkers": "shorttrackers",
    "lepenlaar": "lepelaar",
    "invandalisatie": "inventarisatie",
    "inventarizatie": "inventarisatie",
    "bedelbanen": "padelbanen",
    "pedelbanen": "padelbanen",
    "gepredeld": "gepaddeld",
    "gepedeld": "gepaddeld",
    "het swoort": "enzovoort",
    "Vriesland": "Friesland",
}

# Achternamen die zeker kloppen uit het officiële proces-verbaal
ACHTERNAMEN_TEXEL = [
    # Texels Belang
    "van der Werf", "de Lugt", "Koot", "Timmermans", "Oosterhof", "Kuip",
    "Hooijschuur", "Duinker", "Zwezerijn", "Heijne", "van Dee", "Dros",
    "Groeskamp", "van der Wal", "Kikkert", "Hoogerheide",
    # PvdA
    "Visser-Veltkamp", "van de Belt", "Komdeur", "Breedveld", "van Ouwendorp",
    "Boschman", "van Bruggen", "Schooneman", "Lelij", "Barnard",
    "van IJsseldijk", "Oosterbaan", "Rudolph", "Hercules",
    # GroenLinks
    "Mokveld", "Wiersma", "ter Borg", "von Meyjenfeldt", "Soyer",
    "Festen", "Berger", "te Sligte", "Bale", "Bohnen", "de Vrind",
    "Kompier", "de Jong", "Zegel", "Ridderinkhof", "Kieft",
    # VVD
    "Ran", "Albers", "Huisman", "Bakker", "van der Werff", "van Wijk",
    "de Lange", "van den Heuvel", "Ciçek", "van Lingen", "Schuiringa",
    "Mantje", "Koenen", "Timmer", "Eelman", "Knol", "Pellen",
    "Kaak", "Rab", "Tromp", "van der Kooi",
    # CDA
    "Rutten", "Houwing", "van der Knaap", "Zegeren",
    # D66
    "van de Wetering", "Leclou", "Holman", "Barendregt", "Aardema",
    "Huitema", "van Overmeeren", "Verbraeken", "Snijders",
    "Brinkman", "van Damme", "Eijzinga", "Lindeboom", "van Heerwaarden",
    # Hart voor Texel
    "Polderman", "Kooiman", "Vonk", "Bloem", "Schouwstra", "Boumans-Beijert",
    "Kaercher", "van Beek", "Röpke", "Ris", "Zegers", "Kalis", "Krab",
    "de Porto", "Daalder", "Stroes", "van der Vaart", "Ekker",
    "van 't Noordende", "Winnubst",
    # SP
    "Overbeeke", "Adema", "Hoven", "Hilhorst", "Geurtz", "Cremers", "Dijksen",
    # Bestuur
    "Pol",
]

# Vaste begrippen
VASTE_BEGRIPPEN = [
    "Texel", "Texels", "Texelaar", "Texelaars",
    "Den Burg", "De Koog", "De Cocksdorp", "Oosterend", "Oudeschild",
    "De Waal", "Midsland", "De Westereen", "Eijerland",
    "Waddeneilanden", "Waddenzee", "Schiermonnikoog", "Vlieland",
    "Terschelling", "Ameland", "TESO", "Marsdiep", "Slufter",
    "Deuce", "Deuce Tennis", "padelbanen", "padelvereniging",
    "gemeenteraad", "raadsvergadering", "raadslid", "wethouder",
    "burgemeester", "griffier", "college van B en W",
    "raadsbesluit", "amendement", "zienswijze", "kadernota",
    "coalitieakkoord", "hamerstuk", "bespreekstuk", "motie",
    "initiatiefvoorstel", "reglement van orde", "portefeuillehouder",
    "Texels Belang", "GroenLinks", "Hart voor Texel",
    "Omgevingsdienst Noord-Holland Noord", "ODNHN",
    "Veiligheidsregio Noord-Holland Noord", "GGD Hollands Noorden",
    "Regionaal Historisch Centrum Alkmaar", "RHCA",
    "Regionale Raadscommissie Noordkop", "RRN",
    "toeristenbelasting", "bestemmingsplan", "omgevingsvisie",
    "woningbouwprogramma", "klimaatadaptatieplan", "energietransitie",
    "Stappeland", "karthal", "vuurwerkverbod", "kustverdediging",
    "dijknormering", "waterveiligheid", "waddengebied",
    "Wadkabel", "energiecongestie", "dijkversterking",
    "Kieskompas", "tussenrapportage", "inventarisatie",
    "Woontij", "Staatsbosbeheer", "Rijkswaterstaat",
    "Hoogheemraadschap Hollands Noorderkwartier",
    "Mienterglop", "Thijssehuis", "Stappeland", "Marsweg",
    "Sportpark Den Burg Zuid",
]


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def parse_royalcast_timestamp(ts_str):
    if not ts_str:
        return None
    match = re.search(r"\d+", ts_str)
    if match:
        return int(match.group()) / 1000
    return None


# ============================================================
# NAAM CACHE
# ============================================================

def load_namen_cache():
    if NAMEN_CACHE_FILE.exists():
        return json.loads(NAMEN_CACHE_FILE.read_text())
    return {}


def save_namen_cache(cache):
    NAMEN_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    NAMEN_CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False))


def update_namen_cache(data, cache):
    updated = False
    for spreker in data.get("speakers", []):
        naam = spreker.get("name", {})
        voornaam = naam.get("first", "")
        achternaam = naam.get("last", "")
        tussenvoegsel = naam.get("middle", "")
        if not achternaam or not voornaam:
            continue
        volledige_naam = " ".join(filter(None, [voornaam, tussenvoegsel, achternaam]))
        sleutel = achternaam.lower()
        if sleutel not in cache or cache[sleutel] != volledige_naam:
            cache[sleutel] = volledige_naam
            log(f"Naam geleerd: {volledige_naam}")
            updated = True
    return cache, updated


# ============================================================
# HISTORISCHE ONDERTITELING SCRAPER
# ============================================================

def load_vocabulary_cache():
    if VOCABULARY_CACHE_FILE.exists():
        return json.loads(VOCABULARY_CACHE_FILE.read_text())
    return {"woorden": [], "laatste_update": None, "vergaderingen_verwerkt": []}


def save_vocabulary_cache(cache):
    VOCABULARY_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    VOCABULARY_CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False))


def fetch_vergadering_ids():
    """Haal vergadering-IDs op van bestuurlijkeinformatie.nl via de kalender."""
    url = f"{IBABS_BASE}/Calendar"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        # Zoek agenda IDs in de HTML
        ids = re.findall(r'/Agenda/Index/([a-f0-9-]{36})', html)
        return list(set(ids))
    except Exception as e:
        log(f"Kalender ophalen mislukt: {e}")
        return []


def fetch_ondertiteling_van_vergadering(agenda_id):
    """Haal de ondertiteling PDF op van een vergadering."""
    url = f"{IBABS_BASE}/Agenda/Index/{agenda_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Zoek naar ondertiteling document
        matches = re.findall(
            r'/Agenda/Document/' + agenda_id + r'\?documentId=([a-f0-9-]{36})',
            html
        )
        # Zoek ook naar "ondertiteling" in tekst nabij document links
        ondertiteling_ids = []
        for m in re.finditer(r'[Oo]ndertiteling[^"]*"[^"]*documentId=([a-f0-9-]{36})', html):
            ondertiteling_ids.append(m.group(1))

        if not ondertiteling_ids and matches:
            # Fallback: pak alle documenten en filter later
            return None

        for doc_id in ondertiteling_ids[:1]:
            pdf_url = f"{IBABS_BASE}/Agenda/Document/{agenda_id}?documentId={doc_id}"
            try:
                req2 = urllib.request.Request(pdf_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req2, timeout=15) as resp2:
                    content_type = resp2.headers.get("Content-Type", "")
                    if "pdf" in content_type.lower():
                        return resp2.read()
            except Exception:
                pass
        return None
    except Exception as e:
        log(f"Vergadering {agenda_id} ophalen mislukt: {e}")
        return None


def extract_woorden_uit_pdf(pdf_bytes):
    """Extraheer relevante woorden uit PDF bytes via pdfminer."""
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp_path = f.name

        result = subprocess.run(
            ["python3", "-m", "pdfminer.high_level", tmp_path],
            capture_output=True, text=True, timeout=30
        )
        Path(tmp_path).unlink(missing_ok=True)

        if result.returncode != 0:
            return []

        tekst = result.stdout
        # Extraheer unieke woorden van 4+ tekens, Nederlandse tekst
        woorden = re.findall(r'\b[A-Za-zÀ-ÿ]{4,}\b', tekst)
        # Filter stopwoorden en korte woorden
        stopwoorden = {"voor", "deze", "maar", "door", "over", "naar", "zijn",
                       "heeft", "worden", "kunnen", "moet", "wordt", "geen",
                       "meer", "ook", "niet", "veel", "heel", "even", "want",
                       "zoals", "want", "omdat", "wanneer", "zodat", "toch",
                       "reeds", "aldus", "immers", "evenwel", "hierbij"}
        return [w for w in set(woorden) if w.lower() not in stopwoorden and len(w) >= 4]
    except Exception as e:
        log(f"PDF extractie mislukt: {e}")
        return []


def update_vocabulary_uit_ondertitelingen(vocab_cache, max_vergaderingen=10):
    """
    Haal historische ondertitelingen op en voed de vocabulary.
    Verwerkt maximaal max_vergaderingen nieuwe vergaderingen per run.
    """
    log("Historische ondertitelingen ophalen...")

    try:
        subprocess.run(
            ["pip", "install", "pdfminer.six", "-q"],
            capture_output=True, check=False
        )
    except Exception:
        pass

    agenda_ids = fetch_vergadering_ids()
    log(f"{len(agenda_ids)} vergadering-IDs gevonden")

    verwerkt = set(vocab_cache.get("vergaderingen_verwerkt", []))
    nieuwe_woorden = set(vocab_cache.get("woorden", []))
    count = 0

    for agenda_id in agenda_ids:
        if agenda_id in verwerkt:
            continue
        if count >= max_vergaderingen:
            break

        pdf_bytes = fetch_ondertiteling_van_vergadering(agenda_id)
        if not pdf_bytes:
            verwerkt.add(agenda_id)
            continue

        woorden = extract_woorden_uit_pdf(pdf_bytes)
        if woorden:
            nieuwe_woorden.update(woorden)
            log(f"  {agenda_id}: {len(woorden)} woorden")
            count += 1

        verwerkt.add(agenda_id)

    vocab_cache["woorden"] = list(nieuwe_woorden)
    vocab_cache["vergaderingen_verwerkt"] = list(verwerkt)
    vocab_cache["laatste_update"] = datetime.now().isoformat()

    log(f"Vocabulary bijgewerkt: {len(nieuwe_woorden)} woorden totaal")
    return vocab_cache


# ============================================================
# VOCABULARY BUILDER
# ============================================================

def build_vocabulary(namen_cache, vocab_cache):
    """Bouw volledige vocabulary op voor Whisper."""
    namen = list(VASTE_BEGRIPPEN) + list(ACHTERNAMEN_TEXEL)

    # Volledige namen uit cache
    for volledige_naam in namen_cache.values():
        if volledige_naam not in namen:
            namen.append(volledige_naam)

    # Woorden uit historische ondertitelingen
    historische_woorden = vocab_cache.get("woorden", [])
    # Voeg alleen woorden toe die niet al voorkomen
    bestaande = set(n.lower() for n in namen)
    for w in historische_woorden[:200]:  # Max 200 extra woorden
        if w.lower() not in bestaande:
            namen.append(w)

    return ", ".join(namen[:300])  # Whisper heeft een limiet op initial_prompt


# ============================================================
# TWIJFELGEVALLEN DETECTOR
# ============================================================

def edit_distance(s1, s2):
    """Levenshtein edit distance."""
    if len(s1) < len(s2):
        return edit_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1,
                           prev[j] + (0 if c1 == c2 else 1)))
        prev = curr
    return prev[-1]


def detecteer_twijfelgevallen(tekst, namen_cache, vocab_cache):
    """
    Detecteer woorden die lijken op bekende termen maar net anders gespeld zijn.
    Geeft lijst van (verkeerd woord, meest waarschijnlijke correctie, score).
    """
    bekende_termen = set()
    bekende_termen.update(VASTE_BEGRIPPEN)
    bekende_termen.update(ACHTERNAMEN_TEXEL)
    bekende_termen.update(namen_cache.values())
    bekende_termen.update(CORRECTIES.values())

    woorden_in_tekst = re.findall(r'\b[A-Za-zÀ-ÿ]{5,}\b', tekst)
    twijfels = []
    al_gemeld = set()

    for woord in set(woorden_in_tekst):
        if woord in al_gemeld:
            continue
        if woord in bekende_termen:
            continue
        if woord.lower() in {t.lower() for t in bekende_termen}:
            continue
        if woord in CORRECTIES:
            continue

        # Zoek dichtstbijzijnde bekende term
        beste_match = None
        beste_score = 999
        for term in bekende_termen:
            if abs(len(woord) - len(term)) > 3:
                continue
            d = edit_distance(woord.lower(), term.lower())
            if d < beste_score and d <= 2:
                beste_score = d
                beste_match = term

        if beste_match and beste_score <= 2:
            twijfels.append((woord, beste_match, beste_score))
            al_gemeld.add(woord)

    return sorted(twijfels, key=lambda x: x[2])


# ============================================================
# GITHUB ISSUE AANMAKEN
# ============================================================

def maak_github_issue(date_id, date_str, twijfels, transcript_url=None):
    """Maak een GitHub Issue aan met twijfelgevallen voor review."""
    if not GITHUB_TOKEN or not REPO:
        log("Geen GitHub token - Issue overgeslagen")
        return

    if not twijfels:
        log("Geen twijfelgevallen - geen Issue aangemaakt")
        return

    # Bouw issue body
    regels = [
        f"## Twijfelgevallen transcriptie {date_str}",
        "",
        "Whisper heeft mogelijk fouten gemaakt bij de volgende woorden. "
        "Reageer op dit issue met correcties in het formaat `woord → correctie`.",
        "",
        "| Gevonden | Meest waarschijnlijk | Zekerheid |",
        "|----------|---------------------|-----------|",
    ]

    for woord, match, score in twijfels[:25]:
        zekerheid = "waarschijnlijk" if score == 1 else "mogelijk"
        regels.append(f"| {woord} | {match} | {zekerheid} |")

    if transcript_url:
        regels.extend(["", f"Transcriptie: {transcript_url}"])

    regels.extend([
        "",
        "---",
        "_Automatisch gegenereerd door Raadslens transcriptie-pipeline_"
    ])

    body = "\n".join(regels)

    issue_data = json.dumps({
        "title": f"Twijfelgevallen transcriptie {date_str}",
        "body": body,
        "labels": ["transcriptie", "correctie-nodig"],
    }).encode()

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }

    # Maak labels aan als ze niet bestaan
    for label in ["transcriptie", "correctie-nodig"]:
        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/{REPO}/labels",
                data=json.dumps({"name": label, "color": "0075ca"}).encode(),
                headers=headers,
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass  # Label bestaat al

    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/issues",
        data=issue_data,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            issue = json.loads(resp.read())
            log(f"GitHub Issue aangemaakt: {issue['html_url']}")
    except Exception as e:
        log(f"Issue aanmaken mislukt: {e}")


# ============================================================
# POST-PROCESSING
# ============================================================

def pas_correcties_toe(tekst):
    """Pas de correctielijst toe op de transcriptietekst."""
    for fout, goed in CORRECTIES.items():
        # Case-insensitive maar behoud hoofdletter aan begin van zin
        tekst = re.sub(
            r'\b' + re.escape(fout) + r'\b',
            goed,
            tekst
        )
        # Ook met hoofdletter
        if fout[0].islower():
            tekst = re.sub(
                r'\b' + re.escape(fout.capitalize()) + r'\b',
                goed.capitalize(),
                tekst
            )
    return tekst


# ============================================================
# RELEASE / DOWNLOAD FUNCTIES
# ============================================================

def get_latest_release_with_mp3():
    TRANSCRIPTIES_DIR.mkdir(parents=True, exist_ok=True)
    url = f"https://api.github.com/repos/{REPO}/releases?per_page=10"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        releases = json.loads(resp.read())

    for release in releases:
        tag = release.get("tag_name", "")
        match = re.search(r"vergadering-(\d{8}_\d+)", tag)
        if not match:
            continue
        date_id = match.group(1)
        transcript_file = TRANSCRIPTIES_DIR / f"{date_id}.txt"
        if transcript_file.exists():
            continue
        for asset in release.get("assets", []):
            if asset["name"].endswith(".mp3"):
                return date_id, asset["browser_download_url"]
    return None, None


def get_release_mp3_url(date_id):
    url = f"https://api.github.com/repos/{REPO}/releases/tags/vergadering-{date_id}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        release = json.loads(resp.read())
    for asset in release.get("assets", []):
        if asset["name"].endswith(".mp3"):
            return asset["browser_download_url"]
    return None


def download_mp3(url, date_id):
    output = f"audio/{date_id}_transcript.mp3"
    Path("audio").mkdir(exist_ok=True)
    log(f"MP3 downloaden...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        with open(output, "wb") as f:
            f.write(resp.read())
    log(f"Download OK ({Path(output).stat().st_size / 1024 / 1024:.1f} MB)")
    return output


# ============================================================
# WEBCAST DATA & SPREKERS
# ============================================================

def get_webcast_data(date_id):
    url = f"{ROYALCAST_API}/{date_id}?method=GET&key="
    log(f"Webcast-data ophalen...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log(f"API fout: {e}")
        return {}


def get_intro_duration(data):
    actual_start = parse_royalcast_timestamp(data.get("actualStart"))
    if not actual_start:
        return 0
    earliest_event = None
    for topic in data.get("topics", []):
        for event in topic.get("events", []):
            event_start = parse_royalcast_timestamp(event.get("start"))
            if event_start and (earliest_event is None or event_start < earliest_event):
                earliest_event = event_start
    if not earliest_event:
        return 0
    return max(0, earliest_event - actual_start)


def detect_silences(audio_file, threshold_db="-35dB", min_duration=45):
    detect_cmd = [
        "ffmpeg", "-i", audio_file,
        "-af", f"silencedetect=noise={threshold_db}:d={min_duration}",
        "-f", "null", "-"
    ]
    result = subprocess.run(detect_cmd, capture_output=True, text=True)
    starts = re.findall(r"silence_start: ([\d.]+)", result.stderr)
    ends = re.findall(r"silence_end: ([\d.]+)", result.stderr)
    return [
        (float(s), float(e))
        for s, e in zip(starts, ends)
        if float(e) - float(s) >= min_duration
    ]


def get_speaker_timeline(data):
    actual_start = parse_royalcast_timestamp(data.get("actualStart"))
    if not actual_start:
        log("Geen actualStart - sprekerherkenning beperkt")
        return []
    speakers = []
    for spreker in data.get("speakers", []):
        naam = spreker.get("name", {})
        volledige_naam = " ".join(filter(None, [
            naam.get("first", ""),
            naam.get("middle", ""),
            naam.get("last", ""),
        ])).strip()
        if not volledige_naam:
            continue
        for event in spreker.get("events", []):
            start_sec = parse_royalcast_timestamp(event.get("start"))
            end_sec = parse_royalcast_timestamp(event.get("end"))
            if not start_sec or not end_sec:
                continue
            rel_start = start_sec - actual_start
            rel_end = end_sec - actual_start
            if rel_start >= 0:
                speakers.append((rel_start, rel_end, volledige_naam))
    speakers.sort(key=lambda x: x[0])
    log(f"{len(speakers)} spreekbeurten voor {len(set(s[2] for s in speakers))} sprekers")
    return speakers


def correct_speaker_times(speakers, intro_sec, silences):
    corrected = []
    for start, end, naam in speakers:
        t_start = max(0, start - intro_sec)
        t_end = max(0, end - intro_sec)
        removed_start = sum(
            min(sil_end, t_start) - sil_start
            for sil_start, sil_end in silences
            if sil_start < t_start
        )
        removed_end = sum(
            min(sil_end, t_end) - sil_start
            for sil_start, sil_end in silences
            if sil_start < t_end
        )
        corrected.append((
            max(0, t_start - removed_start),
            max(0, t_end - removed_end),
            naam
        ))
    return corrected


def find_speaker_at(timestamp, speakers):
    for start, end, naam in speakers:
        if start <= timestamp <= end:
            return naam
    return None


# ============================================================
# TRANSCRIPTIE
# ============================================================

def transcribe_audio(audio_file, vocabulary):
    log("Transcriptie starten met faster-whisper...")
    log("Model laden...")
    from faster_whisper import WhisperModel
    model = WhisperModel("small", device="cpu", compute_type="int8")
    log("Transcriberen...")
    segments, info = model.transcribe(
        audio_file,
        language="nl",
        beam_size=3,
        initial_prompt=vocabulary,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500)
    )
    log(f"Taal gedetecteerd: {info.language} ({info.language_probability:.0%})")
    result = []
    for segment in segments:
        result.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip(),
        })
    log(f"{len(result)} segmenten getranscribeerd")
    return result


def format_timestamp(sec):
    if sec is None:
        return "00:00:00"
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def build_transcript(segments, speakers, data, date_str):
    lines = []
    lines.append("RAADSVERGADERING TEXEL")
    lines.append(date_str)
    lines.append("=" * 60)
    lines.append("")

    topics = data.get("topics", []) if data else []
    if topics:
        lines.append("AGENDA")
        lines.append("-" * 30)
        for t in topics:
            lines.append(f"  {t.get('title', '')}")
        lines.append("")
        lines.append("=" * 60)
        lines.append("")

    lines.append("TRANSCRIPTIE")
    lines.append("-" * 30)
    lines.append("")

    current_speaker = None
    current_block = []
    current_start = None

    for seg in segments:
        speaker = find_speaker_at(seg["start"], speakers) if speakers else None
        text = seg["text"]

        if speaker != current_speaker or (speaker is None and len(current_block) > 20):
            if current_block and current_start is not None:
                ts = format_timestamp(current_start)
                label = f" {current_speaker.upper()}" if current_speaker else ""
                lines.append(f"[{ts}]{label}")
                lines.append(" ".join(current_block))
                lines.append("")
            if speaker != current_speaker:
                current_speaker = speaker
            current_block = [text]
            current_start = seg["start"]
        else:
            current_block.append(text)

    if current_block and current_start is not None:
        ts = format_timestamp(current_start)
        label = f" {current_speaker.upper()}" if current_speaker else ""
        lines.append(f"[{ts}]{label}")
        lines.append(" ".join(current_block))
        lines.append("")

    return "\n".join(lines)


def upload_transcript_to_release(date_id, transcript_text):
    if not GITHUB_TOKEN or not REPO:
        return None
    url = f"https://api.github.com/repos/{REPO}/releases/tags/vergadering-{date_id}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            release = json.loads(resp.read())
    except Exception as e:
        log(f"Release niet gevonden: {e}")
        return None

    upload_url = release["upload_url"].replace("{?name,label}", "")
    filename = f"{date_id}_transcriptie.txt"
    upload_headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "text/plain",
    }
    req = urllib.request.Request(
        f"{upload_url}?name={filename}",
        data=transcript_text.encode("utf-8"),
        headers=upload_headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            asset = json.loads(resp.read())
            log(f"Transcriptie geüpload: {asset['browser_download_url']}")
            return asset["browser_download_url"]
    except Exception as e:
        log(f"Upload fout: {e}")
        return None


# ============================================================
# MAIN
# ============================================================

def main():
    log("=== Raadslens Transcriptie ===")

    if not REPO or not GITHUB_TOKEN:
        log("Geen REPO of GITHUB_TOKEN")
        sys.exit(1)

    # Caches laden
    namen_cache = load_namen_cache()
    vocab_cache = load_vocabulary_cache()
    log(f"Naam-cache: {len(namen_cache)} bekende namen")
    log(f"Vocabulary cache: {len(vocab_cache.get('woorden', []))} historische woorden")

    # Historische ondertitelingen ophalen (max 5 per run om tijd te sparen)
    vergaderingen_verwerkt = len(vocab_cache.get("vergaderingen_verwerkt", []))
    if vergaderingen_verwerkt < 30:
        log("Historische ondertitelingen ophalen...")
        vocab_cache = update_vocabulary_uit_ondertitelingen(vocab_cache, max_vergaderingen=5)
        save_vocabulary_cache(vocab_cache)

    # Bepaal welke vergadering
    if DATE_ID:
        log(f"Handmatig opgegeven: {DATE_ID}")
        date_id = DATE_ID
        mp3_url = get_release_mp3_url(date_id)
        if not mp3_url:
            log("Geen MP3 gevonden in release")
            sys.exit(1)
    else:
        date_id, mp3_url = get_latest_release_with_mp3()
        if not date_id:
            log("Geen vergadering gevonden om te transcriberen")
            sys.exit(0)

    log(f"Vergadering: {date_id}")

    try:
        dt = datetime.strptime(date_id[:8], "%Y%m%d")
        date_str = f"{dt.day} {MAANDEN[dt.month]} {dt.year}"
    except Exception:
        date_str = date_id[:8]

    # Webcast-data ophalen
    data = get_webcast_data(date_id)

    # Namen uit API in cache opslaan
    if data:
        namen_cache, updated = update_namen_cache(data, namen_cache)
        if updated:
            save_namen_cache(namen_cache)

    # Vocabulary opbouwen
    vocabulary = build_vocabulary(namen_cache, vocab_cache)
    log(f"Vocabulary gebouwd")

    # Intro-duur
    intro_sec = get_intro_duration(data)
    log(f"Intro: {intro_sec:.0f}s")

    # MP3 downloaden
    audio_file = download_mp3(mp3_url, date_id)

    # Stiltes detecteren
    log("Stiltes detecteren voor timing-correctie...")
    silences = detect_silences(audio_file)
    log(f"{len(silences)} schorsingen gevonden")

    # Sprekerdata
    raw_speakers = get_speaker_timeline(data)
    if raw_speakers:
        speakers = correct_speaker_times(raw_speakers, intro_sec, silences)
        log(f"Spreker-tijden gecorrigeerd")
    else:
        speakers = []

    # Transcriberen
    segments = transcribe_audio(audio_file, vocabulary)
    if not segments:
        log("Geen transcriptie gegenereerd")
        sys.exit(1)

    # Transcript opbouwen
    transcript_raw = build_transcript(segments, speakers, data, date_str)

    # Post-processing correcties toepassen
    log("Post-processing correcties toepassen...")
    transcript = pas_correcties_toe(transcript_raw)

    # Twijfelgevallen detecteren
    log("Twijfelgevallen detecteren...")
    twijfels = detecteer_twijfelgevallen(transcript, namen_cache, vocab_cache)
    log(f"{len(twijfels)} twijfelgevallen gevonden")

    # Opslaan
    TRANSCRIPTIES_DIR.mkdir(parents=True, exist_ok=True)
    transcript_file = TRANSCRIPTIES_DIR / f"{date_id}.txt"
    transcript_file.write_text(transcript, encoding="utf-8")
    log(f"Transcriptie opgeslagen: {transcript_file}")

    # Uploaden bij release
    transcript_url = upload_transcript_to_release(date_id, transcript)

    # GitHub Issue aanmaken met twijfelgevallen
    if twijfels:
        maak_github_issue(date_id, date_str, twijfels, transcript_url)

    log("Klaar!")


if __name__ == "__main__":
    main()
