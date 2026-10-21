"""Surveille un ou plusieurs comptes TikTok et poste chaque nouvelle vidéo dans Discord.

  python watch.py            -> une passe (ce que lance GitHub Actions toutes les 10 min)
  python watch.py --dry      -> affiche ce qui serait posté, sans rien envoyer ni sauvegarder

Config : accounts.txt (un @pseudo par ligne). Secret : DISCORD_WEBHOOK_URL.
État : state.json (vidéos déjà vues, phrases récentes), sauvegardé dans le dépôt par le workflow.
Au premier passage d'un compte, ses vidéos existantes sont seulement mémorisées (pas de rafale).
"""
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

import yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget

from phrases import make_phrase

ROOT = Path(__file__).parent
STATE = ROOT / "state.json"
DRY = "--dry" in sys.argv
RECENT_PHRASES = 30
LOOKBACK = 8  # nombre de vidéos récentes relues à chaque passe
# Vidéos à ne jamais poster ni citer en preuve. Liste privée : variable GitHub BANNED_IDS (ids séparés
# par des espaces ou des virgules) et, en local, banned.txt (ignoré par git). Jamais dans le dépôt public.
BANNED = set(os.environ.get("BANNED_IDS", "").replace(",", " ").split())
if (ROOT / "banned.txt").exists():
    BANNED |= {l.strip() for l in (ROOT / "banned.txt").read_text().splitlines() if l.strip() and not l.startswith("#")}


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"seen": {}, "recent_phrases": []}


def pick_cover(thumbs: list[dict]) -> str | None:
    """La couverture choisie par le créateur (« cover »). « originCover » est la 1re image, souvent noire."""
    by_id = {t.get("id"): t["url"] for t in thumbs if t.get("url")}
    return next((by_id[k] for k in ("cover", "originCover", "dynamicCover") if k in by_id), None)


def latest_videos(handle: str) -> list[dict]:
    # Se fait passer pour Chrome (curl-cffi) : TikTok bloque les requêtes « robot » des serveurs
    opts = {"extract_flat": True, "playlistend": LOOKBACK, "quiet": True, "no_warnings": True,
            "impersonate": ImpersonateTarget("chrome")}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"https://www.tiktok.com/@{handle}", download=False)
    videos = [
        {
            "id": e["id"],
            "url": e.get("url") or f"https://www.tiktok.com/@{handle}/video/{e['id']}",
            "ts": e.get("timestamp") or 0,
            "title": (e.get("title") or "").strip(),
            "cover": pick_cover(e.get("thumbnails") or []),
        }
        for e in info.get("entries") or []
        if e and e.get("id") and e["id"] not in BANNED
    ]
    return sorted(videos, key=lambda v: v["ts"])  # du plus ancien au plus récent


def esc(text: str) -> str:
    """Neutralise le markdown Discord d'un texte venu de TikTok (liens masqués, mentions)."""
    return re.sub(r"([\\`*_~|<>\[\]()#@])", r"\\\1", text or "")


def brightness(image: bytes) -> float:
    """Luminosité moyenne (0 à 255) : sert à écarter les miniatures presque noires."""
    from io import BytesIO
    from PIL import Image, ImageStat
    return ImageStat.Stat(Image.open(BytesIO(image)).convert("L")).mean[0]


def bright_videos(handle: str, count: int = 5, minimum: float = 45) -> list[tuple[dict, bytes]]:
    """Les vidéos récentes dont la miniature est assez claire pour un beau visuel, avec la miniature."""
    out = []
    for v in reversed(latest_videos(handle)[-count:]):
        cover = download(v["cover"]) if v.get("cover") else None
        if cover and brightness(cover) >= minimum:
            out.append((v, cover))
    return out


def download(url: str) -> bytes | None:
    """Récupère la miniature (les liens TikTok expirent en 2 jours : on l'envoie en pièce jointe)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.tiktok.com/"})
        return urllib.request.urlopen(req, timeout=20).read()
    except Exception as err:
        print(f"  miniature indisponible ({err})")
        return None


def build_message(handle: str, phrase: str, video: dict) -> tuple[dict, bytes | None]:
    cover = download(video["cover"]) if video.get("cover") else None
    embed = {
        "color": 0x22D3EE,
        "author": {"name": f"@{handle} on TikTok", "url": f"https://www.tiktok.com/@{handle}"},
        "title": esc(video["title"] or "New video")[:256],
        "url": video["url"],
        "footer": {"text": "Posted with Rapid Quality"},
    }
    if video.get("ts"):
        embed["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(video["ts"]))
    if cover:
        embed["image"] = {"url": "attachment://cover.jpg"}
    payload = {
        "content": phrase,
        "embeds": [embed],
        "components": [{"type": 1, "components": [{"type": 2, "style": 5, "label": "Watch on TikTok", "url": video["url"]}]}],
        "allowed_mentions": {"parse": []},
    }
    return payload, cover


def post(payload: dict, cover: bytes | None = None, webhook: str | None = None, files: list[tuple[str, bytes]] | None = None) -> None:
    """Poste via un webhook (par défaut celui de #live-proof), avec des images jointes éventuelles."""
    url = (webhook or os.environ["DISCORD_WEBHOOK_URL"]) + "?with_components=true"
    files = (files or []) + ([("cover.jpg", cover)] if cover else [])
    if files:
        boundary = "rapidtools" + str(int(time.time() * 1000))
        payload = {**payload, "attachments": [{"id": n, "filename": name} for n, (name, _) in enumerate(files)]}
        body = f"--{boundary}\r\nContent-Disposition: form-data; name=\"payload_json\"\r\nContent-Type: application/json\r\n\r\n".encode() + json.dumps(payload).encode()
        for n, (name, data) in enumerate(files):
            body += f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"files[{n}]\"; filename=\"{name}\"\r\nContent-Type: image/jpeg\r\n\r\n".encode() + data
        body += f"\r\n--{boundary}--\r\n".encode()
        ctype = f"multipart/form-data; boundary={boundary}"
    else:
        body, ctype = json.dumps(payload).encode(), "application/json"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": ctype, "User-Agent": "rapidtools-tiktok-watch"})
    for _ in range(3):
        try:
            urllib.request.urlopen(req, timeout=30)
            return
        except urllib.error.HTTPError as err:
            if err.code == 429:
                time.sleep(float(json.loads(err.read() or b"{}").get("retry_after", 2)) + 0.5)
                continue
            raise RuntimeError(f"Discord {err.code}: {err.read()[:300]}") from err


def main() -> int:
    accounts = [l.strip().lstrip("@") for l in (ROOT / "accounts.txt").read_text().splitlines() if l.strip() and not l.startswith("#")]
    state = load_state()
    errors = 0

    for handle in accounts:
        try:
            videos = latest_videos(handle)
        except Exception as err:  # TikTok bloque parfois : on réessaiera au prochain passage
            print(f"! @{handle} : lecture impossible ({err})")
            errors += 1
            continue

        seen = state["seen"].setdefault(handle, [])
        first_run = not seen
        new = [v for v in videos if v["id"] not in seen]
        if first_run:
            print(f"@{handle} : premier passage, {len(new)} vidéo(s) mémorisée(s) sans annonce")
        for v in ([] if first_run else new):
            key, phrase = make_phrase(f"**@{handle}**", state["recent_phrases"])
            print(f"→ {phrase} {v['url']}")
            if not DRY:
                post(*build_message(handle, phrase, v))
                state["recent_phrases"] = (state["recent_phrases"] + [key])[-RECENT_PHRASES:]
        seen.extend(v["id"] for v in new)
        state["seen"][handle] = seen[-200:]
        if not new:
            print(f"@{handle} : rien de nouveau")

    if not DRY:
        STATE.write_text(json.dumps(state, indent=2) + "\n")
    # Échec seulement si aucun compte n'a pu être lu (évite les alertes pour un raté isolé)
    return 1 if accounts and errors == len(accounts) else 0


if __name__ == "__main__":
    sys.exit(main())
