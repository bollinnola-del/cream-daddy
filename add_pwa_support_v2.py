#!/usr/bin/env python3
"""Production-ready Cream Daddy PWA icon and manifest installer.

Place this script, icon.png, and index.html in the same project folder.
Requires Pillow: python3 -m pip install pillow
"""
from pathlib import Path
from datetime import datetime
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"
SOURCE_ICON = ROOT / "icon.png"
MANIFEST = ROOT / "manifest.json"
ICONS_DIR = ROOT / "assets" / "icons"


def fail(message):
    print(f"ERROR: {message}")
    print("No project files were changed.")
    sys.exit(1)


try:
    from PIL import Image
except ImportError:
    fail("Pillow is not installed. Run: python3 -m pip install pillow")

if not INDEX.exists():
    fail(f"index.html was not found in {ROOT}")
if not SOURCE_ICON.exists():
    fail(f"icon.png was not found in {ROOT}")

html_original = INDEX.read_text(encoding="utf-8")
if "<!-- Cream Daddy PWA -->" in html_original:
    print("No update needed. Cream Daddy PWA support is already installed.")
    sys.exit(0)
if html_original.count("</head>") != 1:
    fail("Expected exactly one </head> tag in index.html")

# Validate the source image before creating any output.
try:
    with Image.open(SOURCE_ICON) as source:
        source.load()
        width, height = source.size
        if width != height:
            fail(f"icon.png must be square. Current dimensions: {width}x{height}")
        if width < 512:
            fail(f"icon.png must be at least 512x512. Current dimensions: {width}x{height}")
        master = source.convert("RGBA")
except Exception as exc:
    fail(f"icon.png could not be opened: {exc}")

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
index_backup = ROOT / f"index-backup-{stamp}.html"
manifest_backup = ROOT / f"manifest-backup-{stamp}.json"

# Prepare all new content in memory first.
pwa_head = '''    <!-- Cream Daddy PWA -->
    <link rel="manifest" href="./manifest.json">
    <meta name="theme-color" content="#fabc15">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="Cream Daddy">
    <link rel="apple-touch-icon" sizes="180x180" href="./assets/icons/icon-180.png">
    <link rel="icon" type="image/png" sizes="32x32" href="./assets/icons/icon-32.png">
    <link rel="icon" type="image/png" sizes="192x192" href="./assets/icons/icon-192.png">
'''
html_updated = html_original.replace("</head>", pwa_head + "</head>", 1)

manifest_data = {
    "id": "./",
    "name": "Cream Daddy POS",
    "short_name": "Cream Daddy",
    "description": "Cream Daddy point-of-sale and inventory app",
    "start_url": "./",
    "scope": "./",
    "display": "standalone",
    "display_override": ["standalone", "minimal-ui"],
    "orientation": "portrait",
    "background_color": "#fabc15",
    "theme_color": "#fabc15",
    "icons": [
        {
            "src": "./assets/icons/icon-192.png",
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "any"
        },
        {
            "src": "./assets/icons/icon-512.png",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "any"
        },
        {
            "src": "./assets/icons/icon-maskable-512.png",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "maskable"
        }
    ]
}

# Back up existing files immediately before writing.
shutil.copy2(INDEX, index_backup)
if MANIFEST.exists():
    shutil.copy2(MANIFEST, manifest_backup)

try:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)

    # Use high-quality downsampling. The supplied 1024px square art already
    # includes a solid background and ample central composition.
    resampling = getattr(Image, "Resampling", Image).LANCZOS
    sizes = {
        "icon-32.png": 32,
        "icon-180.png": 180,
        "icon-192.png": 192,
        "icon-512.png": 512,
        "icon-maskable-512.png": 512,
    }
    for filename, size in sizes.items():
        output = master.resize((size, size), resampling)
        output.save(ICONS_DIR / filename, format="PNG", optimize=True)

    MANIFEST.write_text(
        json.dumps(manifest_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    INDEX.write_text(html_updated, encoding="utf-8")

    # Validate generated files and references.
    json.loads(MANIFEST.read_text(encoding="utf-8"))
    required_files = [MANIFEST] + [ICONS_DIR / name for name in sizes]
    missing = [str(path.relative_to(ROOT)) for path in required_files if not path.exists()]
    if missing:
        raise RuntimeError("Missing generated files: " + ", ".join(missing))

    final_html = INDEX.read_text(encoding="utf-8")
    for marker in [
        '<link rel="manifest" href="./manifest.json">',
        'rel="apple-touch-icon"',
        'name="theme-color"',
    ]:
        if marker not in final_html:
            raise RuntimeError(f"index.html validation failed for: {marker}")

except Exception as exc:
    # Restore prior index/manifest and remove only files generated by this run.
    shutil.copy2(index_backup, INDEX)
    if manifest_backup.exists():
        shutil.copy2(manifest_backup, MANIFEST)
    elif MANIFEST.exists():
        MANIFEST.unlink()
    for filename in ["icon-32.png", "icon-180.png", "icon-192.png", "icon-512.png", "icon-maskable-512.png"]:
        path = ICONS_DIR / filename
        if path.exists():
            path.unlink()
    fail(f"PWA installation failed and backups were restored: {exc}")

print("SUCCESS: Cream Daddy PWA support installed.")
print(f"SOURCE ICON: {width}x{height} icon.png")
print(f"BACKUP: {index_backup.name}")
if manifest_backup.exists():
    print(f"MANIFEST BACKUP: {manifest_backup.name}")
print("CREATED:")
print("  - manifest.json")
print("  - assets/icons/icon-32.png")
print("  - assets/icons/icon-180.png")
print("  - assets/icons/icon-192.png")
print("  - assets/icons/icon-512.png")
print("  - assets/icons/icon-maskable-512.png")
print("UPDATED:")
print("  - index.html PWA and Apple home-screen metadata")
print("NEXT: Test locally, then commit index.html, manifest.json, assets/icons, and this patch.")
