"""Annonce dans #announcements, de temps en temps, avec un visuel : donne envie d'acheter Rapid Quality.
Sans ping (choix de Joris, 2026-10-21) : un @everyone répété pour vendre fait couper les notifications.

  python announce.py               -> une passe (GitHub Actions toutes les heures ; ne poste que si c'est l'heure)
  python announce.py --dry         -> affiche l'annonce qui serait tirée
  python announce.py --test        -> poste dans #staff-chat (secret DISCORD_TEST_WEBHOOK_URL), sans ping ni sauvegarde
  python announce.py --test --key video   -> teste une annonce précise
  python announce.py --now         -> poste tout de suite dans #announcements

Rythme : une annonce tous les 4 à 7 jours (tiré au hasard), entre 17 h et 20 h UTC (soirée en Europe,
après-midi aux États-Unis). Jamais la même que l'une des 3 précédentes.

Règle : rien d'inventé. Textes repris du site rapidquality.store (accroche, avis, prix, navigateurs)
et du guide d'installation ; visuels : comparatif du site (assets/before-after.jpg), image du site,
miniature de la dernière vidéo de @snzzedit.
Secret : DISCORD_ANNOUNCE_WEBHOOK_URL (webhook de #announcements). État : announce_state.json.
"""
import json
import os
import random
import sys
import time
from pathlib import Path

from watch import bright_videos, esc, post as send

ROOT = Path(__file__).parent
STATE = ROOT / "announce_state.json"
DRY = "--dry" in sys.argv
TEST = "--test" in sys.argv
NOW = "--now" in sys.argv
FORCED_KEY = sys.argv[sys.argv.index("--key") + 1] if "--key" in sys.argv else None
SHOP = "https://rapidquality.store/"
SITE_IMAGE = "https://rapidquality.store/cdn/shop/files/SEOWEBSITEIMAGE.jpg?v=1778957415"
GET_VERIFIED = "<#1562177895860797603>"
HANDLE = "snzzedit"
GAP_DAYS = (4, 7)
HOURS_UTC = range(17, 20)
RECENT = 3
INVITE_EVERY_D = 7
COLOR = 0x22D3EE
FOOTER = {"text": "Rapid Quality · Not affiliated with TikTok", "icon_url": "attachment://logo.jpeg"}

# image : "ba" = comparatif sans/avec, "site" = image du site, "video" = miniature de la dernière vidéo
ANNOUNCEMENTS = {
    "before-after": {
        "ping": "quick look at what TikTok does to a PC upload 👇",
        "image": "ba",
        "title": "This is what TikTok does to your edits",
        "description": (
            "On the left, a normal upload from a computer. On the right, the same clip uploaded with Rapid Quality.\n\n"
            "TikTok re-encodes everything you post from a PC and the bitrate drops hard. "
            "Rapid Quality makes your video land on TikTok the way you exported it.\n\n"
            "**€20 one time**, lifetime updates. Chrome, Edge and Brave, on Windows and Mac."
        ),
    },
    "video": {
        "ping": "more proof, straight from @snzzedit",
        "image": "video",
        "title": "Uploaded by @snzzedit with Rapid Quality",
        "description": (
            "{caption}"
            "Posted from a PC with Rapid Quality. Open it on TikTok, go fullscreen and compare it with your last upload.\n\n"
            "You pay **€20 once** and every update after that is free."
        ),
    },
    "pitch": {
        "ping": "if you post edits from your PC, this is for you",
        "image": "site",
        "title": "Stop letting TikTok ruin your edits",
        "description": (
            "PC uploads get re-encoded by TikTok: bitrate gets slashed, fine detail vanishes, motion blurs. "
            "Rapid Quality fixes the upload at the source, so your video lands on TikTok the way you exported it.\n\n"
            "Made for editors: anime edits, AMVs, car edits, gaming clips and every high quality TikTok video.\n\n"
            "**€20 one time.** No subscription."
        ),
    },
    "reviews": {
        "ping": "here's what people say after trying it",
        "image": "ba",
        "title": "What editors say",
        "description": "Real reviews from rapidquality.store.",
        "fields": [
            {"name": "★★★★★ Alejandro", "value": "\"This completely changed the quality of my edits. The before/after is honestly insane.\""},
            {"name": "★★★★★ James T.", "value": "\"It feels like I'm back in the prime 2023 era in terms of quality, except now it works every time instead of randomly.\""},
            {"name": "★★★★★ Aurelia", "value": "\"Every serious editor needs this. I'm not letting TikTok flatten my work anymore.\""},
        ],
    },
    "price": {
        "ping": "reminder for anyone still on the fence",
        "image": "site",
        "title": "One payment, yours for life",
        "description": (
            "There's no subscription and nothing to renew. You pay **€20 once** and you get every future version of Rapid Quality, "
            "including the fixes we ship when TikTok changes something.\n\n"
            f"Already bought it? Get verified in {GET_VERIFIED} to unlock the customer channels."
        ),
    },
    # Teaser des prochains outils : dates de config/site.json (launches), décrits d'après Joris
    "coming-soon": {
        "ping": "4 new tools are on the way 👀",
        "image": "coming-soon",
        "title": "Coming soon to RapidTools",
        "description": (
            "🎨 **RapidCc's**: our color correction presets, as LUTs. <#1562463197120823338> · <t:1793469600:R>\n"
            "🤖 **RapidQualityPresets**: the presets we use in Topaz Video. <#1562463199050342521> · <t:1794074400:R>\n"
            "🎬 **RapidScenes**: drop your video, pick the characters, get the packs. <#1562463200585322637> · <t:1794679200:R>\n"
            "✍️ **RapidCaptions**: caption presets and 3D text for After Effects. <#1562463202107990076> · <t:1795284000:R>\n\n"
            "Want a ping when each one drops? Pick **Yes, ping me** in **Channels & Roles**."
        ),
    },
    # Récompense d'invitations (demande de Joris, 2026-10-30) : au moins une fois par semaine (INVITE_EVERY_D)
    "invites": {
        "ping": "invite your editor friends, win a product 📨",
        "image": "giveaway",
        "title": "15 invites = a free spin of the product wheel",
        "description": (
            "Get your own invite link in <#1565356814411898880> (button **Get my invite link**) or type `/invites` anywhere.\n\n"
            "Send it to editors who'd like Rapid Quality or the tools on the way. Every **15 people** who join with your link = "
            "**one spin of the product wheel**, live in <#1565356814411898880>: Rapid Quality, RapidCc's, RapidQualityPresets, "
            "RapidScenes or RapidCaptions, free.\n\n"
            "Top inviters are in <#1565356816223961258>. Only real people count, the team checks every win."
        ),
    },
    "how-it-works": {
        "ping": "how it works, in case you were wondering",
        "image": "ba",
        "title": "Four steps and your uploads stay sharp",
        "description": (
            "1. Unzip the file you get after buying\n"
            "2. Load it in Chrome, Edge or Brave (one time, no account needed)\n"
            "3. Drop your video in the extension\n"
            "4. Post the fixed file on tiktok.com/upload from your computer\n\n"
            "**€20 once**, updates included for life."
        ),
    },
}


def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {"last": 0, "gap_d": 0, "recent": []}


def build(key: str) -> tuple[dict, list[tuple[str, bytes]]]:
    a = ANNOUNCEMENTS[key]
    files = [("logo.jpeg", (ROOT / "assets/logo.jpeg").read_bytes())]
    embed = {"color": COLOR, "title": a["title"], "url": SHOP, "footer": FOOTER, "thumbnail": {"url": "attachment://logo.jpeg"}}
    buttons = [{"type": 2, "style": 5, "label": "Get Rapid Quality", "url": SHOP, "emoji": {"name": "⚡"}}]
    description = a["description"]

    if a["image"] == "ba":
        files.append(("before-after.jpg", (ROOT / "assets/before-after.jpg").read_bytes()))
        embed["image"] = {"url": "attachment://before-after.jpg"}
    elif a["image"] == "coming-soon":
        files.append(("coming-soon.jpg", (ROOT / "assets/coming-soon.jpg").read_bytes()))
        embed["image"] = {"url": "attachment://coming-soon.jpg"}
    elif a["image"] == "giveaway":
        files.append(("invites.jpg", (ROOT / "assets/invites.jpg").read_bytes()))
        embed["image"] = {"url": "attachment://invites.jpg"}
    elif a["image"] == "site":
        embed["image"] = {"url": SITE_IMAGE}
    elif a["image"] == "video":
        # La plus récente à miniature lisible ; erreur si TikTok bloque ou rien d'utilisable : main() passe à une autre annonce
        video, cover = bright_videos(HANDLE)[0]
        files.append(("cover.jpg", cover))
        embed["image"] = {"url": "attachment://cover.jpg"}
        caption = esc(video["title"][:200])
        description = description.replace("{caption}", f"> {caption}\n\n" if caption else "")
        buttons.insert(0, {"type": 2, "style": 5, "label": "Watch on TikTok", "url": video["url"]})

    embed["description"] = description
    if a.get("fields"):
        embed["fields"] = a["fields"]
    payload = {
        "content": ("[TEST] " if TEST else "") + a["ping"],
        "embeds": [embed],
        "components": [{"type": 1, "components": buttons}],
        "allowed_mentions": {"parse": []},
    }
    return payload, files


def main() -> int:
    state = load_state()
    now = time.time()
    due = now - state["last"] >= state["gap_d"] * 86400 and time.gmtime(now).tm_hour in HOURS_UTC
    if not (due or NOW or TEST or DRY):
        nxt = time.gmtime(state["last"] + state["gap_d"] * 86400)
        print(f"pas encore l'heure (prochaine annonce après {time.strftime('%Y-%m-%d %H:%M UTC', nxt)}, entre 17 h et 20 h UTC)")
        return 0

    fresh = [k for k in ANNOUNCEMENTS if k not in state["recent"]] or list(ANNOUNCEMENTS)
    keys = [FORCED_KEY] if FORCED_KEY else random.sample(fresh, k=len(fresh))
    if not FORCED_KEY and now - state.get("invite_last", 0) >= INVITE_EVERY_D * 86400:
        keys = ["invites"] + [k for k in keys if k != "invites"]
    for key in keys:
        try:
            payload, files = build(key)
        except Exception as err:  # TikTok indisponible pour l'annonce vidéo : on passe à la suivante
            print(f"! {key} impossible ({err})")
            continue
        print(f"→ [{key}] {payload['content']} | {payload['embeds'][0]['title']}")
        if DRY:
            return 0
        webhook = os.environ["DISCORD_TEST_WEBHOOK_URL" if TEST else "DISCORD_ANNOUNCE_WEBHOOK_URL"]
        send(payload, files=files, webhook=webhook)
        if not TEST:
            if key == "invites":
                state["invite_last"] = now
            state.update(last=now, gap_d=round(random.uniform(*GAP_DAYS), 2), recent=(state["recent"] + [key])[-RECENT:])
            STATE.write_text(json.dumps(state, indent=2) + "\n")
            print(f"prochaine annonce dans {state['gap_d']} jours")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
