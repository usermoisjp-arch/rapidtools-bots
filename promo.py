"""Garde #general vivant : poste de temps en temps un message qui donne envie d'acheter Rapid Quality.

  python promo.py            -> une passe (GitHub Actions toutes les heures ; ne poste que si c'est l'heure)
  python promo.py --dry      -> affiche un exemple de message, sans rien envoyer ni sauvegarder
  python promo.py --now      -> poste tout de suite (ignore l'écart et la plage horaire)
  python promo.py --now --key v10 -> poste ce message précis

Rythme : un message toutes les 6 à 12 h (tiré au hasard à chaque fois), seulement entre 13 h et 23 h UTC
(après-midi et soirée en Europe, journée aux États-Unis). Jamais le même message sur les 25 derniers.
Les messages « v » montrent une des 5 dernières vidéos de @snzzedit : carte avec miniature jointe
(TikTok bloque l'aperçu automatique de Discord, d'où la carte faite maison), bouton « Watch on TikTok ».

Règle : rien d'inventé. Prix, mises à jour à vie, navigateurs et avis viennent du site rapidquality.store.
Pas de fausse urgence (« plus que 3 places »), pas de faux avis.
Secret : DISCORD_PROMO_WEBHOOK_URL (webhook de #general). État : promo_state.json.
"""
import json
import os
import random
import sys
import time
from pathlib import Path

from watch import bright_videos, esc, post as send

ROOT = Path(__file__).parent
STATE = ROOT / "promo_state.json"
DRY = "--dry" in sys.argv
NOW = "--now" in sys.argv
FORCED_KEY = sys.argv[sys.argv.index("--key") + 1] if "--key" in sys.argv else None
SHOP = "https://rapidquality.store/"
HANDLE = "snzzedit"
GAP_HOURS = (6, 12)
HOURS_UTC = range(13, 23)
RECENT = 25

# Preuves : suivies de la carte de la vidéo (miniature, légende, bouton)
VIDEO = [
    "still thinking about it? this one was uploaded from a PC with Rapid Quality. look at the detail",
    "people keep asking if it really works. here's another one, straight from @snzzedit's PC",
    "zoom in on this one. that's what it looks like on TikTok after upload, not the export file",
    "watch this fullscreen on a big screen, then think about how your last upload looked",
    "latest from @snzzedit, posted with the extension. same thing for your edits for €20, once",
    "you spent hours on that edit. TikTok shouldn't get to wreck it in five seconds",
    "this is what we mean by sharp",
    "how many more edits are you gonna let TikTok blur before you try it?",
    "more proof, since that's what everyone asks for",
    "go fullscreen on this one",
    "you're seriously still hesitating? look at this upload and tell me you don't want yours to look like that",
    "if you're still on the fence, this is the video to watch",
    "posted from a PC with Rapid Quality. €20 one time, no subscription. that's the whole pitch",
]

PRICE = [
    "reminder that Rapid Quality is €20 one time. you pay once and every update after that is free",
    "no monthly fee on this one. €20, it's yours, updates included for life",
    "when TikTok changes something we update the extension. you don't pay again for that",
    "no trial that turns into a monthly charge, no renewal email. €20 and you're done",
    "if you've already spent money on presets and plugins, €20 so TikTok stops ruining all of it is the cheapest part of your setup",
    "one payment, instant access, works on Chrome, Edge and Brave",
]

NUDGE = [
    "the edit is done, the export looks perfect, then TikTok compresses it and it looks like a 2015 upload. that's exactly what this fixes",
    "you can keep tweaking your export settings, but on PC the blur usually comes from TikTok's re-encode",
    "works on Windows PCs and MacBooks. you set it up once, then you just drop your video in and upload",
    "if you bought it, tell us how your uploads look. if you didn't, what's stopping you? genuinely curious",
    "got a question before buying? hit Contact the team in <#1562177895860797603>, we answer",
    "TikTok re-encodes PC uploads. the bitrate drops, fine detail goes, fast motion turns to mush. Rapid Quality stops that",
    "you won't notice it on a phone preview. you'll notice it when someone watches your edit fullscreen",
    "your edit deserves to look the way it did in your timeline",
    "anime line art, faces, text on screen. that's usually the first stuff TikTok blurs",
    "it's PC only for now (Chrome, Edge, Brave). if you edit on a computer and post on TikTok, it's for you",
    "check <#1550435122564567220> if you want to see the same clip with and without it",
]

# Astuces tirées du guide d'installation, utiles à tous : pas de bouton d'achat
TIPS = [
    "tip for customers: export your MP4 with sound, even if the edit is silent, before you drop it in the extension",
    "tip: post the _patched.mp4 from tiktok.com/upload in your browser, not from the phone app",
    "tip: check the sharpness about 10 minutes after posting, not right away",
    "before a big upload, <#1550435117992910889> tells you if everything works right now",
    "keep the Rapid Quality folder somewhere safe after you load it. if you delete it, the extension stops working",
    "the setup steps are public in <#1562177908179738626> if you want to see how it works before buying",
]

# Teasers des prochains outils (pas de bouton d'achat : rien à acheter encore)
TEASERS = [
    "RapidCc's drop <t:1793469600:R>. our color correction presets, as LUTs. <#1562463197120823338>",
    "RapidQualityPresets, our Topaz Video presets, are out <t:1794074400:R> <#1562463199050342521>",
    "RapidScenes makes scene packs without the manual work: drop your video, pick the characters. <t:1794679200:R> <#1562463200585322637>",
    "RapidCaptions, caption presets and 3D text for After Effects, is coming <t:1795284000:R>. <#1562463202107990076>",
    "which one are you waiting for? RapidCc's, RapidQualityPresets, RapidScenes or RapidCaptions?",
]

# Récompense d'invitations (demande de Joris, 2026-10-30) : au moins un message par jour (INVITE_EVERY_H).
# Lien personnel via le bouton de #giveaways ou /invites ; 15 personnes = un tour de la roue des produits.
INVITES = [
    "know editors who'd want their uploads sharp? grab your own invite link in <#1565356814411898880> (or type /invites). every 15 people who join with it = a free spin of the product wheel",
    "free Rapid Quality, RapidCc's, RapidScenes and more are on the wheel. bring 15 editor friends with your invite link from <#1565356814411898880> and you spin it",
    "your editor friends complain about TikTok blurring their edits? send them your invite link (/invites). 15 joins and you spin the product wheel",
    "invite race is on: check the top inviters in <#1565356816223961258>. 15 people with your link = one free product off the wheel in <#1565356814411898880>",
    "type /invites to get your link and see how many people joined with it. at 15 the wheel spins for you, live in <#1565356814411898880>",
]
INVITE_EVERY_H = 24

# Questions pour faire parler les gens : pas de bouton d'achat
QUESTIONS = [
    "what are you editing with these days? CapCut, AE, something else?",
    "if your uploads look good, drop your export settings in <#1550435123479052334>. someone using the same app will thank you",
    "post your latest edit in <#1550435121524641853>, curious what everyone's working on",
    "what kind of edits do you make? anime, cars, gaming, something else?",
]

# Avis réels du site (rapidquality.store), cités tels quels
REVIEWS = [
    'Alejandro on the site: "This completely changed the quality of my edits. The before/after is honestly insane."',
    "James T. wrote this one: \"It feels like I'm back in the prime 2023 era in terms of quality, except now it works every time instead of randomly.\"",
    "Aurelia: \"Every serious editor needs this. I'm not letting TikTok flatten my work anymore.\"",
    'one of the reviews we got: "Setup took 30 seconds. The quality difference is something you actually see immediately."',
    "\"I still don't understand how it works, but all I know is that it works.\" best review we've had tbh",
    "someone called it TikTok Premium in a review and we can't really argue with that",
]

MESSAGES = {f"v{i}": m for i, m in enumerate(VIDEO)}
MESSAGES |= {f"p{i}": m for i, m in enumerate(PRICE)}
MESSAGES |= {f"n{i}": m for i, m in enumerate(NUDGE)}
MESSAGES |= {f"r{i}": m for i, m in enumerate(REVIEWS)}
MESSAGES |= {f"t{i}": m for i, m in enumerate(TIPS)}
MESSAGES |= {f"q{i}": m for i, m in enumerate(QUESTIONS)}
MESSAGES |= {f"c{i}": m for i, m in enumerate(TEASERS)}
MESSAGES |= {f"i{i}": m for i, m in enumerate(INVITES)}
NO_BUTTON = ("t", "q", "c", "i")  # astuces et questions : pas de bouton d'achat


def load(path: Path, default: dict) -> dict:
    return json.loads(path.read_text()) if path.exists() else default


def recent_videos() -> list[dict]:
    """Les 5 dernières vidéos à miniature lisible (vidéo + image). Liste vide si TikTok bloque : pas de message vidéo cette fois."""
    try:
        return [{**v, "image": img} for v, img in bright_videos(HANDLE)]
    except Exception as err:
        print(f"! vidéos indisponibles ({err})")
        return []


def pick(state: dict) -> tuple[str, str, dict | None]:
    videos = recent_videos()
    keys = [k for k in MESSAGES if k not in state["recent"] and (videos or not k.startswith("v"))]
    # Une fois sur trois une preuve vidéo, sinon un autre type
    video_keys = [k for k in keys if k.startswith("v")]
    other_keys = [k for k in keys if not k.startswith("v")]
    key = FORCED_KEY or random.choice(video_keys if video_keys and (random.random() < 0.35 or not other_keys) else other_keys)
    # Invitations : un message par jour au moins, en plus du tirage normal
    invite_keys = [k for k in MESSAGES if k.startswith("i") and k not in state["recent"][-len(INVITES) + 1:]]
    if not FORCED_KEY and time.time() - state.get("invite_last", 0) >= INVITE_EVERY_H * 3600 and invite_keys:
        key = random.choice(invite_keys)
    if key.startswith("i"):
        state["invite_last"] = time.time()
    video = None
    if key.startswith("v") and videos:
        fresh = [v for v in videos if v["url"] not in state["recent_videos"]] or videos
        video = random.choice(fresh)
        state["recent_videos"] = (state["recent_videos"] + [video["url"]])[-3:]
    return key, MESSAGES[key], video


def build(text: str, video: dict | None, sell: bool = True) -> tuple[dict, bytes | None]:
    buttons = [{"type": 2, "style": 5, "label": "Get Rapid Quality", "url": SHOP, "emoji": {"name": "⚡"}}] if sell else []
    payload = {"content": text, "allowed_mentions": {"parse": []}}
    cover = None
    if video:
        cover = video["image"]
        embed = {
            "color": 0x22D3EE,
            "author": {"name": f"@{HANDLE} on TikTok", "url": f"https://www.tiktok.com/@{HANDLE}"},
            "title": esc(video["title"] or "Watch on TikTok")[:256],
            "url": video["url"],
            "footer": {"text": "Uploaded with Rapid Quality"},
        }
        if cover:
            embed["image"] = {"url": "attachment://cover.jpg"}
        payload["embeds"] = [embed]
        buttons.insert(0, {"type": 2, "style": 5, "label": "Watch on TikTok", "url": video["url"]})
    if buttons:
        payload["components"] = [{"type": 1, "components": buttons}]
    return payload, cover


def main() -> int:
    state = load(STATE, {"last": 0, "gap_h": 0, "recent": [], "recent_videos": []})
    now = time.time()
    due = now - state["last"] >= state["gap_h"] * 3600 and time.gmtime(now).tm_hour in HOURS_UTC
    if not (due or NOW or DRY):
        print(f"pas encore l'heure (prochain message après {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(state['last'] + state['gap_h'] * 3600))}, entre 13 h et 23 h UTC)")
        return 0

    key, text, video = pick(state)
    print(f"→ [{key}] {text}" + (f"  [{video['url']}]" if video else ""))
    if DRY:
        return 0
    send(*build(text, video, sell=not key.startswith(NO_BUTTON)), webhook=os.environ["DISCORD_PROMO_WEBHOOK_URL"])
    state["last"] = now
    state["gap_h"] = round(random.uniform(*GAP_HOURS), 2)
    state["recent"] = (state["recent"] + [key])[-RECENT:]
    STATE.write_text(json.dumps(state, indent=2) + "\n")
    print(f"prochain message dans {state['gap_h']} h")
    return 0


if __name__ == "__main__":
    sys.exit(main())
