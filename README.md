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

## XP et classement (points.py)

`.github/workflows/points.yml`, toutes les 10 min : `points.py` envoie `points.json` au bot (Vercel, `/api/cron`), qui relit les nouveaux messages des salons de discussion, compte l'XP (+5 par message, une fois par minute ; +2 pour une réponse à quelqu'un ; +10 pour le premier message du jour ; staff exclu), donne les rôles Level 5/10/20/30, annonce les passages de niveau dans #general et met à jour #leaderboard. Le nouvel état revient ici et est commité. Le token du bot reste sur Vercel. Secret : `CRON_SECRET` (même valeur que sur Vercel). Code : `bot/lib/community.js` du projet RapidTools.

## Giveaways (giveaway.py)

`giveaways.json` liste les giveaways (lot, `draw` en timestamp Unix, salon et message où réagir 🎉, salon où réclamer le lot). `.github/workflows/giveaway.yml` tourne toutes les heures à :45 et ne fait rien sauf si un tirage tombe dans les 80 min. Alors : rappel dans #general 1 h avant, dans #giveaways 10 min avant, liste des participants demandée au bot 1 min avant (1 ticket, 2 au niveau 5, 3 au niveau 10), tirage `secrets`, roue GIF postée à la seconde près, gagnant annoncé quand elle s'arrête, message du giveaway marqué terminé, staff prévenu dans #staff-chat. État : `giveaway_state.json`. Secrets : `CRON_SECRET`, `DISCORD_GIVEAWAY_WEBHOOK_URL`, `DISCORD_PROMO_WEBHOOK_URL`.

- Nouveau giveaway : poster son message dans #giveaways (`config/site.json` > giveaways puis `npm run messages -- giveaways` dans RapidTools), ajouter la réaction 🎉, puis une entrée dans `giveaways.json` avec l'ID du message.
- Voir la roue sans rien poster : `python giveaway.py --gif-test` (crée `wheel-test.gif`).
