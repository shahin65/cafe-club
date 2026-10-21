"""Build a private upload bundle, excluding local accounts and credentials."""

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"

import django

django.setup()

from django.conf import settings
from django.core import serializers
from banners.models import Banner
from scenarios.models import FinalMoveCard, Role, Scenario, ScenarioSize


def main():
    output = ROOT / "_deploy"
    output.mkdir(exist_ok=True)
    database_path = Path(settings.DATABASES["default"]["NAME"])
    with sqlite3.connect(f"{database_path.as_uri()}?mode=ro", uri=True) as source:
        with sqlite3.connect(output / "local-backup.sqlite3") as backup:
            source.backup(backup)

    models = [Banner, Scenario, ScenarioSize, Role, FinalMoveCard]
    objects = [obj for model in models for obj in model.objects.order_by("pk")]
    fixture = serializers.serialize("json", objects, indent=2)
    (output / "content.json").write_text(fixture, encoding="utf-8")

    media_root = Path(settings.MEDIA_ROOT).resolve()
    media_paths = set()
    for obj in objects:
        for field in obj._meta.fields:
            if field.get_internal_type() not in {"FileField", "ImageField"}:
                continue
            field_file = getattr(obj, field.name)
            if not field_file:
                continue
            path = (media_root / field_file.name).resolve()
            if not path.is_relative_to(media_root) or not path.is_file():
                raise ValueError(f"Missing or invalid media path for {obj._meta.label}:{obj.pk}")
            if path.suffix.lower() not in {".webp", ".png", ".jpg", ".jpeg", ".gif", ".avif"}:
                raise ValueError("Review the media type before uploading it.")
            media_paths.add(path)

    result = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
    )
    code_paths = [ROOT / p.decode("utf-8") for p in result.split(b"\0") if p]
    bundle = output / "cafe-club-deploy.zip"
    with ZipFile(bundle, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(code_paths):
            relative = path.relative_to(ROOT)
            if relative.parts[0] in {".git", ".venv", "_deploy", "media", "staticfiles"}:
                raise ValueError("Private or generated directory in the code manifest.")
            if path.name == "production.json" or path.name.startswith(".env"):
                raise ValueError("Private configuration in the code manifest.")
            if path.suffix.lower() in {".sqlite3", ".pem", ".key"}:
                raise ValueError("Private file in the code manifest.")
            archive.write(path, relative.as_posix())
        archive.writestr("_deployment/content.json", fixture)
        for path in sorted(media_paths):
            archive.write(path, "media/" + path.relative_to(media_root).as_posix())

    with bundle.open("rb") as bundle_file:
        checksum = hashlib.file_digest(bundle_file, "sha256").hexdigest()
    manifest = {
        "archive": bundle.name,
        "bytes": bundle.stat().st_size,
        "sha256": checksum,
        "code_files": len(code_paths),
        "media_files": len(media_paths),
        "content": {model.__name__: model.objects.count() for model in models},
        "includes_accounts": False,
        "includes_credentials": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
