"""Carrousel TikTok du jour : envoie en brouillon le prochain dossier de carrousels/ pas encore publié.

Chaque dossier contient les diapos (01-….jpg, 02-….jpg, … dans l'ordre) et infos.json :
    {"titre": "…", "description": "légende + hashtags", "son": "mot à chercher dans les sons TikTok"}
Les images sont servies par GitHub Pages (préfixe vérifié chez TikTok). L'API ne permet pas de
choisir la musique d'un brouillon : la notification Discord rappelle quel son ajouter.

    python publication/publier_carrousel.py --essai
    python publication/publier_carrousel.py --ignorer-heure [--forcer 02-halloween-2]
"""
import argparse
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
from plateformes import discord, tiktok  # noqa: E402
from publier import CONFIG, PARIS, ecrire_registre, lire_registre  # noqa: E402

DOSSIER = ICI.parent / "carrousels"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--essai", action="store_true", help="ne publie rien")
    ap.add_argument("--forcer", help="dossier à publier (ex. 02-halloween-2)")
    ap.add_argument("--ignorer-heure", action="store_true")
    args = ap.parse_args()

    maintenant = datetime.now(PARIS)
    aujourdhui = maintenant.date().isoformat()
    reg = lire_registre()
    faits = reg.setdefault("carrousels", {})

    if not args.ignorer_heure and maintenant.hour < CONFIG["heure_carrousel"]:
        print(f"Il est {maintenant:%H:%M} à Paris : pas l'heure du carrousel.")
        return 0
    if not args.forcer and any(p.get("date") == aujourdhui for p in faits.values()):
        print("Le carrousel du jour a déjà été envoyé.")
        return 0

    dossiers = sorted(d.name for d in DOSSIER.iterdir() if (d / "infos.json").exists())
    nom = args.forcer or next((d for d in dossiers if d not in faits), None)
    if not nom:
        discord.envoyer("📭 **Carrousels TikTok** : plus aucun carrousel à envoyer, demande-en d'autres !")
        return 0
    infos = json.loads((DOSSIER / nom / "infos.json").read_text())
    images = sorted(p.name for p in (DOSSIER / nom).glob("*.jpg"))
    urls = [f"{CONFIG['pages']}carrousels/{quote(nom)}/{quote(i)}" for i in images]
    print(f"Carrousel : {nom} — {infos['titre']} ({len(urls)} photos)")
    print(infos["description"])
    if args.essai:
        print("\n".join(urls))
        print("\nMode essai : rien n'est publié.")
        return 0

    try:
        res = tiktok.publier_photos(urls, infos["titre"], infos["description"])
    except Exception as e:
        traceback.print_exc()
        discord.envoyer(f"❌ **Carrousel TikTok** `{nom}` : {str(e)[:400]}\nIl sera retenté au prochain passage.")
        return 1

    faits[nom] = {"date": aujourdhui, "titre": infos["titre"], "id": res["id"], "statut": res["statut"]}
    ecrire_registre(reg)
    restants = sum(1 for d in dossiers if d not in faits)
    lignes = [f"🖼️ **Carrousel TikTok** : {infos['titre']} (`{nom}`) envoyé en brouillon — {restants} carrousels restants",
              f"📱 Ouvre TikTok → notification « brouillon » → **Ajouter un son** (cherche « {infos['son']} ») → Publier.",
              "La description et les hashtags sont déjà remplis."]
    if res["jeton_change"]:
        lignes.append("⚠️ TikTok a renvoyé un nouveau jeton : relance `outils/envoyer_secrets.py` sur le Mac.")
    discord.envoyer("\n".join(lignes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
