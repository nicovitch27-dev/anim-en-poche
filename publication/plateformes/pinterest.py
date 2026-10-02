"""Pinterest API v5 : Épingle vidéo (si l'accès API est accordé), sinon kit manuel sur Discord."""
import os
import time

import requests

API = "https://api.pinterest.com/v5"


def publier(video, meta, config):
    tok, board = os.environ.get("PINTEREST_TOKEN"), config.get("pinterest_board_id")
    if not tok or not board:
        return {"note": "(manuel : kit envoyé sur Discord)", "a_faire": (
            f"📌 **Pinterest** (à poster à la main) :\n**Titre** : {meta['titre']}\n"
            f"**Lien** : {config['lien_site']}\n**Description** :\n```\n{meta['description']}\n```")}
    h = {"Authorization": f"Bearer {tok}"}
    m = requests.post(f"{API}/media", headers=h, json={"media_type": "video"}, timeout=60)
    m.raise_for_status()
    m = m.json()
    with open(video, "rb") as f:
        u = requests.post(m["upload_url"], data=m["upload_parameters"], files={"file": f}, timeout=900)
    u.raise_for_status()
    for _ in range(40):
        time.sleep(10)
        etat = requests.get(f"{API}/media/{m['media_id']}", headers=h, timeout=30).json().get("status")
        if etat == "succeeded":
            break
        if etat == "failed":
            raise RuntimeError("Pinterest n'a pas pu traiter la vidéo")
    p = requests.post(f"{API}/pins", headers=h, timeout=60, json={
        "board_id": board, "title": meta["titre"], "description": meta["description"][:500],
        "link": config["lien_site"], "alt_text": f"Règles du jeu {meta['titre']} expliquées en vidéo",
        "media_source": {"source_type": "video_id", "media_id": m["media_id"],
                         "cover_image_key_frame_time": config["seconde_couverture"]}})
    if not p.ok:
        raise RuntimeError(f"Épingle refusée : {p.text[:300]}")
    return {"id": p.json()["id"], "lien": f"https://pinterest.com/pin/{p.json()['id']}"}
