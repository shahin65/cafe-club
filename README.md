# Cafe Club

Django website with Persian/English pages, banner administration, game scenarios,
and session-based role dealing.

## Local development

Use Python 3.12 and install the pinned dependencies:

```text
python -m venv .venv
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Activate the virtual environment before running the pip and Django commands.
The local database is SQLite (`db.sqlite3`). Existing database contents and
uploaded media are intentionally excluded from Git; back them up separately.
Initial banner images are included in `banners/seed_images` and restored by
the banner data migration.

## Configuration

Set environment variables in the shell or hosting panel:

- `DJANGO_DEBUG`: defaults to `true` for local development; set to `false` on a server.
- `DJANGO_SECRET_KEY`: a private random key; required when debug is disabled.
- `DJANGO_ALLOWED_HOSTS`: comma-separated hostnames; defaults to `127.0.0.1,localhost`.

The fallback development key is public and is not suitable for deployment.
Changing the key invalidates existing signed sessions. `.env` files are ignored
by Git but are not automatically loaded by this application.

## Validation

```text
python manage.py check
python manage.py test
```

## Deployment status

Production deployment still needs database configuration, HTTPS/cookie settings,
static/media serving, backups, and a WSGI entry point for the hosting environment.
The current WSGI application is `config.wsgi.application`.
Run `python manage.py check --deploy` with production settings before publishing.
Do not upload `.venv`, database backups, `.env` files, or private keys to GitHub.
