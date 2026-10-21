"""Phrases d'annonce des nouvelles vidéos (anglais, comme le serveur).

Une phrase = accroche + corps + chute, tirés au hasard : 18 x 20 x 16 = 5 760 combinaisons,
plus les emojis. watch.py évite de reprendre une phrase déjà utilisée parmi les 30 dernières.
"""
import random

OPENERS = [
    "🚨 New drop!",
    "🔥 Fresh upload!",
    "⚡ Just posted!",
    "🎬 New edit is live!",
    "👀 New video alert!",
    "📲 Straight from TikTok:",
    "💎 Another one!",
    "🆕 Brand new post!",
    "🎥 It's out!",
    "✨ New upload just landed!",
    "📢 Heads up!",
    "🚀 New one is up!",
    "🍿 Grab a snack, new video!",
    "🎯 Fresh off the timeline!",
    "⏱️ Posted minutes ago!",
    "📈 New post incoming!",
    "🔔 Ding! New video!",
    "🧨 Boom, new edit!",
]

BODIES = [
    "{handle} just uploaded with Rapid Quality",
    "{handle} posted a new edit using Rapid Quality",
    "another upload from {handle}, patched with Rapid Quality",
    "{handle} dropped a new one with Rapid Quality on",
    "fresh edit by {handle}, uploaded through Rapid Quality",
    "{handle} is back with a new video, Rapid Quality enabled",
    "new post from {handle} with the extension on",
    "{handle} just hit upload with Rapid Quality",
    "here is the latest from {handle}, posted with Rapid Quality",
    "{handle} shipped a new edit, Rapid Quality did the rest",
    "live proof from {handle}: uploaded with Rapid Quality",
    "{handle} uploaded straight from PC with Rapid Quality",
    "real upload, real account: {handle} with Rapid Quality",
    "{handle} posted again, same extension, same quality",
    "new TikTok from {handle}, sent through Rapid Quality",
    "{handle} went live with a new edit using Rapid Quality",
    "one more for the proof wall: {handle} with Rapid Quality",
    "{handle} just posted, Rapid Quality turned on as always",
    "{handle} uploaded a new edit, no settings, just Rapid Quality",
    "fresh proof from {handle}, posted with Rapid Quality",
]

CLOSERS = [
    "Check the sharpness yourself 👇",
    "Look at that quality 👇",
    "Zoom in, it holds up 👇",
    "Judge the quality yourself 👇",
    "Watch it in full quality 👇",
    "No blur, no mush. See for yourself 👇",
    "This is what an untouched upload looks like 👇",
    "Every frame stays clean 👇",
    "Exactly like the export 👇",
    "Pause on any frame 👇",
    "Fast cuts, still crisp 👇",
    "Detail survived the upload 👇",
    "Same file, same quality, now on TikTok 👇",
    "Tap in and see the difference 👇",
    "Go show some love 👇",
    "Proof is in the pixels 👇",
]


def make_phrase(handle: str, recent: list[str], rng: random.Random | None = None) -> tuple[str, str]:
    """Tire une phrase qui n'est pas dans `recent` (on compare le gabarit, pas le pseudo)."""
    rng = rng or random.Random()
    for _ in range(200):
        o, b, c = rng.choice(OPENERS), rng.choice(BODIES), rng.choice(CLOSERS)
        parts = (OPENERS.index(o), BODIES.index(b), CLOSERS.index(c))
        key = "-".join(map(str, parts))
        # Ni la même phrase sur les 30 dernières, ni le même morceau sur les 5 dernières
        last = [k.split("-") for k in recent[-5:]]
        if key not in recent and not any(str(p) == l[i] for l in last for i, p in enumerate(parts)):
            body = b.format(handle=handle)
            return key, f"{o} {body[0].upper()}{body[1:]}. {c}"
    raise RuntimeError("Plus de phrase disponible (ne devrait jamais arriver)")
