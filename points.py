"""XP du serveur : toutes les 10 min, envoie points.json au bot (Vercel, /api/cron) qui relit les nouveaux
messages, donne les rôles de niveau, met à jour #leaderboard et renvoie le nouvel état, sauvegardé ici.
Le token du bot reste sur Vercel ; ce script n'a que CRON_SECRET. Bibliothèque standard seulement.
Le premier passage démarre le compteur (les messages d'avant ne comptent pas).
"""
import json
import os
import urllib.request
from pathlib import Path

POINTS = Path(__file__).resolve().parent / "points.json"
CRON_URL = "https://rapidtools-bot.vercel.app/api/cron"

state = json.loads(POINTS.read_text()) if POINTS.exists() else {}
req = urllib.request.Request(
    CRON_URL,
    data=json.dumps({"task": "points", "state": state}).encode(),
    headers={"Authorization": f"Bearer {os.environ['CRON_SECRET']}", "Content-Type": "application/json", "User-Agent": "rapidtools-bots"},
)
out = json.loads(urllib.request.urlopen(req, timeout=90).read())
new = out["state"]
assert isinstance(new.get("users"), dict) and isinstance(new.get("cursors"), dict)
POINTS.write_text(json.dumps(new, indent=1, sort_keys=True) + "\n")
print(f"{out['counted']} messages comptés, {out['levelUps']} passages de niveau, {len(new['users'])} membres avec de l'XP")
