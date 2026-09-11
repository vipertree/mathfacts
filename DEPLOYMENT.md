# Deploying Math Facts

Live at **https://adderoaks.com/mathfacts/** — a path-prefix mount on the
adderoaks vhost, gunicorn on `127.0.0.1:8006`, Postgres database `mathfacts`.
Same shape as outrangeous / imitation / frogracer.

## First-run: create your admin account

Students are created by an admin and there is **no self-signup**, so the very
first account has to be made on the server. SSH in and run:

```bash
ssh deploy@91.98.21.156
cd /home/deploy/mathfacts
set -a; . ./.env; set +a          # load production settings + DATABASE_URL
./venv/bin/python manage.py createsuperuser
```

It will prompt for a username and password (leave the email blank — it is
optional and unused). Then log in at
**https://adderoaks.com/mathfacts/** and you will see **Manage students** and
**Django admin** in the top bar.

From *Manage students* you can add each student, tick which of the four
operations they practise, and reset their passwords. Nothing else needs the
command line.

> Sourcing `.env` first is load-bearing. `manage.py` defaults to
> `config.settings.development`, so a bare `manage.py createsuperuser` writes
> to the local sqlite file instead of Postgres and the account will not exist
> on the site.

## Routine updates

Run on the server as `deploy@`:

```bash
cd /home/deploy/mathfacts
git pull
set -a; . ./.env; set +a
./venv/bin/pip install -r requirements.txt
./venv/bin/python manage.py migrate
./venv/bin/python manage.py collectstatic --noinput
./venv/bin/python manage.py seed_facts        # only if the fact domain changed
sudo systemctl restart mathfacts
```

`seed_facts` is idempotent and safe to rerun. Rerun it after changing
`MUL_MAX`, `stage_for`, `strategy_for` or the batch ordering — it re-tags every
fact in place, and `intro_order` is generated from a fixed seed so a rerun
never renumbers the sequence out from under students mid-learning.

## What is where

| Thing | Location |
|---|---|
| Code | `/home/deploy/mathfacts` (clone of `vipertree/mathfacts`, branch `main`) |
| Secrets | `/home/deploy/mathfacts/.env`, mode 600 |
| Virtualenv | `/home/deploy/mathfacts/venv` |
| Static files | `/home/deploy/mathfacts/staticfiles` (world-readable; nginx serves these) |
| Service | `mathfacts.service`, gunicorn 3 workers on `127.0.0.1:8006` |
| Database | Postgres `mathfacts`, role `mathfacts` |
| Nginx | two blocks in `/etc/nginx/sites-enabled/adderoaks.com` |
| Logs | `sudo journalctl -u mathfacts -f` |

## Things that bite

- **Source `.env` before any `manage.py` command.** Without it you are in
  development settings: sqlite instead of Postgres, and `collectstatic` writes
  plain (unhashed) files that the production manifest storage cannot serve —
  every page then 500s. Recover with `collectstatic --clear --noinput` after
  sourcing `.env`.
- **`collectstatic` fails hard on a missing CSS `url()` target.** Manifest
  storage resolves every reference, so an "optional" image referenced from a
  theme stylesheet is not optional. Each theme therefore ships a 1×1
  transparent `static/drill/themes/<key>/background.webp`; overwrite one with
  real art and it just appears. `drill/tests/test_themes.py` fails if a
  reference has no file behind it.
- **nginx needs to traverse the project directory.** After a fresh clone under
  a tight umask the root is 700 and nginx 403s on static:
  `chmod o+x /home/deploy/mathfacts && chmod -R go+rX /home/deploy/mathfacts/staticfiles`.
- **Keep nginx backups out of `sites-enabled/`.** nginx loads every file in
  that directory, so a `.bak` copy means duplicate `listen` directives and a
  failed reload. Backups belong in `/etc/nginx/backups/`.
- **Generate secrets on the server, alphanumeric only.** A `#` in a value
  silently truncates it when `.env` is sourced — an empty `SECRET_KEY` 500s
  every POST.
- There is deliberately **no card on `/games`**. `/games` links party games;
  this is a school tool. Add one later by putting
  `mathfactsscreencap.{png,webp}` in the adderoaks repo with a row in its
  `optimize-images.py`, plus a tile in `games/index.html`.
