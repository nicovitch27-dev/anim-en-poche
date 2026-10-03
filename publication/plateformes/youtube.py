"""YouTube Data API v3 : envoi reprenable + miniature personnalisée."""
import json
import os

import requests


def jeton():
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def publier(video, couverture, meta, config):
    tok = jeton()
    taille = os.path.getsize(video)
    corps = {
        "snippet": {
            "title": meta["titre"],
            "description": meta["description"],
            "categoryId": config["youtube_categorie"],
            "defaultLanguage": "fr",
            "defaultAudioLanguage": "fr",
        },
        "status": {"privacyStatus": config["youtube_confidentialite"], "selfDeclaredMadeForKids": False},
    }
    r = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(taille)},
        data=json.dumps(corps), timeout=60)
    r.raise_for_status()
    with open(video, "rb") as f:
        r = requests.put(r.headers["Location"], data=f,
                         headers={"Authorization": f"Bearer {tok}", "Content-Type": "video/mp4"}, timeout=1800)
    r.raise_for_status()
    vid = r.json()["id"]
    res = {"id": vid, "lien": f"https://youtu.be/{vid}"}
    if couverture:
        res["note"] = miniature(vid, couverture, tok)
    return res


def miniature(vid, image, tok=None):
    """Pose (ou remplace) la miniature d'une vidéo déjà en ligne."""
    with open(image, "rb") as f:
        t = requests.post(
            f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}&uploadType=media",
            headers={"Authorization": f"Bearer {tok or jeton()}", "Content-Type": "image/jpeg"}, data=f, timeout=120)
    return "(miniature ok)" if t.ok else f"(miniature refusée : {t.text[:150]})"
