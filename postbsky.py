import requests
import argparse
import os
import importlib.util
import re
import mimetypes
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
def login_to_bluesky(handle, password, debug=False):
    login_url = "https://bsky.social/xrpc/com.atproto.server.createSession"
    payload = {"identifier": handle, "password": password}
    response = requests.post(login_url, json=payload)

    if debug:
        print(f"🔍 Debug: Login respons {response.status_code} - {response.text}")

    if response.status_code == 200:
        data = response.json()
        return data.get("accessJwt"), data.get("did")
    else:
        print(f"❌ Fout bij inloggen: {response.status_code}, {response.text}")
        return None, None

# Haal de DID op van een gebruiker (mention)
def get_did_for_handle(handle, debug=False):
    if "." not in handle:
        handle += ".bsky.social"

    lookup_url = f"https://bsky.social/xrpc/com.atproto.identity.resolveHandle?handle={handle}"
    response = requests.get(lookup_url)

    if debug:
        print(f"🔍 Debug: DID ophalen voor {handle} - Status: {response.status_code}")

    if response.status_code == 200:
        return response.json().get("did")
    else:
        print(f"⚠️ Waarschuwing: Kon DID niet ophalen voor {handle}. API status: {response.status_code}")
        return None

# Hashtags en mentions parseren voor Bluesky
def parse_hashtags_and_mentions(text, debug=False):
    facets = []

    if not text:
        return None

    for match in re.finditer(r"(@[\w.-]+|#[\w]+)", text):
        match_text = match.group(0)
        start, end = match.span()

        if match_text.startswith("#"):
            facet_type = "app.bsky.richtext.facet#tag"
            facet_data = {"$type": facet_type, "tag": match_text[1:]}  
            if debug:
                print(f"🔍 Debug: Herkende hashtag {match_text}")
        
        elif match_text.startswith("@"):
            facet_type = "app.bsky.richtext.facet#mention"
            did = get_did_for_handle(match_text[1:], debug)  
            
            if did:
                facet_data = {"$type": facet_type, "did": did}
                if debug:
                    print(f"🔍 Debug: Mention {match_text} gekoppeld aan DID {did}")
            else:
                if debug:
                    print(f"⚠️ Debug: Kon DID niet ophalen voor mention {match_text}, wordt overgeslagen.")
                continue  

        else:
            continue  

        facets.append({
            "index": {"byteStart": start, "byteEnd": end},
            "features": [facet_data]
        })

    return facets if facets else None

# Post een bericht naar Bluesky
def post_to_bluesky(access_token, did, message=None, debug=False):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    api_post_url = "https://bsky.social/xrpc/com.atproto.repo.createRecord"

    current_time = datetime.now(timezone.utc).isoformat()

    data = {
        "repo": did,
        "collection": "app.bsky.feed.post",
        "record": {
            "text": message or "",
            "createdAt": current_time
        }
    }

    facets = parse_hashtags_and_mentions(message, debug)
    if facets:
        data["record"]["facets"] = facets

    if debug:
        print(f"📸 Debug: Volledige API-payload: {data}")

    response = requests.post(api_post_url, headers=headers, json=data)

    if debug:
        print(f"🔍 Debug: Post respons {response.status_code} - {response.text}")

    if response.status_code == 200:
        print("✅ Bericht succesvol geplaatst op Bluesky!")
    else:
        print(f"❌ Fout bij plaatsen van bericht: {response.status_code}, {response.text}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plaats een bericht op Bluesky.")
    parser.add_argument("-m", "--message", type=str, help="Tekstbericht dat geplaatst moet worden.")
    parser.add_argument("-d", "--debug", action="store_true", help="Schakel debug-modus in.")

    args = parser.parse_args()

    secrets = load_secrets()
    handle = secrets.get("handle")
    password = secrets.get("password")

    access_token, did = login_to_bluesky(handle, password, args.debug)
    if access_token and did:
        post_to_bluesky(access_token, did, message=args.message, debug=args.debug)
