# -*- coding: utf-8 -*-
"""Miniature YouTube 1280x720 : fond du modèle « Balle aux prisonniers » sans son titre,
avec le nom du jeu réécrit dans le même style (ligne 1 jaune, ligne 2 blanche,
contour bleu marine épais, ombre portée).

Usage : python generer_miniature.py "Ballon brûlé" sortie.jpg
"""
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

ICI = os.path.dirname(os.path.abspath(__file__))
FOND = os.path.join(ICI, "fond_sans_titre.png")
SF_ROUNDED = "/System/Library/Fonts/SFNSRounded.ttf"   # police d'origine (Mac uniquement)
NUNITO = os.path.join(ICI, "Nunito.ttf")                # équivalent libre (licence OFL) pour GitHub Actions

JAUNE = (252, 222, 43)
BLANC = (255, 255, 255)
MARINE = (19, 22, 73)

CENTRE_X = 655          # centre horizontal du titre d'origine
ZONE_HAUT, ZONE_BAS = 112, 362   # bande verticale disponible au-dessus de « LES RÈGLES DU JEU »
LARGEUR_MAX = 740


def nettoyer(titre):
    t = re.sub(r"\s*\([^)]*\)", "", titre).strip()       # retire « (Baseball) », « (variante) »…
    return t.upper()


def couper(titre):
    """1 ligne si court, sinon 2 lignes équilibrées (comme BALLE AUX / PRISONNIERS)."""
    mots = titre.split()
    if len(mots) == 1 or len(titre) <= 11:
        return [titre]
    meilleur = None
    for i in range(1, len(mots)):
        l1, l2 = " ".join(mots[:i]), " ".join(mots[i:])
        ecart = abs(len(l1) - len(l2)) + (2 if len(l1) > len(l2) else 0)  # ligne 1 un peu plus courte
        if meilleur is None or ecart < meilleur[0]:
            meilleur = (ecart, [l1, l2])
    return meilleur[1]


def police(taille):
    if os.path.exists(SF_ROUNDED):
        f = ImageFont.truetype(SF_ROUNDED, taille)
        f.set_variation_by_axes([400, 1000])   # GRAD, Weight max = « Black »
    else:
        f = ImageFont.truetype(NUNITO, taille)
        f.set_variation_by_axes([1000])        # Weight max = « Black »
    return f


def dessiner_ligne(img, texte, taille, cy, couleur):
    f = police(taille)
    d = ImageDraw.Draw(img)
    contour = max(9, taille // 7)
    l, t, r, b = d.textbbox((0, 0), texte, font=f, stroke_width=contour)
    x = CENTRE_X - (r - l) / 2 - l
    y = cy - (b - t) / 2 - t
    # ombre portée
    d.text((x + taille * 0.05, y + taille * 0.11), texte, font=f, fill=MARINE,
           stroke_width=contour, stroke_fill=MARINE)
    # contour épais puis remplissage
    d.text((x, y), texte, font=f, fill=couleur, stroke_width=contour, stroke_fill=MARINE)


def taille_pour(texte, largeur, hauteur):
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    for taille in range(140, 30, -2):
        f = police(taille)
        l, t, r, b = d.textbbox((0, 0), texte, font=f, stroke_width=max(9, taille // 7))
        if r - l <= largeur and b - t <= hauteur:
            return taille
    return 30


def generer(titre, sortie):
    img = Image.open(FOND).convert("RGB")
    lignes = couper(nettoyer(titre))
    hauteur_zone = ZONE_BAS - ZONE_HAUT
    if len(lignes) == 1:
        taille = taille_pour(lignes[0], LARGEUR_MAX, hauteur_zone * 0.62)
        dessiner_ligne(img, lignes[0], taille, (ZONE_HAUT + ZONE_BAS) / 2, JAUNE)
    else:
        h = hauteur_zone / 2
        taille = min(taille_pour(l, LARGEUR_MAX, h * 1.18) for l in lignes)
        dessiner_ligne(img, lignes[0], taille, ZONE_HAUT + h * 0.5, JAUNE)
        dessiner_ligne(img, lignes[1], taille, ZONE_HAUT + h * 1.5, BLANC)
    img.save(sortie, "JPEG", quality=90, optimize=True)   # < 2 Mo exigé par YouTube
    return sortie


if __name__ == "__main__":
    generer(sys.argv[1], sys.argv[2])
