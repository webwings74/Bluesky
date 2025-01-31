import requests
import argparse
import os
import importlib.util
import re
from datetime import datetime, timezone

# Probeer secrets.py te laden als het bestaat
def load_secrets():
    secrets = {}
    secrets_path = "secrets.py"
    if os.path.exists(secrets_path):
        spec = importlib.util.spec_from_file_location("secrets", secrets_path)
        secrets_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(secrets_module)
        secrets["handle"] = getattr(secrets_module, "BLUESKY_HANDLE", None)
        secrets["password"] = getattr(secrets_module, "BLUESKY_PASSWORD", None)
    return secrets

# Login bij Bluesky om een toegangstoken en DID te krijgen
def login_to_bluesky(handle, password):
    login_url = "https://bsky.social/xrpc/com.atproto.server.createSession"
    payload = {"identifier": handle, "password": password}
    response = requests.post(login_url, json=payload)

    if response.status_code == 200:
        data = response.json()
        return data.get("accessJwt"), data.get("did")
    else:
        print(f"❌ Fout bij inloggen: {response.status_code}, {response.text}")
        return None, None

# Haal de DID op van een gebruiker (mention)
def get_did_for_handle(handle):
    # Voeg ".bsky.social" toe als het er niet is
    if "." not in handle:
        handle += ".bsky.social"

    lookup_url = f"https://bsky.social/xrpc/com.atproto.identity.resolveHandle?handle={handle}"
    response = requests.get(lookup_url)

    if response.status_code == 200:
        return response.json().get("did")
    else:
        print(f"⚠️ Waarschuwing: Kon DID niet ophalen voor {handle}. API status: {response.status_code}")
        return None

# Hashtags en mentions parseren voor Bluesky
def parse_hashtags_and_mentions(text):
    facets = []
    matches = []

    # Zoek hashtags en mentions
    for match in re.finditer(r"(@[\w.-]+|#[\w]+)", text):
        match_text = match.group(0)
        start, end = match.span()

        if match_text.startswith("#"):
            facet_type = "app.bsky.richtext.facet#tag"
            facet_data = {"$type": facet_type, "tag": match_text[1:]}  # Hashtags zonder '#'
        elif match_text.startswith("@"):
            facet_type = "app.bsky.richtext.facet#mention"
            did = get_did_for_handle(match_text[1:])  # Haal DID op van de gebruiker
            if did:
                facet_data = {"$type": facet_type, "did": did}
            else:
                continue  # Sla over als we geen DID kunnen ophalen
        else:
            continue

        facets.append({
            "index": {"byteStart": start, "byteEnd": end},
            "features": [facet_data]
        })

    return facets if facets else None

# Post een bericht en/of afbeelding naar Bluesky
def post_to_bluesky(access_token, did, message=None, image_path=None):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    api_post_url = "https://bsky.social/xrpc/com.atproto.repo.createRecord"

    # ✅ Gebruik de juiste UTC-tijd
    current_time = datetime.now(timezone.utc).isoformat()

    # Maak de JSON-payload voor het bericht
    data = {
        "repo": did,
        "collection": "app.bsky.feed.post",
        "record": {
            "text": message or "",
            "createdAt": current_time
        }
    }

    # ✅ Voeg hashtags en mentions toe als 'facets'
    facets = parse_hashtags_and_mentions(message) if message else None
    if facets:
        data["record"]["facets"] = facets

    # Upload afbeelding als deze opgegeven is
    if image_path:
        if not os.path.isfile(image_path):
            print(f"❌ Fout: Bestand '{image_path}' bestaat niet.")
            return
        with open(image_path, 'rb') as image_file:
            upload_url = "https://bsky.social/xrpc/com.atproto.repo.uploadBlob"
            files = {"file": image_file}
            upload_response = requests.post(upload_url, headers={"Authorization": f"Bearer {access_token}"}, files=files)

            if upload_response.status_code == 200:
                blob = upload_response.json().get("blob")
                data["record"]["embed"] = {
                    "$type": "app.bsky.embed.images",
                    "images": [
                        {
                            "image": blob,
                            "alt": "Afbeelding geplaatst via script"
                        }
                    ]
                }
            else:
                print(f"❌ Fout bij uploaden van afbeelding: {upload_response.status_code}, {upload_response.text}")
                return

    # Plaats het bericht op Bluesky
    response = requests.post(api_post_url, headers=headers, json=data)
    if response.status_code == 200:
        print("✅ Bericht succesvol geplaatst op Bluesky!")
    else:
        print(f"❌ Fout bij plaatsen van bericht: {response.status_code}, {response.text}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plaats een bericht en/of afbeelding op Bluesky.")
    parser.add_argument("-m", "--message", type=str, help="Tekstbericht dat geplaatst moet worden.")
    parser.add_argument("-i", "--image", type=str, help="Pad naar afbeelding die geplaatst moet worden.")
    parser.add_argument("--handle", type=str, help="Bluesky gebruikersnaam (handle).")
    parser.add_argument("--password", type=str, help="Bluesky wachtwoord.")

    args = parser.parse_args()

    # Inloggegevens ophalen uit command line of secrets.py
    secrets = load_secrets()
    handle = args.handle if args.handle else secrets.get("handle")
    password = args.password if args.password else secrets.get("password")

    if not handle or not password:
        print("❌ Fout: Handle en wachtwoord zijn vereist. Voeg ze toe via de command line of in secrets.py.")
        exit(1)

    # Login om toegangstoken en DID te verkrijgen
    access_token, did = login_to_bluesky(handle=handle, password=password)
    if access_token and did:
        post_to_bluesky(access_token=access_token, did=did, message=args.message, image_path=args.image)
