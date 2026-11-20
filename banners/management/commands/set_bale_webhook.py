"""Set or delete the Bale bot webhook on the public site URL."""
from django.core.management.base import BaseCommand, CommandError

from banners.bale import api, delete_webhook, set_webhook, webhook_url


class Command(BaseCommand):
    help = "Set Bale webhook on the public site URL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            default="",
            help="Override webhook URL. Defaults to BALE_WEBHOOK_URL or PUBLIC_SITE_URL.",
        )
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Remove the webhook instead of setting it.",
        )

    def handle(self, *args, **options):
        if options["delete"]:
            result = delete_webhook()
            self._report(result, "Webhook deleted.")
            return
        target = (options.get("url") or webhook_url()).strip()
        if not target:
            from django.conf import settings

            from banners.bale import public_site_url, webhook_secret

            site = public_site_url()
            secret = webhook_secret()
            if site and secret:
                target = f"{site}/auth/bale/webhook/{secret}/"
        if not target:
            raise CommandError(
                "Set BALE_WEBHOOK_URL, or PUBLIC_SITE_URL and BALE_WEBHOOK_SECRET, or pass --url."
            )
        result = set_webhook(target)
        self._report(result, f"Webhook set to {target}")
        info = api("getWebhookInfo")
        description = info.get("description") or info.get("result") or info
        self.stdout.write(self.style.NOTICE(str(description)))

    def _report(self, result: dict, success_message: str):
        if not result.get("ok"):
            raise CommandError(result.get("description") or "Bale API call failed.")
        self.stdout.write(self.style.SUCCESS(success_message))
