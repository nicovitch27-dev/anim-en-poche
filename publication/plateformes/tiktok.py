"""TikTok Content Posting API : envoi en brouillon (boîte de réception de l'appli)."""
import os
import time

import requests

API = "https://open.tiktokapis.com/v2"


def jeton():
    # TikTok répond parfois vide (page d'erreur, limite de débit) : on réessaie avant d'abandonner.
    erreur = "?"
    for attente in (0, 30, 90, 180):
        time.sleep(attente)
        try:
            r = requests.post(f"{API}/oauth/token/", headers={"Cache-Control": "no-cache"}, data={
                "client_key": os.environ["TIKTOK_CLIENT_KEY"],
                "client_secret": os.environ["TIKTOK_CLIENT_SECRET"],
                "grant_type": "refresh_token",
                "refresh_token": os.environ["TIKTOK_REFRESH_TOKEN"],
            }, timeout=30)
        except requests.RequestException as e:
            erreur = f"connexion : {e.__class__.__name__}"
            print(f"Jeton TikTok, essai raté ({erreur})")
            continue
        try:
            d = r.json()
        except ValueError:
            erreur = f"HTTP {r.status_code}, réponse illisible « {r.text[:150]} »"
            print(f"Jeton TikTok, essai raté ({erreur})")
            continue
        if "access_token" in d:
            return d["access_token"], d.get("refresh_token") != os.environ["TIKTOK_REFRESH_TOKEN"]
        erreur = f"HTTP {r.status_code} : {d}"
        print(f"Jeton TikTok, essai raté ({erreur})")
        if d.get("error") in ("invalid_grant", "invalid_client"):
            break  # inutile d'insister : il faut reconnecter le compte
    raise RuntimeError(f"jeton TikTok refusé : {erreur}")


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


def publier_photos(urls, titre, description):
    """Carrousel photo en brouillon. TikTok va chercher les images lui-même : leurs adresses
    doivent commencer par un préfixe vérifié dans le portail développeur (ici le site GitHub Pages)."""
    tok, jeton_change = jeton()
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8"}
    r = requests.post(f"{API}/post/publish/content/init/", headers=h, json={
        "media_type": "PHOTO", "post_mode": "MEDIA_UPLOAD",
        "post_info": {"title": titre[:90], "description": description[:4000]},
        "source_info": {"source": "PULL_FROM_URL", "photo_images": urls, "photo_cover_index": 0}},
        timeout=60).json()
    if r.get("error", {}).get("code") != "ok":
        raise RuntimeError(f"init TikTok (photos) : {r.get('error')}")
    pid = r["data"]["publish_id"]
    statut = "?"
    for _ in range(30):
        time.sleep(10)
        s = requests.post(f"{API}/post/publish/status/fetch/", headers=h, json={"publish_id": pid}, timeout=30).json()
        statut = s.get("data", {}).get("status", "?")
        if statut in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE"):
            break
        if statut == "FAILED":
            raise RuntimeError(f"TikTok a refusé le carrousel : {s.get('data', {}).get('fail_reason')}")
    res = {"id": pid, "statut": statut, "jeton_change": jeton_change}
    return res
