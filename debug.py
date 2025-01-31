import mimetypes

image_path = "IMG_6731.jpeg"
mime_type, _ = mimetypes.guess_type(image_path)

print(f"Bestand: {image_path}")
print(f"Herkenbaar MIME-type: {mime_type}")
