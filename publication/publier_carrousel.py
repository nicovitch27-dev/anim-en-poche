"""Carrousel TikTok du jour : envoie en brouillon le carrousel que le calendrier désigne.

Chaque dossier de carrousels/ contient les diapos (01-….jpg, 02-….jpg, … dans l'ordre) et infos.json :
    {"titre", "description" (légende + hashtags), "son" (mot à chercher dans les sons TikTok),
     "theme", "numero", "total" (carrousels du thème), "periode" (["MM-JJ", "MM-JJ"] ou null), "ordre"}
Un thème de saison (Halloween, Noël, été…) n'est publié que pendant sa période, ses carrousels
étalés régulièrement dessus ; les autres jours, on prend un thème « toute l'année », en alternant.
Les images sont servies par GitHub Pages (préfixe vérifié chez TikTok). L'API ne permet pas de
choisir la musique d'un brouillon : la notification Discord rappelle quel son ajouter.

    python publication/publier_carrousel.py --essai
    python publication/publier_carrousel.py --ignorer-heure [--forcer 02-halloween-2]
"""
import argparse
import json
import sys
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
from plateformes import discord, tiktok  # noqa: E402
from publier import CONFIG, PARIS, ecrire_registre, lire_registre  # noqa: E402

DOSSIER = ICI.parent / "carrousels"


def fenetre(periode, jour):
    """(début, fin) de la période qui contient ce jour, ou None. Gère les périodes à cheval sur deux années."""
    (md, jd), (mf, jf) = (map(int, x.split("-")) for x in periode)
    for an in (jour.year - 1, jour.year):
        debut = date(an, md, jd)
        fin = date(an + (1 if (mf, jf) < (md, jd) else 0), mf, jf)
        if debut <= jour <= fin:
            return debut, fin
    return None


def choisir(carrousels, faits, jour):
    """carrousels : {nom: infos}. Renvoie le nom à publier ce jour-là, ou None."""
    dus, libres = [], []
    for nom, i in carrousels.items():
        if nom in faits:
            continue
        if not i.get("periode"):
            libres.append((i.get("numero", 1), i.get("ordre", 99), nom))
            continue
        f = fenetre(i["periode"], jour)
        if not f:
            continue
        duree = (f[1] - f[0]).days + 1
        echeance = f[0] + timedelta(days=int((i.get("numero", 1) - 0.5) * duree / i.get("total", 1)))
        if jour >= echeance:
            dus.append((f[1], echeance, i.get("ordre", 99), nom))   # la saison qui finit le plus tôt d'abord
    choix = min(dus) if dus else min(libres) if libres else None
    return choix[-1] if choix else None


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

    carrousels = {d.name: json.loads((d / "infos.json").read_text())
                  for d in DOSSIER.iterdir() if (d / "infos.json").exists()}
    nom = args.forcer or choisir(carrousels, faits, maintenant.date())
    if not nom:
        print("Aucun carrousel prévu aujourd'hui (rien de la saison, plus de thème toute l'année).")
        if not any(n not in faits for n in carrousels):
            discord.envoyer("📭 **Carrousels TikTok** : tous les carrousels sont publiés, demande-en d'autres !")
        return 0
    infos = carrousels[nom]
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
    restants = sum(1 for d in carrousels if d not in faits)
    lignes = [f"🖼️ **Carrousel TikTok** : {infos['titre']} (`{nom}`) envoyé en brouillon — {restants} carrousels restants",
              f"📱 Ouvre TikTok → notification « brouillon » → **Ajouter un son** (cherche « {infos['son']} ») → Publier.",
              "La description et les hashtags sont déjà remplis."]
    if res["jeton_change"]:
        lignes.append("⚠️ TikTok a renvoyé un nouveau jeton : relance `outils/envoyer_secrets.py` sur le Mac.")
    discord.envoyer("\n".join(lignes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
