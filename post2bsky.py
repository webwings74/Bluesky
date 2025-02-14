import requests
import argparse
import os
import importlib.util
import re
import mimetypes
import sys
from datetime import datetime, timezone
from PIL import Image

# Bestandsnaam voor de Bluesky Handle/password
blueskyconfig = "config-webwings.py"

# Maximale afbeeldingsgrootte (aanpasbaar)
MAX_WIDTH = 2048
MAX_HEIGHT = 2048
MAX_IMAGES = 4  # Bluesky ondersteunt maximaal 4 afbeeldingen per post

# Probeer de credentials te laden als het bestaat
def load_secrets():
    secrets = {}
    secrets_path = blueskyconfig
    if os.path.exists(secrets_path):
        spec = importlib.util.spec_from_file_location("myconfig", secrets_path)
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

# 📸 Resize afbeelding als deze groter is dan MAX_WIDTH x MAX_HEIGHT
def resize_image(image_path, debug=False):
    with Image.open(image_path) as img:
        width, height = img.size

        if width > MAX_WIDTH or height > MAX_HEIGHT:
            img.thumbnail((MAX_WIDTH, MAX_HEIGHT))  # Behoudt aspect ratio
            resized_path = f"{image_path}_resized.jpg"
            img.save(resized_path, "JPEG", quality=85)  # Compressie toepassen
            if debug:
                print(f"📏 Afbeelding resized: {image_path} -> {resized_path} ({img.size[0]}x{img.size[1]})")
            return resized_path
        else:
            if debug:
                print(f"✅ Afbeelding is al binnen limiet: {width}x{height}, resizing niet nodig.")
            return image_path  # Gebruik originele afbeelding als deze al klein genoeg is

# Upload meerdere afbeeldingen naar Bluesky
def upload_images_to_bluesky(access_token, image_paths, debug=False):
    blobs = []
    for index, image_path in enumerate(image_paths[:MAX_IMAGES]):  # Max 4 afbeeldingen
        if not os.path.isfile(image_path):
            print(f"❌ Fout: Bestand '{image_path}' bestaat niet.")
            continue

        image_path = resize_image(image_path, debug)

        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type or not mime_type.startswith("image/"):
            print(f"❌ Ongeldig afbeeldingsbestand '{image_path}'. MIME-type: {mime_type or 'None'}. Probeer een .jpg of .png bestand.")
            continue

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": mime_type
        }

        upload_url = "https://bsky.social/xrpc/com.atproto.repo.uploadBlob"

        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
            upload_response = requests.post(upload_url, headers=headers, data=image_data)

            if debug:
                print(f"🔍 Debug: Upload respons {upload_response.status_code} - {upload_response.text}")

            if upload_response.status_code == 200:
                blob_data = upload_response.json()
                blobs.append(blob_data)
                if debug:
                    print(f"📸 Geüploade afbeelding {index+1}: {blob_data}")

    return blobs

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
            facet_data = {"$type": facet_type, "tag": match_text[1:]}  # Hashtag zonder '#'
            if debug:
                print(f"🔍 Debug: Herkende hashtag {match_text}")
        
        elif match_text.startswith("@"):
            facet_type = "app.bsky.richtext.facet#mention"
            did = get_did_for_handle(match_text[1:], debug)  # Haal DID op van de gebruiker
            
            if did:
                facet_data = {"$type": facet_type, "did": did}
                if debug:
                    print(f"🔍 Debug: Mention {match_text} gekoppeld aan DID {did}")
            else:
                if debug:
                    print(f"⚠️ Debug: Kon DID niet ophalen voor mention {match_text}, wordt overgeslagen.")
                continue  # Sla over als we geen DID kunnen ophalen

        else:
            continue  # Sla over als het geen hashtag of mention is

        facets.append({
            "index": {"byteStart": start, "byteEnd": end},
            "features": [facet_data]
        })

    return facets if facets else None

# Post een bericht naar Bluesky
def post_to_bluesky(access_token, did, message=None, image_paths=None, debug=False):
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

    if image_paths:
        blobs = upload_images_to_bluesky(access_token, image_paths, debug)
        if blobs:
            data["record"]["embed"] = {
                "$type": "app.bsky.embed.images",
                "images": [
                    {
                        "image": {
                            "$type": "blob",
                            "ref": blob["blob"]["ref"], 
                            "mimeType": blob["blob"]["mimeType"], 
                            "size": blob["blob"]["size"]
                        },
                        "alt": f"Afbeelding {idx+1} geplaatst via script"
                    } for idx, blob in enumerate(blobs)
                ]
            }

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
    parser.add_argument("-i", "--images", type=str, help="Pad naar afbeeldingen, gescheiden door komma.")
    parser.add_argument("-d", "--debug", action="store_true", help="Schakel debug-modus in.")

    args = parser.parse_args()

    if not sys.stdin.isatty():
        piped_text = sys.stdin.read().strip()
    else:
        piped_text = None

    message_text = args.message if args.message else piped_text

    if not message_text:
        print("❌ Fout: Er is geen bericht opgegeven. Gebruik -m of een pipe-invoer.")
        sys.exit(1)

    secrets = load_secrets()
    access_token, did = login_to_bluesky(secrets.get("handle"), secrets.get("password"), args.debug)

    image_paths = args.images.split(",") if args.images else []
    post_to_bluesky(access_token, did, message=message_text, image_paths=image_paths, debug=args.debug)
