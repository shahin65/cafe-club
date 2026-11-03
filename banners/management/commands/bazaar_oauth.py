from django.core.management.base import BaseCommand, CommandError

from banners.gateways import _json_body, _request, _store_bazaar_refresh_token


class Command(BaseCommand):
    help = "Exchange a Cafe Bazaar authorization code for a refresh token and store it."

    def add_arguments(self, parser):
        parser.add_argument("--code", required=True, help="authorization code from the Bazaar redirect")
        parser.add_argument("--redirect-uri", required=True, help="exact Redirect URI registered on the Bazaar client")

    def handle(self, *args, **options):
        from django.conf import settings

        client_id = str(getattr(settings, "BAZAAR_CLIENT_ID", "") or "").strip()
        client_secret = str(getattr(settings, "BAZAAR_CLIENT_SECRET", "") or "").strip()
        if not client_id or not client_secret:
            raise CommandError("Set BAZAAR_CLIENT_ID and BAZAAR_CLIENT_SECRET first.")
        _status, raw = _request(
            "https://pardakht.cafebazaar.ir/devapi/v2/auth/token/",
            data={
                "grant_type": "authorization_code",
                "code": options["code"].strip(),
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": options["redirect_uri"].strip(),
            },
        )
        data = _json_body(raw)
        refresh = (data.get("refresh_token") or "").strip()
        access = (data.get("access_token") or "").strip()
        if not refresh:
            raise CommandError("Bazaar did not return a refresh_token.")
        _store_bazaar_refresh_token(refresh)
        self.stdout.write(self.style.SUCCESS("Cafe Bazaar refresh token stored."))
        if access:
            self.stdout.write("Access token received; it is not printed.")
