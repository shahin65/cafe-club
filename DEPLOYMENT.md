# cPanel deployment

## Isolated resources

- Domain: `cafeclub.amytisapp.ir`
- Document root: `/home/exmykvwq/cafeclub.amytisapp.ir`
- Python application root: `/home/exmykvwq/cafe-club-app`
- Runtime: Python 3.12.13
- Startup file: `passenger_wsgi.py`; callable: `application`
- New MySQL database and user: `exmykvwq_cafeclub`

The application code, configuration and data fixture must stay outside the
document root. Existing applications and databases use separate paths.

## Configuration and installation

Copy `production.example.json` to `production.json` in the application root.
Replace every placeholder with new private values and restrict the file to the
account owner (`chmod 600 production.json`). This file is excluded from Git and
the deployment bundle. Environment variables override the JSON configuration.
Production settings always disable debug and refuse a missing or development key.

After the Python application is created in cPanel, activate its virtual
environment using the command shown by cPanel. From the application root run:

```text
python -m pip install -r requirements-production.txt
python manage.py migrate --settings=config.production --noinput
python manage.py loaddata _deployment/content.json --settings=config.production
python manage.py collectstatic --settings=config.production --noinput
python manage.py check --deploy --database default --settings=config.production
```

Create the database with `utf8mb4` and give its dedicated user access only to the
new database. The driver is Oracle's MySQL Connector/Python, which provides its
own Django backend and installs without compiling on this hosting account.
The host denies compiler execution, so mysqlclient cannot be built here.
Do not change the other applications' environments.

## Public files and HTTPS

Link `static` in the document root to the application's `staticfiles` directory
and `media` to its `media` directory. Copy `deploy/static.htaccess` into
`staticfiles/.htaccess` and `deploy/media.htaccess` into `media/.htaccess`.
Confirm that directory listing and executable file types are blocked.
Do not place application code, SQLite files, fixtures or `production.json` in the
document root.

Issue/verify an SSL certificate for the new subdomain before enabling public
HTTPS access. The application redirects HTTP to HTTPS and sets secure cookies.
HSTS initially lasts one hour, applies to this hostname only, and is not
preloaded. Django may report advisory HSTS include-subdomain/preload warnings;
these deliberate choices avoid committing to a broader policy during rollout.
Do not trust forwarded protocol headers without verifying the proxy configuration.

Restart only this Python application. Verify HTTPS home, Persian and English
pages, static images, admin login, database migrations and a role-dealing flow.
Create a new administrator interactively; the bundle excludes existing users,
password hashes, sessions and admin logs.

## Content transfer and backup

Run `python scripts/prepare_deployment.py` locally. It creates `_deploy/` with:

- A local SQLite backup (keep this on the local computer).
- A content fixture for banners and scenarios, excluding authentication data.
- `cafe-club-deploy.zip`, containing code, the content fixture and referenced images.
- A size/hash manifest for verifying the uploaded bundle.

Do not load the initial fixture again after administrators start editing live
content: it updates records with matching primary keys. Future releases should
deploy code and migrations without importing the old content fixture.
Back up both the production database and media before future releases.
