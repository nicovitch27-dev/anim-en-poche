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


# ---------- playlists par famille de jeux et mise à jour des vidéos déjà en ligne ----------

API = "https://www.googleapis.com/youtube/v3"


def _toutes(url, params, tok):
    params = dict(params, maxResults=50)
    while True:
        r = requests.get(url, params=params, headers={"Authorization": f"Bearer {tok}"}, timeout=60)
        r.raise_for_status()
        j = r.json()
        yield from j.get("items", [])
        if not j.get("nextPageToken"):
            return
        params["pageToken"] = j["nextPageToken"]


_PLAYLISTS = {}


def playlist(titre, description, tok):
    """Identifiant de la playlist de ce titre sur la chaîne ; elle est créée (publique) si elle n'existe pas.
    Une playlist toute neuve met un moment à apparaître dans la liste : on garde son identifiant en mémoire."""
    if titre in _PLAYLISTS:
        return _PLAYLISTS[titre]
    _PLAYLISTS[titre] = _cherche_ou_cree(titre, description, tok)
    return _PLAYLISTS[titre]


def _cherche_ou_cree(titre, description, tok):
    for p in _toutes(f"{API}/playlists", {"part": "snippet", "mine": "true"}, tok):
        if p["snippet"]["title"] == titre:
            return p["id"]
    r = requests.post(f"{API}/playlists?part=snippet,status", headers={"Authorization": f"Bearer {tok}"}, json={
        "snippet": {"title": titre, "description": description, "defaultLanguage": "fr"},
        "status": {"privacyStatus": "public"}}, timeout=60)
    r.raise_for_status()
    return r.json()["id"]


def ajouter_a_playlist(vid, pid, tok):
    try:
        for it in _toutes(f"{API}/playlistItems", {"part": "contentDetails", "playlistId": pid}, tok):
            if it["contentDetails"]["videoId"] == vid:
                return False
    except requests.HTTPError as e:
        # playlist toute neuve : YouTube répond 404 tant qu'elle n'est pas visible, elle est encore vide
        if e.response is None or e.response.status_code != 404:
            raise
    r = requests.post(f"{API}/playlistItems?part=snippet", headers={"Authorization": f"Bearer {tok}"}, json={
        "snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}}, timeout=60)
    r.raise_for_status()
    return True


def modifier(vid, titre, description, tok):
    """Remplace le titre et la description d'une vidéo en ligne (catégorie et langue gardées)."""
    r = requests.get(f"{API}/videos", params={"part": "snippet", "id": vid},
                     headers={"Authorization": f"Bearer {tok}"}, timeout=60)
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        return False
    sn = items[0]["snippet"]
    corps = {"id": vid, "snippet": {"title": titre, "description": description, "categoryId": sn["categoryId"],
                                    "defaultLanguage": sn.get("defaultLanguage", "fr"),
                                    "defaultAudioLanguage": sn.get("defaultAudioLanguage", "fr"),
                                    **({"tags": sn["tags"]} if sn.get("tags") else {})}}
    r = requests.put(f"{API}/videos?part=snippet", headers={"Authorization": f"Bearer {tok}"}, json=corps, timeout=60)
    r.raise_for_status()
    return True
