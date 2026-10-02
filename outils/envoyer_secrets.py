"""À lancer sur le Mac : copie les clés déjà en place (n8n + ~/lancer_n8n.sh) dans GitHub Secrets.

    python3 outils/envoyer_secrets.py

Aucune clé n'est affichée : elles passent directement de ton Mac à GitHub via `gh secret set`.
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

DEPOT = "nicovitch27-dev/anim-en-poche"
N8N = str(Path.home() / ".local/bin/n8n")
WORKFLOW_N8N = "cdbc78e8-04ee-4e11-8434-3180e761f4d1"


def envoyer(nom, valeur):
    if not valeur:
        print(f"  ⏭  {nom} : introuvable, ignoré")
        return
    subprocess.run(["gh", "secret", "set", nom, "--repo", DEPOT], input=valeur, text=True,
                   check=True, capture_output=True)
    print(f"  ✅ {nom}")


def main():
    secrets = {}

    # TikTok + Meta : dans le lanceur de n8n
    lanceur = (Path.home() / "lancer_n8n.sh").read_text()
    for nom in ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN", "META_PAGE_TOKEN"):
        m = re.search(rf"^export {nom}=['\"]?([^'\"\n]+)", lanceur, re.M)
        secrets[nom] = m.group(1) if m else None

    with tempfile.TemporaryDirectory() as tmp:
        # YouTube : identifiant OAuth enregistré (chiffré) dans n8n
        sortie = Path(tmp) / "cred.json"
        subprocess.run([N8N, "export:credentials", "--all", "--decrypted", f"--output={sortie}"],
                       check=True, capture_output=True)
        for c in json.loads(sortie.read_text()):
            if c.get("type") == "youTubeOAuth2Api":
                d = c["data"]
                secrets["YT_CLIENT_ID"] = d.get("clientId")
                secrets["YT_CLIENT_SECRET"] = d.get("clientSecret")
                secrets["YT_REFRESH_TOKEN"] = (d.get("oauthTokenData") or {}).get("refresh_token")
        sortie.unlink()

        # Discord : adresse du webhook dans le workflow n8n
        wf = Path(tmp) / "wf.json"
        subprocess.run([N8N, "export:workflow", f"--id={WORKFLOW_N8N}", f"--output={wf}"],
                       check=True, capture_output=True)
        m = re.search(r"https://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/[\w/-]+", wf.read_text())
        secrets["DISCORD_WEBHOOK"] = m.group(0) if m else None

    print(f"Envoi vers GitHub Secrets ({DEPOT}) :")
    for nom, valeur in secrets.items():
        envoyer(nom, valeur)
    print("\nTerminé. Vérifie avec : gh secret list --repo " + DEPOT)


if __name__ == "__main__":
    sys.exit(main())
