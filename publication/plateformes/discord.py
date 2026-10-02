import os

import requests


def envoyer(texte):
    url = os.environ.get("DISCORD_WEBHOOK")
    print(texte)
    if not url:
        return
    while texte:
        morceau, texte = texte[:1900], texte[1900:]
        requests.post(url, json={"content": morceau}, timeout=30)
