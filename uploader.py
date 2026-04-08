"""
SEP Toernooi – Automatische uploader

=====================================

Dit script draait op de achtergrond tijdens het toernooi.

Het haalt elke minuut het Excel-bestand op van OneDrive

en uploadt het naar GitHub zodat de website live standen toont.



INSTALLATIE (eenmalig):

  pip install requests msal watchdog



GEBRUIK:

  1. Vul hieronder je gegevens in (sectie CONFIGURATIE)

  2. Dubbelklik op dit bestand, of open een terminal en typ:

       python uploader.py

  3. Eerste keer: er opent een browser om in te loggen bij Microsoft

  4. Daarna draait het script automatisch op de achtergrond



Stop het script met Ctrl+C

"""



import os

import sys

import time

import base64

import hashlib

import requests

import threading

from datetime import datetime



# ════════════════════════════════════════════════

#  CONFIGURATIE — vul hier jouw gegevens in

# ════════════════════════════════════════════════



# Microsoft Azure (zelfde app als voorheen, of maak een nieuwe)

CLIENT_ID   = ''       # Azure App Client ID

TENANT_ID   = ''                     # of jouw specifieke Tenant ID

# 4x4_test
#CLIENT_ID   = 'c3'       # Azure App Client ID

TENANT_ID   = '18 e4'                     # of jouw specifieke Tenant ID

# 4x4MSGRAPH
#CLIENT_ID   = '535aca74 616'       # Azure App Client ID

TENANT_ID   = '18842 c41e4'                     # of jouw specifieke Tenant ID



# Bestandsnaam op OneDrive (zoals het gedeeld is met jou, vorheen Master.XLSM nu met xslm?)

ONEDRIVE_FILENAME = 'Master.xlsm' #  Dit wordt NIET gebruikt, verander de sharepoint link als je een ander bestand wil gebuiken !!

SHAREPOINT_LINK = "https://vvsep-my.sharepoint.com/:x:/r/personal/sander_tetteroo_vvsep_nl/Documents/SEP_Uitslagen/Master.XLSM?d=wa83105de47ff4745b4156a7b060258ed&csf=1&web=1&e=H4iQXa"


# GitHub

GITHUB_TOKEN = 'ghp_M O6xT'   # Personal Access Token (zie uitleg hieronder)

GITHUB_REPO  = 'SEP-4x4-Schoolvoetbaltoernooi/4x4website_Sep'

GITHUB_BRANCH = 'main'

GITHUB_FILE_PATH = 'Master.XLSM'          # Pad in de repo waar het bestand komt



# Hoe vaak controleren (in seconden)

CHECK_INTERVAL = 120



# ════════════════════════════════════════════════



TOKEN_CACHE_FILE = '.sep_token_cache.json'

access_token = None

last_hash = None





def log(msg):

    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def encode_sharepoint_link(url: str) -> str:
    encoded = base64.b64encode(url.encode('utf-8')).decode('utf-8')
    encoded = encoded.replace('/', '_').replace('+', '-').rstrip('=')
    return encoded

encoded_share_id = encode_sharepoint_link(SHAREPOINT_LINK)

# ── MICROSOFT LOGIN ──

def get_access_token():

    global access_token

    try:

        from msal import PublicClientApplication, SerializableTokenCache

    except ImportError:

        print("Installeer eerst: pip install msal")

        sys.exit(1)



    cache = SerializableTokenCache()

    if os.path.exists(TOKEN_CACHE_FILE):

        cache.deserialize(open(TOKEN_CACHE_FILE).read())



    app = PublicClientApplication(

        CLIENT_ID,

        authority=f'https://login.microsoftonline.com/{TENANT_ID}',

        token_cache=cache,
    )



    scopes =  ['https://graph.microsoft.com/Files.Read.All']

    accounts = app.get_accounts()

    result = None



    if accounts:

        result = app.acquire_token_silent(scopes, account=accounts[0])

    

    if not result:

        log("Eerste keer inloggen — browser wordt geopend...")

        # Haal de redirect_uri hier weer weg:

        result = app.acquire_token_interactive(
            scopes,
        )

    if 'access_token' not in result:

        print(f"Inloggen mislukt: {result.get('error_description', 'onbekende fout')}")

        sys.exit(1)


    # Sla token cache op zodat volgende keer niet opnieuw hoeft in te loggen

    if cache.has_state_changed:

        open(TOKEN_CACHE_FILE, 'w').write(cache.serialize())



    access_token = result['access_token']

    log("Ingelogd bij Microsoft ✓")

    return access_token





def refresh_token_if_needed():

    """Vernieuw token voor het verloopt (elke ~50 minuten)"""

    get_access_token()





# ── ONEDRIVE ──

def fetch_from_onedrive():

    global access_token

    headers = {'Authorization': f'Bearer {access_token}'}



    # Zoek bestand in "Gedeeld met mij"

    resp = requests.get(

        #'https://graph.microsoft.com/v1.0/me/drive/sharedWithMe?$top=100',
        f'https://graph.microsoft.com/v1.0/shares/u!{encoded_share_id}/driveItem',

        headers=headers

    )

    if resp.status_code == 401:

        log("Token verlopen, opnieuw inloggen...")

        get_access_token()

        headers = {'Authorization': f'Bearer {access_token}'}

        resp = requests.get(

            f'https://graph.microsoft.com/v1.0/shares/u!{encoded_share_id}/driveItem',

            headers=headers

        )



    resp.raise_for_status()

    resp_json = resp.json()




    drive_id = resp_json['parentReference']['driveId']

    item_id  = resp_json['id']



    # Download bestandsinhoud

    download_resp = requests.get(

        f'https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/content',

        headers=headers,

        allow_redirects=True

    )

    download_resp.raise_for_status()

    return download_resp.content





# ── GITHUB ──

def get_github_file_sha():

    """Haal de huidige SHA op van het bestand op GitHub (nodig voor update)"""

    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}'

    resp = requests.get(url, headers={

        'Authorization': f'token {GITHUB_TOKEN}',

        'Accept': 'application/vnd.github.v3+json'

    }, params={'ref': GITHUB_BRANCH})

    if resp.status_code == 200:

        return resp.json().get('sha')

    return None





def upload_to_github(content_bytes):

    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}'

    sha = get_github_file_sha()



    body = {

        'message': f'Auto-update {datetime.now().strftime("%H:%M:%S")}',

        'content': base64.b64encode(content_bytes).decode('utf-8'),

        'branch':  GITHUB_BRANCH,

    }

    if sha:

        body['sha'] = sha  # vereist voor update van bestaand bestand



    resp = requests.put(url, json=body, headers={

        'Authorization': f'token {GITHUB_TOKEN}',

        'Accept': 'application/vnd.github.v3+json'

    })

    resp.raise_for_status()

    log(f"Geüpload naar GitHub ✓ ({len(content_bytes)//1024} KB)")





# ── HOOFDLUS ──

def run():

    global last_hash



    log("SEP Toernooi Uploader gestart")

    log(f"Controleert elke {CHECK_INTERVAL} seconden op wijzigingen")

    log("Druk op Ctrl+C om te stoppen\n")



    # Validatie

    if CLIENT_ID == 'JOUW_CLIENT_ID_HIER':

        print("⚠️  Vul eerst je CLIENT_ID in bovenaan dit bestand!")

        sys.exit(1)

    if GITHUB_TOKEN == 'JOUW_GITHUB_TOKEN_HIER':

        print("⚠️  Vul eerst je GITHUB_TOKEN in bovenaan dit bestand!")

        print("\nGitHub token aanmaken:")

        print("  1. Ga naar github.com → Settings → Developer settings")

        print("  2. Personal access tokens → Tokens (classic) → Generate new token")

        print("  3. Geef het een naam, stel 'repo' scope in, klik Generate")

        print("  4. Kopieer het token en plak het hierboven bij GITHUB_TOKEN\n")

        sys.exit(1)



    # Eerste keer inloggen

    get_access_token()



    while True:

        try:

            log("Bestand ophalen van OneDrive...")

            content = fetch_from_onedrive()
            print(content)



            # Controleer of het bestand gewijzigd is

            file_hash = hashlib.md5(content).hexdigest()

            if file_hash == last_hash:

                log("Geen wijzigingen gevonden, wachten...")

            else:

                log("Wijziging gedetecteerd! Uploaden naar GitHub...")

                upload_to_github(content)

                last_hash = file_hash



        except KeyboardInterrupt:

            log("Gestopt.")

            break

        except Exception as e:

            log(f"Fout: {e}")

            log("Probeer het opnieuw over 120 seconden...")



        time.sleep(CHECK_INTERVAL)





if __name__ == '__main__':

    run()