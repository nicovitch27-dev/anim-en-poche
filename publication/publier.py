"""Publication quotidienne Anim en poche : 1 vidéo par jour sur toutes les plateformes.

Lancé par .github/workflows/publier.yml (cron) ou à la main :
    python publication/publier.py --essai            # n'envoie rien, montre ce qui serait publié
    python publication/publier.py --forcer ziggy-ziggy --ignorer-heure
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
from plateformes import discord, meta, pinterest, tiktok, youtube  # noqa: E402

CONFIG = json.loads((ICI / "config.json").read_text())
REGISTRE = ICI / "publications.json"
PARIS = ZoneInfo("Europe/Paris")


# ---------- registre anti-doublon ----------

def lire_registre():
    if REGISTRE.exists():
        return json.loads(REGISTRE.read_text())
    return {"publiees": {}}


def ecrire_registre(reg):
    REGISTRE.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n")


# ---------- catalogue des vidéos (lu sur GitHub, sans tout télécharger) ----------

FICHIER_RE = re.compile(r"^(?:(\d+) - )?(.+?) - (YOUTUBE|TIKTOK)\.mp4$")


def catalogue():
    url = f"https://api.github.com/repos/{CONFIG['depot']}/git/trees/{quote(CONFIG['branche_videos'], safe='')}?recursive=1"
    entetes = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        entetes["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    r = requests.get(url, headers=entetes, timeout=60)
    r.raise_for_status()
    racine = CONFIG["dossier_videos"].rstrip("/") + "/"
    videos = {}
    for e in r.json()["tree"]:
        if e["type"] != "blob" or not e["path"].startswith(racine):
            continue
        morceaux = e["path"][len(racine):].split("/")
        if len(morceaux) != 2:
            continue
        dossier, nom = morceaux
        m = FICHIER_RE.match(nom)
        if not m:
            continue
        num, titre, fmt = m.groups()
        v = videos.setdefault(dossier, {"dossier": dossier, "numero": num, "titre": titre.strip()})
        v[fmt.lower()] = {"chemin": e["path"], "taille": e["size"]}
    return videos


def ordre(videos):
    prio = CONFIG["prioritaires"]

    def cle(v):
        if v["dossier"] in prio:
            return (0, prio.index(v["dossier"]), "")
        if v["numero"]:
            return (1, int(v["numero"]), "")
        return (2, 0, v["dossier"])

    return sorted(videos.values(), key=cle)


def url_brute(chemin):
    return f"https://raw.githubusercontent.com/{CONFIG['depot']}/{CONFIG['branche_videos']}/{quote(chemin)}"


def telecharger(chemin, dest):
    url = url_brute(chemin)
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for bloc in r.iter_content(1 << 20):
                f.write(bloc)
    return dest


def couverture(video, dest):
    """Image exacte à la 2e seconde (00:00:02)."""
    s = CONFIG["seconde_couverture"]
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"00:00:{s:02d}", "-i", str(video),
         "-frames:v", "1", "-q:v", "2", str(dest)],
        check=True,
    )
    return dest


def duree(video):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
        check=True, capture_output=True, text=True,
    ).stdout
    return float(out.strip())


def metadonnees(titre):
    description = f"{titre}\n\n{CONFIG['accroche']}\n\n{CONFIG['hashtags']}"
    return {"titre": titre[:100], "description": description}


# ---------- programme principal ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--essai", action="store_true", help="ne publie rien")
    ap.add_argument("--forcer", help="dossier à publier (ex. ziggy-ziggy)")
    ap.add_argument("--ignorer-heure", action="store_true")
    ap.add_argument("--plateformes", help="limiter à certaines plateformes, ex. instagram,facebook")
    args = ap.parse_args()

    maintenant = datetime.now(PARIS)
    aujourdhui = maintenant.date().isoformat()
    reg = lire_registre()

    if not args.ignorer_heure and maintenant.hour not in CONFIG["heures_paris_autorisees"]:
        print(f"Il est {maintenant:%H:%M} à Paris : pas l'heure de publier.")
        return 0
    if not args.forcer and any(p.get("date") == aujourdhui for p in reg["publiees"].values()):
        print("Une vidéo a déjà été publiée aujourd'hui.")
        return 0

    videos = ordre(catalogue())
    if args.forcer:
        choix = next((v for v in videos if v["dossier"] == args.forcer), None)
        if not choix:
            print(f"Dossier introuvable : {args.forcer}")
            return 1
    else:
        choix = next((v for v in videos if v["dossier"] not in reg["publiees"]), None)
    restantes = sum(1 for v in videos if v["dossier"] not in reg["publiees"])
    if not choix:
        discord.envoyer("📭 **Anim en poche** : plus aucune vidéo à publier, ajoute-en dans le dépôt !")
        return 0

    meta_ = metadonnees(choix["titre"])
    print(f"Vidéo du jour : {choix['dossier']} — {meta_['titre']}  ({restantes} restantes)")
    print(meta_["description"])
    if args.essai:
        print("\nMode essai : rien n'est publié.")
        return 0

    resultats = {}
    pl = dict(CONFIG["plateformes"])
    if args.plateformes:
        voulues = {x.strip() for x in args.plateformes.split(",") if x.strip()}
        pl = {k: (v and k in voulues) for k, v in pl.items()}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        horiz = vert = None
        if "youtube" in choix:
            horiz = telecharger(choix["youtube"]["chemin"], tmp / "horizontal.mp4")
            couverture(horiz, tmp / "couverture_169.jpg")
        if "tiktok" in choix:
            vert = telecharger(choix["tiktok"]["chemin"], tmp / "vertical.mp4")
            couverture(vert, tmp / "couverture_916.jpg")
        cov_h = tmp / "couverture_169.jpg" if horiz else None
        cov_v = tmp / "couverture_916.jpg" if vert else None

        def lancer(nom, actif, fn, *a):
            if not actif:
                return
            if any(x is None for x in a[:1]):
                resultats[nom] = {"ok": False, "erreur": "fichier vidéo absent pour ce format"}
                return
            try:
                resultats[nom] = {"ok": True, **(fn(*a) or {})}
            except Exception as e:  # une plateforme en panne ne bloque pas les autres
                traceback.print_exc()
                resultats[nom] = {"ok": False, "erreur": str(e)[:400]}

        lancer("youtube", pl["youtube"], youtube.publier, horiz, cov_h, meta_, CONFIG)
        lancer("youtube_short", pl["youtube_short"], youtube.publier, vert, None, meta_, CONFIG)
        lancer("tiktok", pl["tiktok"], tiktok.publier, vert, meta_)
        lancer("instagram", pl["instagram"], meta.instagram, vert, meta_, CONFIG,
               url_brute(choix["tiktok"]["chemin"]) if vert else None)
        lancer("facebook", pl["facebook"], meta.facebook, vert, cov_v, duree(vert) if vert else 0, meta_, CONFIG)
        lancer("pinterest", pl["pinterest"], pinterest.publier, vert, meta_, CONFIG)

    reussites = [k for k, v in resultats.items() if v["ok"]]
    deja = choix["dossier"] in reg["publiees"]
    if reussites:
        entree = reg["publiees"].setdefault(choix["dossier"], {"date": aujourdhui, "titre": meta_["titre"], "resultats": {}})
        entree["resultats"].update(resultats)  # un rattrapage garde la date d'origine
        ecrire_registre(reg)

    lignes = [f"🎬 **{meta_['titre']}** (`{choix['dossier']}`) — {restantes - (1 if reussites and not deja else 0)} vidéos restantes"]
    for k, v in resultats.items():
        if v["ok"]:
            lignes.append(f"✅ {k} {v.get('lien', '')} {v.get('note', '')}".rstrip())
        else:
            lignes.append(f"❌ {k} : {v['erreur']}")
    if not reussites and not deja:
        lignes.append("⚠️ Rien n'a marché : la vidéo n'est pas consommée, elle sera retentée.")
    discord.envoyer("\n".join(lignes))
    for k, v in resultats.items():
        if v.get("a_faire"):
            discord.envoyer(v["a_faire"])

    return 0 if reussites else 1


if __name__ == "__main__":
    sys.exit(main())
