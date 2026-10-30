from django.core.management.base import BaseCommand

from assistant.defaults import ensure_policies
from assistant.jobs import retry_failed_reports, run_hourly, send_periodic_report


class Command(BaseCommand):
    help = "بررسی ساعتی موارد جدید دستیار یا ارسال گزارش ۱۲ساعته بله"

    def add_arguments(self, parser):
        parser.add_argument("--report", action="store_true", help="ارسال گزارش ۱۲ساعته به بله")
        parser.add_argument("--retry-reports", action="store_true", help="تلاش مجدد گزارش‌های ارسال‌نشده")

    def handle(self, *args, **options):
        ensure_policies()
        if options["retry_reports"]:
            retried = retry_failed_reports()
            self.stdout.write(f"retried={len(retried)}")
            return
        if options["report"]:
            result = send_periodic_report()
            self.stdout.write(str(result))
            return
        result = run_hourly()
        self.stdout.write(str(result))
