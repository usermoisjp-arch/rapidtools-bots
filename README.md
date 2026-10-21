# tiktok-watch

Poste automatiquement chaque nouvelle vidéo TikTok des comptes listés dans `accounts.txt`
dans le salon #live-proof du serveur Discord RapidTools, avec une phrase différente à chaque fois
(`phrases.py`, des milliers de combinaisons).

- Tourne sur GitHub Actions toutes les 10 minutes (`.github/workflows/watch.yml`).
- Secret GitHub requis : `DISCORD_WEBHOOK_URL` (webhook du salon #live-proof).
- Ajouter un compte : une ligne dans `accounts.txt`. Ses vidéos existantes sont mémorisées sans annonce.
- Test local : `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python watch.py --dry`

## Messages dans #general (promo.py)

`.github/workflows/promo.yml` tourne toutes les heures ; `promo.py` poste un message toutes les 6 à 12 h (tiré au hasard), entre 13 h et 23 h UTC, jamais le même sur les 25 derniers. Environ un tiers des messages montrent une des 5 dernières vidéos de @snzzedit. Chaque message a un bouton « Get Rapid Quality ». Secret : `DISCORD_PROMO_WEBHOOK_URL` (webhook de #general). État : `promo_state.json`.

- Ajouter ou changer un message : listes `VIDEO`, `PRICE`, `NUDGE`, `REVIEWS` en haut de `promo.py` (anglais, ton naturel, rien d'inventé).
- Tester : `python promo.py --dry`. Poster tout de suite : `python promo.py --now` (avec le secret en variable d'environnement).

## Annonces @everyone dans #announcements (announce.py)

Même workflow (`promo.yml`). Une annonce tous les 4 à 7 jours, entre 17 h et 20 h UTC, avec un visuel : comparatif sans/avec (`assets/before-after.jpg`, fait à partir des images du site), image du site, ou miniature d'une vidéo récente de @snzzedit (seulement si elle est assez claire). 6 annonces (`ANNOUNCEMENTS` en haut du fichier), jamais l'une des 3 précédentes. Secret : `DISCORD_ANNOUNCE_WEBHOOK_URL`. État : `announce_state.json`.

- Tester sans ping dans #staff-chat : `DISCORD_TEST_WEBHOOK_URL=... python announce.py --test --key video`.

- Vidéos à exclure : variable GitHub `BANNED_IDS` (privée) ; en local `banned.txt` (ignoré par git).
