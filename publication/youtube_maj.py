"""Met à niveau les vidéos YouTube déjà publiées : titre de recherche, description avec le lien de la fiche,
rangement de la vidéo longue dans la playlist de sa famille de jeux. Sans risque de doublon : relançable.
    python publication/youtube_maj.py [--essai]"""
import sys

import publier
from plateformes import discord, youtube


def main():
    essai = "--essai" in sys.argv
    tok = None if essai else youtube.jeton()
    lignes, erreurs = [], 0
    for dossier, e in publier.lire_registre()["publiees"].items():
        meta_ = publier.metadonnees(e["titre"])
        pl = publier.playlist_de(meta_)
        res = e.get("resultats", {})
        print(f"{dossier} : {meta_['titre']} → {meta_['lien']} {pl[0] if pl else '(sans playlist)'}")
        if essai:
            continue
        for fmt in ("youtube", "youtube_short"):
            vid = res.get(fmt, {}).get("id")
            if not vid:
                continue
            try:
                youtube.modifier(vid, meta_["titre"], meta_["description"], tok)
                if fmt == "youtube" and pl:
                    youtube.ajouter_a_playlist(vid, youtube.playlist(*pl, tok), tok)
            except Exception as ex:
                erreurs += 1
                print(f"   ❌ {fmt} {vid} : {str(ex)[:200]}")
                lignes.append(f"❌ {e['titre']} ({fmt}) : {str(ex)[:150]}")
                if erreurs >= 3:
                    discord.envoyer("🛠️ **Mise à jour YouTube arrêtée**\n" + "\n".join(lignes))
                    return 1
    if not essai:
        discord.envoyer(f"🛠️ **Mise à jour YouTube** : titres, descriptions avec lien et playlists refaits "
                        f"({erreurs} erreur(s))." + ("\n" + "\n".join(lignes) if lignes else ""))
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
