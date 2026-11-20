from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


CORS_RULES = {
    "CORSRules": [
        {
            "AllowedOrigins": [
                "https://cafeclub.amytisapp.ir",
                "http://cafeclub.amytisapp.ir",
                "http://127.0.0.1:8000",
                "http://localhost:8000",
            ],
            "AllowedMethods": ["GET", "HEAD"],
            "AllowedHeaders": ["*", "Range"],
            "ExposeHeaders": [
                "ETag",
                "Content-Length",
                "Content-Type",
                "Accept-Ranges",
                "Content-Range",
            ],
            "MaxAgeSeconds": 86400,
        }
    ]
}


class Command(BaseCommand):
    help = "اعمال CORS روی صندوقچه آروان کافه کلاب."

    def handle(self, *args, **options):
        if not getattr(settings, "ARVAN_MEDIA_ENABLED", False):
            raise CommandError("آروان فعال نیست. کلیدها را در فایل .env بگذار.")
        import boto3
        from botocore.client import Config

        client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            region_name=settings.AWS_S3_REGION_NAME,
            config=Config(signature_version="s3v4", s3={"addressing_style": settings.AWS_S3_ADDRESSING_STYLE}),
        )
        client.put_bucket_cors(Bucket=settings.AWS_STORAGE_BUCKET_NAME, CORSConfiguration=CORS_RULES)
        self.stdout.write(self.style.SUCCESS(f"CORS روی صندوقچه {settings.AWS_STORAGE_BUCKET_NAME} اعمال شد."))
