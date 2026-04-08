"""
SEP Toernooi – Lokale uploader
================================
Dit script uploadt een lokaal Excel-bestand (Master.xlsm)
automatisch naar GitHub van GJ zodra het bestand gewijzigd wordt.

INSTALLATIE (eenmalig):
    pip install requests watchdog

GEBRUIK:
    python lokale_uploader.py

Het script controleert elke 10 seconden of het bestand gewijzigd is.
Zodra je een score opslaat in Excel wordt het automatisch geüpload.
Stop met Ctrl+C
"""

import os
import sys
import time
import base64
import hashlib
import requests
from datetime import datetime

# ════════════════════════════════════════════════
#  CONFIGURATIE — vul hier jouw gegevens in
# ════════════════════════════════════════════════

# Pad naar het lokale Excel-bestand
# Voorbeelden:
#   Windows:  r'C:\Users\Jouw Naam\Documents\Master.xlsm'
#   Mac/Linux: '/Users/jouwnaam/Documents/Master.xlsm'
LOCAL_FILE = 'Gaster.xlsm'  # of volledig pad als het elders staat

# GitHub
GITHUB_TOKEN     = 'ghp_MjJ3F7 lo7U2AO6xT'   # zie uitleg hieronder
GITHUB_REPO      = 'sep-4x4-schoolvoetbaltoernooi/4x4website_Sep'
GITHUB_BRANCH    = 'main'
GITHUB_FILE_PATH = 'Gaster.xlsm'              # pad in de repo

# Hoe vaak controleren op wijzigingen (seconden)
CHECK_INTERVAL = 60

# ════════════════════════════════════════════════


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def file_hash(path):
    """Bereken MD5 hash van het bestand om wijzigingen te detecteren."""
    with open(path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def get_github_sha():
    """Haal de huidige SHA op van het bestand in GitHub (nodig voor update)."""
    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}'
    resp = requests.get(url, headers={
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
    }, params={'ref': GITHUB_BRANCH})
    if resp.status_code == 200:
        return resp.json().get('sha')
    elif resp.status_code == 404:
        return None  # bestand bestaat nog niet in repo
    else:
        resp.raise_for_status()


def upload_to_github(filepath):
    """Upload het bestand naar GitHub."""
    with open(filepath, 'rb') as f:
        content = f.read()

    sha = get_github_sha()
    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}'

    body = {
        'message': f'Auto-update {datetime.now().strftime("%d-%m-%Y %H:%M:%S")}',
        'content': base64.b64encode(content).decode('utf-8'),
        'branch':  GITHUB_BRANCH,
    }
    if sha:
        body['sha'] = sha  # vereist voor update van bestaand bestand

    resp = requests.put(url, json=body, headers={
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
    })
    resp.raise_for_status()
    size_kb = len(content) // 1024
    log(f"✓ Geüpload naar GitHub ({size_kb} KB)")


def validate_config():
    """Controleer of de configuratie correct is ingevuld."""
    ok = True
    if GITHUB_TOKEN == 'JOUW_GITHUB_TOKEN_HIER':
        print("⚠️  Vul je GITHUB_TOKEN in bovenaan dit bestand!")
        print()
        print("GitHub token aanmaken:")
        print("  1. Ga naar github.com → klik profielfoto → Settings")
        print("  2. Scroll naar beneden → Developer settings")
        print("  3. Personal access tokens → Tokens (classic) → Generate new token")
        print("  4. Naam: 'SEP Uploader', vink 'repo' aan, klik Generate")
        print("  5. Kopieer het token (ghp_...) en plak het hierboven")
        print()
        ok = False

    if not os.path.exists(LOCAL_FILE):
        print(f"⚠️  Bestand niet gevonden: {LOCAL_FILE}")
        print(f"   Pas LOCAL_FILE aan naar het juiste pad.")
        print()
        ok = False

    return ok


def run():
    log("SEP Toernooi – Lokale uploader gestart")
    log(f"Bestand:   {os.path.abspath(LOCAL_FILE)}")
    log(f"GitHub:    {GITHUB_REPO}/{GITHUB_FILE_PATH}")
    log(f"Interval:  elke {CHECK_INTERVAL} seconden")
    log("Druk op Ctrl+C om te stoppen")
    print()

    if not validate_config():
        sys.exit(1)

    last_hash = None

    # Direct eerste upload bij opstarten
    log("Eerste upload...")
    try:
        upload_to_github(LOCAL_FILE)
        last_hash = file_hash(LOCAL_FILE)
    except Exception as e:
        log(f"Fout bij eerste upload: {e}")

    log("Watching voor wijzigingen...\n")

    while True:
        try:
            time.sleep(CHECK_INTERVAL)
            current_hash = file_hash(LOCAL_FILE)
            if current_hash != last_hash:
                log("Wijziging gedetecteerd — uploaden...")
                upload_to_github(LOCAL_FILE)
                last_hash = current_hash
            else:
                log("Geen wijzigingen.")

        except KeyboardInterrupt:
            print()
            log("Gestopt.")
            break
        except FileNotFoundError:
            log(f"Bestand niet gevonden: {LOCAL_FILE} — wachten...")
        except requests.exceptions.HTTPError as e:
            log(f"GitHub fout: {e}")
            if '401' in str(e):
                log("Token ongeldig of verlopen. Controleer GITHUB_TOKEN.")
                break
        except Exception as e:
            log(f"Onverwachte fout: {e}")
            log("Probeer opnieuw over 30 seconden...")
            time.sleep(30)


if __name__ == '__main__':
    run()
