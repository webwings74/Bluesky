# Bluesky
Een klein project, waarbij je via een **Python** programma een bericht kunt plaatsen op Bluesky. Dit kan een eigen tekstbericht zijn, en kan eventueel voorzien worden van afbeeldingen (tot een max van 4) die automatisch van formaat worden gewijzigd als deze te groot zouden zijn. Ook kun je via een **pipe** uitvoer op Bluesky plaatsen.

## Python programma
Het programma ```post2bsky.py``` is een **Python** programma, dat voorzien is van commentaar waar je de werking uit kunt halen. Het maakt gebruik van de volgende modules:
* **requests**
* **argparse** voor het lezen van de argumenten voor gebruik in het programma.
* **os**
* **importlib.util**
* **re**
* **mimetypes**
* **sys**
* **datetime** voor de correcte plaatsings datum/tijd.
* **Pillow** (PIL) voor het verkleinen van afbeeldingen. 

## Gebruik
* Plaatsen van alleen een tekstbericht: ```python post2bsky.py -m "Dit is een bericht op Bluesky"```
* Plaatsen van een afbeelding: ```python post2bsky.py -i "pad-naar-afbeelding.jpg"```
* Voor het plaatsen van meerdere afbeeldingen dienen de paden gescheiden te zijn met een komma: ```-i "afbeelding1.jpeg,afbeelding2.png"``` etc.
* Uitvoer van een terminal commando, bijvoorbeeld de inhoud van config.py: ```more config.py | python post2bsky.py```
