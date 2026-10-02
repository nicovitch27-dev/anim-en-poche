"""Instagram Reels + Facebook (Reel si ≤ 90 s, sinon vidéo classique) via l'API Graph."""
import os
import time

import requests


def _h():
    return {"Authorization": f"OAuth {os.environ['META_PAGE_TOKEN']}"}


def _verif(r, etape):
    d = r.json()
    if not r.ok or "error" in d:
        raise RuntimeError(f"{etape} : {d.get('error', d)}")
    return d


def instagram(video, meta, config):
    g = f"https://graph.facebook.com/{config['graph_version']}"
    taille = os.path.getsize(video)
    c = _verif(requests.post(f"{g}/{config['ig_user_id']}/media", headers=_h(), data={
        "media_type": "REELS", "upload_type": "resumable", "share_to_feed": "true",
        "caption": meta["description"],
        "thumb_offset": str(config["seconde_couverture"] * 1000),  # couverture = image à 2 s
    }, timeout=60), "création conteneur IG")
    with open(video, "rb") as f:
        _verif(requests.post(f"https://rupload.facebook.com/ig-api-upload/{config['graph_version']}/{c['id']}",
                             headers={**_h(), "offset": "0", "file_size": str(taille)}, data=f, timeout=900),
               "envoi IG")
    for _ in range(40):
        time.sleep(15)
        s = _verif(requests.get(f"{g}/{c['id']}", headers=_h(), params={"fields": "status_code,status"}, timeout=30),
                   "statut IG")
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram a refusé la vidéo : {s.get('status')}")
    p = _verif(requests.post(f"{g}/{config['ig_user_id']}/media_publish", headers=_h(),
                             data={"creation_id": c["id"]}, timeout=60), "publication IG")
    return {"id": p["id"]}


def facebook(video, couverture, duree, meta, config):
    page, v = config["fb_page_id"], config["graph_version"]
    texte = meta["description"]
    if duree > 90:
        with open(video, "rb") as f, open(couverture, "rb") as c:
            d = _verif(requests.post(f"https://graph-video.facebook.com/{v}/{page}/videos", headers=_h(),
                                     data={"title": meta["titre"], "description": texte},
                                     files={"source": ("video.mp4", f, "video/mp4"),
                                            "thumb": ("couverture.jpg", c, "image/jpeg")}, timeout=1800),
                       "vidéo FB")
        return {"id": d["id"], "lien": f"https://www.facebook.com/{d['id']}", "note": "(vidéo > 90 s : publiée hors Reels)"}

    g = f"https://graph.facebook.com/{v}"
    s = _verif(requests.post(f"{g}/{page}/video_reels", headers=_h(), data={"upload_phase": "start"}, timeout=60),
               "début Reel FB")
    with open(video, "rb") as f:
        _verif(requests.post(s["upload_url"], headers={**_h(), "offset": "0", "file_size": str(os.path.getsize(video))},
                             data=f, timeout=900), "envoi Reel FB")
    _verif(requests.post(f"{g}/{page}/video_reels", headers=_h(), data={
        "upload_phase": "finish", "video_id": s["video_id"], "video_state": "PUBLISHED",
        "title": meta["titre"], "description": texte}, timeout=60), "fin Reel FB")
    note = ""
    if couverture:
        time.sleep(30)
        with open(couverture, "rb") as c:
            t = requests.post(f"{g}/{s['video_id']}/thumbnails", headers=_h(), data={"is_preferred": "true"},
                              files={"source": ("couverture.jpg", c, "image/jpeg")}, timeout=120)
        note = "(couverture ok)" if t.ok else "(couverture auto)"
    return {"id": s["video_id"], "lien": f"https://www.facebook.com/reel/{s['video_id']}", "note": note}
