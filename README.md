# anim-en-poche
Site Anim en poche - jeux collectifs en video

## Publication automatique

`.github/workflows/publier.yml` publie chaque jour à 12h et à 18h (Paris) une vidéo de
`motion/videos-realisees` (branche `claude/confident-archimedes-d6w5qr`) sur YouTube, TikTok
(brouillon), Instagram, Facebook et Pinterest. Réglages : `publication/config.json`.
Registre anti-doublon : `publication/publications.json`.

## Carrousels TikTok

Chaque jour à partir de 12h, `publication/publier_carrousel.py` envoie en brouillon TikTok le prochain
dossier de `carrousels/` (diapos `*.jpg` dans l'ordre + `infos.json` : titre, description, son à ajouter).
Les images sont lues par TikTok sur GitHub Pages, préfixe vérifié dans le portail développeur
(fichier `tiktokeqz1….txt` à la racine : ne pas le supprimer). Le son se choisit dans l'appli.
