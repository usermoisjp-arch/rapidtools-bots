"""Giveaways du serveur : tirage à l'heure pile avec une roue animée postée dans #giveaways.

Les giveaways sont listés dans giveaways.json (id, lot, date du tirage, salon et message où l'on réagit 🎉).
Le workflow giveaway.yml tourne toutes les heures ; ce script ne fait rien sauf si un tirage tombe dans les
80 prochaines minutes (ou a été manqué depuis moins de 24 h). Alors il :
  1. poste un rappel dans #general 1 h avant (si le robot a démarré à temps) et dans #giveaways 10 min avant ;
  2. 1 min avant : demande au bot (Vercel, /api/cron) la liste des participants et leurs tickets
     (le token du bot ne quitte pas Vercel ; GitHub n'a que CRON_SECRET) ;
  3. tire le gagnant (secrets.SystemRandom, pondéré par les tickets) et prépare la roue (GIF) ;
  4. à la seconde près : poste la roue, puis le gagnant quand elle s'arrête, marque le message « Ended »,
     annonce le gagnant dans #general et prévient le staff.
Rien de nominatif n'est écrit dans les journaux GitHub (dépôt public) : seulement des nombres.

  python giveaway.py              # mode robot
  python giveaway.py --gif-test   # roue d'essai avec de faux noms -> wheel-test.gif, rien n'est posté
Secrets : CRON_SECRET, DISCORD_GIVEAWAY_WEBHOOK_URL (#giveaways), DISCORD_PROMO_WEBHOOK_URL (#general).
"""
import io
import json
import math
import os
import secrets
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "giveaways.json"
STATE = ROOT / "giveaway_state.json"
POINTS = ROOT / "points.json"
CRON_URL = "https://rapidtools-bot.vercel.app/api/cron"
UA = "rapidtools-bots (github.com/usermoisjp-arch/rapidtools-bots)"
COLORS = [(34, 211, 238), (139, 92, 246), (244, 63, 94), (245, 158, 11), (34, 197, 94), (59, 130, 246)]


def load(p: Path, fallback):
    return json.loads(p.read_text()) if p.exists() else fallback


def http(url: str, data: bytes | None = None, headers: dict | None = None, method: str | None = None) -> bytes:
    for attempt in range(4):
        req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})}, method=method)
        try:
            return urllib.request.urlopen(req, timeout=90).read()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(float(json.loads(e.read() or b"{}").get("retry_after", 1)) + 0.2)
                continue
            raise RuntimeError(f"{method or ('POST' if data else 'GET')} -> {e.code}") from None
    raise RuntimeError("rate limit")


def cron(task: dict) -> dict:
    body = json.dumps(task).encode()
    headers = {"Authorization": f"Bearer {os.environ['CRON_SECRET']}", "Content-Type": "application/json"}
    return json.loads(http(CRON_URL, body, headers))


def webhook(env: str, payload: dict, files: dict | None = None, edit: str | None = None) -> dict:
    url = os.environ[env] + (f"/messages/{edit}" if edit else "?wait=true")
    payload = {"allowed_mentions": {"parse": []}, **payload}
    if not files:
        return json.loads(http(url, json.dumps(payload).encode(), {"Content-Type": "application/json"}, "PATCH" if edit else "POST"))
    boundary = "rt" + secrets.token_hex(12)
    payload["attachments"] = [{"id": i, "filename": n} for i, n in enumerate(files)]
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="payload_json"\r\nContent-Type: application/json\r\n\r\n'.encode() + json.dumps(payload).encode()]
    for i, (name, blob) in enumerate(files.items()):
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="files[{i}]"; filename="{name}"\r\nContent-Type: image/gif\r\n\r\n'.encode() + blob)
    body = b"\r\n".join(parts) + f"\r\n--{boundary}--\r\n".encode()
    return json.loads(http(url, body, {"Content-Type": f"multipart/form-data; boundary={boundary}"}, "PATCH" if edit else "POST"))


def sleep_until(ts: float) -> None:
    while (left := ts - time.time()) > 0:
        time.sleep(min(left, 30))


# ---------- La roue ----------

def font(size: int) -> ImageFont.FreeTypeFont:
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


def label(p: dict) -> str:
    """Nom lisible avec la police de la roue (les emojis et écritures non latines sont retirés)."""
    for raw in (p.get("name"), p.get("username")):
        s = "".join(c for c in str(raw or "") if 32 <= ord(c) < 0x250).strip()
        if len(s) >= 2:
            return s if len(s) <= 20 else s[:19] + "…"
    return "member"


def wheel_image(people: list[dict], size: int) -> tuple[Image.Image, list[tuple[float, float]]]:
    """Roue dessinée à 2x puis réduite (bords lisses). Part de chaque participant proportionnelle à ses tickets.
    Angles en degrés, sens horaire depuis 3 h (convention de Pillow)."""
    big = size * 2
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    total = sum(p["entries"] for p in people)
    spans, a = [], 0.0
    for p in people:
        b = a + 360 * p["entries"] / total
        spans.append((a, b))
        a = b
    pad = 8
    for i, (a, b) in enumerate(spans):
        color = COLORS[i % len(COLORS)] if len(people) % len(COLORS) != 1 or i != len(people) - 1 else COLORS[2]
        d.pieslice((pad, pad, big - pad, big - pad), a, b, fill=color, outline=(15, 16, 24), width=4)
    d.ellipse((pad, pad, big - pad, big - pad), outline=(255, 255, 255), width=10)
    c = big / 2
    r = c - pad
    for p, (a, b) in zip(people, spans):
        span = b - a
        fs = int(max(14, min(44, r * math.radians(span) * 0.55)))
        txt = label(p)
        f = font(fs)
        while f.getlength(txt) > r * 0.62 and fs > 12:
            fs -= 2
            f = font(fs)
        if span < 3:
            continue
        w = int(f.getlength(txt)) + 8
        t = Image.new("RGBA", (w, fs + 12), (0, 0, 0, 0))
        ImageDraw.Draw(t).text((4, 4), txt, font=f, fill="white", stroke_width=3, stroke_fill=(15, 16, 24))
        mid = (a + b) / 2
        # Texte dans l'axe du rayon, lu du centre vers le bord (comme sur une vraie roue)
        rot = t.rotate(-mid, expand=True, resample=Image.BICUBIC)
        dist = r * 0.58
        x = c + dist * math.cos(math.radians(mid)) - rot.width / 2
        y = c + dist * math.sin(math.radians(mid)) - rot.height / 2
        img.alpha_composite(rot, (int(x), int(y)))
    return img.resize((size, size), Image.LANCZOS), spans


def render(people: list[dict], winner: int, title: str, logo: Path | None, fps: int = 20, banner: str = "WINNER") -> tuple[bytes, float]:
    """GIF de la roue qui tourne et s'arrête sur le gagnant. Renvoie (octets, durée de la rotation en s)."""
    W, H, S = 520, 600, 440
    cx, cy = W // 2, 92 + S // 2
    wheel, spans = wheel_image(people, S)
    a, b = spans[winner]
    # Point d'arrivée au hasard dans la part du gagnant (pas toujours pile au milieu)
    stop = a + (b - a) * (0.2 + 0.6 * secrets.randbelow(1000) / 1000)
    # Rotation horaire de θ : l'angle φ passe à φ + θ ; le pointeur est en haut (270°)
    final = 360 * 7 + (270 - stop) % 360
    spin = 7.0
    frames, durations = [], []

    bg = Image.new("RGB", (W, H), (10, 11, 18))
    bd = ImageDraw.Draw(bg)
    bd.text((W // 2, 40), title.upper(), font=font(30), fill="white", anchor="mm")
    bd.text((W // 2, 72), "LIVE DRAW", font=font(16), fill=(245, 158, 11), anchor="mm")
    hub = None
    if logo and logo.exists():
        hub = Image.open(logo).convert("RGB").resize((76, 76))
        m = Image.new("L", (76, 76), 0)
        ImageDraw.Draw(m).ellipse((0, 0, 75, 75), fill=255)
        hub.putalpha(m)

    def frame(theta: float, banner: str | None = None) -> Image.Image:
        im = bg.copy()
        im.paste(wheel.rotate(-theta, resample=Image.BICUBIC), (cx - S // 2, cy - S // 2), wheel.rotate(-theta, resample=Image.BICUBIC))
        dr = ImageDraw.Draw(im)
        dr.ellipse((cx - 44, cy - 44, cx + 44, cy + 44), fill=(10, 11, 18), outline="white", width=4)
        if hub:
            im.paste(hub, (cx - 38, cy - 38), hub)
        top = cy - S // 2
        dr.polygon([(cx - 20, top - 16), (cx + 20, top - 16), (cx, top + 26)], fill="white", outline=(10, 11, 18))
        if banner:
            dr.rounded_rectangle((30, H - 74, W - 30, H - 18), 16, fill=(245, 158, 11))
            dr.text((W // 2, H - 46), banner, font=font(26), fill=(10, 11, 18), anchor="mm")
        return im

    n = int(spin * fps)
    for i in range(n + 1):
        t = i / n
        ease = 1 - (1 - t) ** 4  # démarre vite, ralentit longuement
        frames.append(frame(final * ease))
        durations.append(1000 // fps)
    win = f"{banner}: {label(people[winner])}"
    frames.append(frame(final, win))
    durations.append(60000)  # reste affiché

    pal = frames[-1].quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    buf = io.BytesIO()
    q[0].save(buf, "GIF", save_all=True, append_images=q[1:], duration=durations, optimize=True, disposal=1)
    return buf.getvalue(), spin


# ---------- Tirage ----------

def draw(g: dict, st: dict) -> None:
    t = g["draw"]
    gid = g["id"]
    s = st.setdefault(gid, {})
    ch = f"<#{g['channel']}>"

    if time.time() < t - 3300 and not s.get("reminder_1h"):
        sleep_until(t - 3600)
        webhook("DISCORD_PROMO_WEBHOOK_URL", {"content": f"⏰ **1 hour left** to enter the **{g['prize']}** giveaway. React {g['emoji']} in {ch}, the wheel spins live <t:{t}:t>."})
        s["reminder_1h"] = True
        print("rappel 1 h posté")
    if time.time() < t - 300 and not s.get("reminder_10m"):
        sleep_until(t - 600)
        webhook("DISCORD_GIVEAWAY_WEBHOOK_URL", {"content": f"🎡 The wheel spins in **10 minutes** (<t:{t}:R>). Last chance to react {g['emoji']} on the giveaway above."})
        s["reminder_10m"] = True
        print("rappel 10 min posté")

    sleep_until(t - 60)
    people = cron({"task": "entrants", "channel": g["channel"], "message": g["message"], "emoji": g["emoji"], "state": load(POINTS, {})})["entrants"]
    total = sum(p["entries"] for p in people)
    print(f"{len(people)} participants, {total} tickets")
    if not people:
        sleep_until(t)
        webhook("DISCORD_GIVEAWAY_WEBHOOK_URL", {"content": f"Nobody entered the **{g['prize']}** giveaway, so there is no winner this time."})
        s.update(drawn=int(time.time()), winner=None, participants=0)
        return

    # Tirage pondéré : chaque ticket a la même chance
    pick = secrets.randbelow(total)
    winner = 0
    while pick >= people[winner]["entries"]:
        pick -= people[winner]["entries"]
        winner += 1
    order = people[:]
    secrets.SystemRandom().shuffle(order)
    w = people[winner]
    # Webhook : 10 Mo au plus par fichier. Beaucoup de participants = GIF plus lourd : moins d'images par seconde
    for fps in (20, 14, 10, 7):
        gif, spin = render(order, order.index(w), f"{g['prize']} giveaway", ROOT / "assets/logo.jpeg", fps)
        if len(gif) < 9.5e6:
            break
    print(f"roue prête : {len(gif) // 1024} Ko")

    sleep_until(t)
    webhook("DISCORD_GIVEAWAY_WEBHOOK_URL", {"content": f"🎡 **The wheel is spinning!** {len(people)} participants, {total} entries."}, {"wheel.gif": gif})
    sleep_until(time.time() + spin + 0.5)
    tickets = f"{w['entries']} entr{'ies' if w['entries'] > 1 else 'y'}"
    webhook("DISCORD_GIVEAWAY_WEBHOOK_URL", {
        "content": f"🎉 Congratulations <@{w['id']}>, you won **{g['prize']}**! ({tickets})\nClaim it with **Contact the team** in <#{g['claim_channel']}>.",
        "allowed_mentions": {"users": [w["id"]]},
    })
    s.update(drawn=int(time.time()), winner=w["id"], participants=len(people), entries=total)

    # Message du giveaway : marqué terminé (le webhook peut éditer ses propres messages)
    try:
        msg = json.loads(http(f"{os.environ['DISCORD_GIVEAWAY_WEBHOOK_URL']}/messages/{g['message']}"))
        emb = msg["embeds"][0]
        emb["title"] = f"🎁 GIVEAWAY ENDED: {g['prize']}"
        emb["color"] = 0x64748B
        emb["description"] = f"**Winner: <@{w['id']}>** ({len(people)} participants, {total} entries)\n\n" + emb.get("description", "")
        emb.pop("image", None)
        webhook("DISCORD_GIVEAWAY_WEBHOOK_URL", {"embeds": [emb], "attachments": []}, edit=g["message"])
    except Exception as e:
        print(f"! message du giveaway non modifié : {e}")
    try:
        webhook("DISCORD_PROMO_WEBHOOK_URL", {
            "content": f"🎉 <@{w['id']}> just won **{g['prize']}** in {ch}! More giveaways are coming: chat here to earn XP and extra entries (`/rank`).",
            "allowed_mentions": {"users": [w["id"]]},
        })
    except Exception as e:
        print(f"! annonce #general : {e}")
    try:
        cron({"task": "result", "prize": g["prize"], "winner": w["id"], "participants": len(people), "entries": w["entries"]})
    except Exception as e:
        print(f"! message au staff : {e}")


# ---------- Récompense d'invitations ----------
# points.json > rewards : nombre de tours gagnés par membre (toutes les 15 personnes venues par son lien,
# compté par le bot). giveaway_state.json > spun : tours déjà joués. Chaque tour manquant = une roue des produits.

def reward_spins(st: dict) -> None:
    cfg = load(ROOT / "rewards.json", {})
    earned = load(POINTS, {}).get("rewards", {})
    spun = st.setdefault("spun", {})
    for uid, n in earned.items():
        while spun.get(uid, 0) < n:
            prizes = cfg["prizes"]
            k = secrets.randbelow(len(prizes))
            people = [{"name": p["name"], "entries": 1} for p in prizes]
            gif = b""
            for fps in (20, 14, 10):
                gif, spin = render(people, k, "Invite reward", ROOT / "assets/logo.jpeg", fps, banner="WON")
                if len(gif) < 9.5e6:
                    break
            done = spun.get(uid, 0) + 1
            webhook("DISCORD_GIVEAWAY_WEBHOOK_URL", {
                "content": f"🎡 <@{uid}> brought **{done * cfg['goal']} people** to the server! Spinning the product wheel...",
                "allowed_mentions": {"users": [uid]},
            }, {"wheel.gif": gif})
            time.sleep(spin + 0.5)
            p = prizes[k]
            when = f" It drops <t:{p['release']}:D>, you get it on release day." if p.get("release", 0) > time.time() else ""
            webhook("DISCORD_GIVEAWAY_WEBHOOK_URL", {
                "content": f"🎉 <@{uid}> won **{p['name']}** for free!{when}\nClaim it with **Contact the team** in <#{cfg['claim_channel']}>. The team checks the invites first.",
                "allowed_mentions": {"users": [uid]},
            })
            try:
                cron({"task": "result", "prize": f"{p['name']} (invite reward, {done * cfg['goal']} invites)", "winner": uid, "participants": 0, "entries": 1})
            except Exception as e:
                print(f"! message au staff : {e}")
            spun[uid] = done
            STATE.write_text(json.dumps(st, indent=2) + "\n")
            print("1 tour de roue d'invitations joué")


def main() -> None:
    if "--gif-test" in sys.argv:
        fake = [{"id": str(i), "name": n, "entries": e} for i, (n, e) in enumerate([("Nora", 1), ("Pce.aep", 2), ("Ryn", 1), ("TERMINATOR", 3), ("alex_edits", 1), ("Ma😀rco", 1), ("kaiedits.ae", 2), ("Lina", 1), ("vfx.sam", 1), ("ゆき", 1)])]
        for p in fake:
            p["username"] = "yuki" if p["name"] == "ゆき" else p["name"]
        gif, _ = render(fake, 3, "RapidCc's giveaway", ROOT / "assets/logo.jpeg")
        (ROOT / "wheel-test.gif").write_bytes(gif)
        prizes = [{"name": p["name"], "entries": 1} for p in load(ROOT / "rewards.json", {})["prizes"]]
        (ROOT / "wheel-test-rewards.gif").write_bytes(render(prizes, 3, "Invite reward", ROOT / "assets/logo.jpeg", banner="WON")[0])
        print(f"wheel-test.gif : {len(gif) // 1024} Ko")
        return

    st = load(STATE, {})
    try:
        reward_spins(st)
    except Exception as e:
        print(f"! roue d'invitations : {e}")
    finally:
        STATE.write_text(json.dumps(st, indent=2) + "\n")
    now = time.time()
    due = [g for g in load(CONFIG, []) if not st.get(g["id"], {}).get("drawn") and g.get("message") and -86400 < g["draw"] - now < 80 * 60]
    if not due:
        print("aucun tirage dans les 80 prochaines minutes")
        return
    g = min(due, key=lambda x: x["draw"])
    try:
        draw(g, st)
    finally:
        STATE.write_text(json.dumps(st, indent=2) + "\n")


if __name__ == "__main__":
    main()
