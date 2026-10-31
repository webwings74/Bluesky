# Bluesky
A small project that lets you post a message to Bluesky using a **Python** program. This can be your own text message, optionally accompanied by images (up to a maximum of 4), which are automatically resized if they are too large. You can also post output to Bluesky via a **pipe**.

## Python program
The program ```post2bsky.py``` is a **Python** program with comments explaining how it works. It uses the following modules:
* **requests**
* **argparse** for reading the command-line arguments used by the program.
* **os**
* **importlib.util**
* **re**
* **mimetypes**
* **sys**
* **datetime** for the correct posting date/time.
* **Pillow** (PIL) for resizing images.

## Setup
1. Create and activate a virtual environment, then install the dependencies from ```requirements.txt```:
   ```bash
   python3 -m venv bluesky-env
   source bluesky-env/bin/activate
   pip install -r requirements.txt
   ```
   The ```bluesky-env/``` folder is ignored by git (```*-env/``` in ```.gitignore```). Activate the environment again with ```source bluesky-env/bin/activate``` whenever you want to use the program.
2. Copy the template config file: ```cp config.py myconfig.py```
3. Edit ```myconfig.py``` and fill in your Bluesky handle and an app password (create one under *Settings → Privacy and security → App passwords* on Bluesky).

```myconfig.py``` is listed in ```.gitignore```, so your credentials will not be committed.

## Usage
* Post a text message only: ```python post2bsky.py -m "This is a message on Bluesky"```
* Post an image: ```python post2bsky.py -i "path-to-image.jpg"```
* To post multiple images, separate the paths with a comma: ```-i "image1.jpeg,image2.png"``` etc.
* Post the output of a terminal command, for example the contents of config.py: ```more config.py | python post2bsky.py```
