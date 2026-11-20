"""One-off shrink of oversized static icons and local seed banners."""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
SKIP_NAMES = {"favicon.ico"}
SKIP_PREFIX = ()


def max_side(path: Path) -> int:
    name = path.name.lower()
    if name in {"pwa-512.png", "pwa-192.png"}:
        return 512 if "512" in name else 192
    if name == "logo.png":
        return 192
    if name.startswith("logo-"):
        return 256
    if name.startswith("card-") or name == "background.webp":
        return 1280
    if "banner" in name:
        return 1200
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        return 720
    return 128


def should_skip(path: Path) -> bool:
    if path.name.lower() in SKIP_NAMES:
        return True
    return False


def save_image(im: Image.Image, path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        im.convert("RGB").save(path, "JPEG", quality=78, optimize=True, progressive=True)
        return
    if suffix == ".webp":
        im.save(path, "WEBP", quality=72, method=6)
        return
    if im.mode not in {"RGB", "RGBA"}:
        im = im.convert("RGBA")
    im.save(path, "PNG", optimize=True, compress_level=9)


def compress_file(path: Path) -> str:
    before = path.stat().st_size
    with Image.open(path) as src:
        im = src.copy()
    side = max_side(path)
    im.thumbnail((side, side), Image.Resampling.LANCZOS)
    save_image(im, path)
    after = path.stat().st_size
    return f"{path.relative_to(ROOT)} {before} -> {after}"


def iter_targets():
    for path in STATIC.iterdir():
        if not path.is_file() or should_skip(path):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            yield path
    media = ROOT / "media"
    if not media.is_dir():
        return
    for folder in ("banners", "event_ads"):
        root = media / folder
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                if "banner" in path.name.lower() or path.parent.name in {"banners", "event_ads"}:
                    yield path


def main():
    for path in iter_targets():
        try:
            print(compress_file(path))
        except Exception as exc:
            print(f"SKIP {path}: {exc}")


if __name__ == "__main__":
    main()
