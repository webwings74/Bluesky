import requests
import argparse
import os
import importlib.util
import re
import mimetypes
from datetime import datetime, timezone
from PIL import Image

# Maximale afbeeldingsgrootte (aanpasbaar)
MAX_WIDTH = 2048
MAX_HEIGHT = 2048

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

# Upload een afbeelding naar Bluesky als een binaire upload
def upload_image_to_bluesky(access_token, image_path, debug=False):
    if not os.path.isfile(image_path):
        print(f"❌ Fout: Bestand '{image_path}' bestaat niet.")
        return None

    # Resize afbeelding als nodig
    image_path = resize_image(image_path, debug)

    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type or not mime_type.startswith("image/"):
        print(f"❌ Ongeldig afbeeldingsbestand '{image_path}'. MIME-type: {mime_type or 'None'}. Probeer een .jpg of .png bestand.")
        return None

    file_size = os.path.getsize(image_path)
    if debug:
        print(f"📂 Uploading afbeelding: {image_path} (MIME: {mime_type}, Grootte: {file_size} bytes)")

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
            if debug:
                print(f"📸 Geüploade afbeelding respons: {blob_data}")
            return blob_data
        else:
            print(f"❌ Fout bij uploaden van afbeelding: {upload_response.status_code}, {upload_response.text}")
            return None

# Post een bericht naar Bluesky
def post_to_bluesky(access_token, did, message=None, image_path=None, debug=False):
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

    if image_path:
        blob = upload_image_to_bluesky(access_token, image_path, debug)
        if blob:
            if debug:
                print(f"📸 Afbeelding succesvol geüpload! Blob: {blob}")

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
                        "alt": "Afbeelding geplaatst via script"
                    }
                ]
            }
        else:
            print("❌ Afbeelding werd niet correct geüpload.")

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
    parser.add_argument("-i", "--image", type=str, help="Pad naar afbeelding die geplaatst moet worden.")
    parser.add_argument("-d", "--debug", action="store_true", help="Schakel debug-modus in.")

    args = parser.parse_args()

    secrets = load_secrets()
    handle = secrets.get("handle")
    password = secrets.get("password")

    access_token, did = login_to_bluesky(handle, password, args.debug)
    if access_token and did:
        post_to_bluesky(access_token, did, message=args.message, image_path=args.image, debug=args.debug)
