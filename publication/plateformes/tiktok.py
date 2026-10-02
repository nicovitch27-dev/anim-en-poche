"""TikTok Content Posting API : envoi en brouillon (boîte de réception de l'appli)."""
import os
import time

import requests

API = "https://open.tiktokapis.com/v2"


def jeton():
    r = requests.post(f"{API}/oauth/token/", data={
        "client_key": os.environ["TIKTOK_CLIENT_KEY"],
        "client_secret": os.environ["TIKTOK_CLIENT_SECRET"],
        "grant_type": "refresh_token",
        "refresh_token": os.environ["TIKTOK_REFRESH_TOKEN"],
    }, timeout=30)
    d = r.json()
    if "access_token" not in d:
        raise RuntimeError(f"jeton TikTok refusé : {d}")
    return d["access_token"], d.get("refresh_token") != os.environ["TIKTOK_REFRESH_TOKEN"]


def publier(video, meta):
    tok, jeton_change = jeton()
    taille = os.path.getsize(video)
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8"}
    r = requests.post(f"{API}/post/publish/inbox/video/init/", headers=h, json={
        "source_info": {"source": "FILE_UPLOAD", "video_size": taille,
                        "chunk_size": taille, "total_chunk_count": 1}}, timeout=60).json()
    if r.get("error", {}).get("code") != "ok":
        raise RuntimeError(f"init TikTok : {r.get('error')}")
    pid, url = r["data"]["publish_id"], r["data"]["upload_url"]
    with open(video, "rb") as f:
        u = requests.put(url, data=f, timeout=900, headers={
            "Content-Type": "video/mp4", "Content-Length": str(taille),
            "Content-Range": f"bytes 0-{taille - 1}/{taille}"})
    u.raise_for_status()
    statut = "?"
    for _ in range(30):
        time.sleep(10)
        s = requests.post(f"{API}/post/publish/status/fetch/", headers=h, json={"publish_id": pid}, timeout=30).json()
        statut = s.get("data", {}).get("status", "?")
        if statut in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE"):
            break
        if statut == "FAILED":
            raise RuntimeError(f"TikTok a refusé la vidéo : {s.get('data', {}).get('fail_reason')}")
    res = {"id": pid, "note": "(brouillon envoyé dans l'appli)" if statut == "SEND_TO_USER_INBOX" else f"(statut {statut})"}
    a_faire = [f"📱 **TikTok** : ouvre l'appli → notification « brouillon » → colle la légende puis Publier :\n```\n{meta['description']}\n```"]
    if jeton_change:
        a_faire.append("⚠️ TikTok a renvoyé un nouveau jeton : relance `outils/envoyer_secrets.py` sur le Mac.")
    res["a_faire"] = "\n".join(a_faire)
    return res
