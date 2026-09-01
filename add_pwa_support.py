#!/usr/bin/env python3
"""
Cream Daddy PWA Installer

Requirements:
    pip install pillow

Place:
    icon.png
next to:
    index.html
"""

from pathlib import Path
from datetime import datetime
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"
ICON = ROOT / "icon.png"

try:
    from PIL import Image
except Exception:
    print("ERROR: Pillow not installed.")
    print("Run: pip install pillow")
    sys.exit(1)


def fail(msg):
    print("ERROR:", msg)
    sys.exit(1)


if not INDEX.exists():
    fail("index.html not found")

if not ICON.exists():
    fail("icon.png not found beside index.html")

html = INDEX.read_text(encoding="utf-8")

if "manifest.json" in html:
    print("PWA support already appears installed.")
    sys.exit(0)

# --------------------------------------------------
# Backup
# --------------------------------------------------

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = ROOT / f"index-backup-{stamp}.html"
shutil.copy2(INDEX, backup)

# --------------------------------------------------
# Create icon folder
# --------------------------------------------------

icons_dir = ROOT / "assets" / "icons"
icons_dir.mkdir(parents=True, exist_ok=True)

img = Image.open(ICON).convert("RGBA")

sizes = {
    180: "icon-180.png",
    192: "icon-192.png",
    512: "icon-512.png"
}

for size, filename in sizes.items():
    resized = img.resize((size, size))
    resized.save(icons_dir / filename)

# --------------------------------------------------
# Create manifest
# --------------------------------------------------

manifest = {
    "name": "Cream Daddy POS",
    "short_name": "Cream Daddy",
    "start_url": "./",
    "display": "standalone",
    "background_color": "#fabc15",
    "theme_color": "#fabc15",
    "orientation": "portrait",
    "icons": [
        {
            "src": "assets/icons/icon-192.png",
            "sizes": "192x192",
            "type": "image/png"
        },
        {
            "src": "assets/icons/icon-512.png",
            "sizes": "512x512",
            "type": "image/png"
        }
    ]
}

with open(ROOT / "manifest.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

# --------------------------------------------------
# Inject head tags
# --------------------------------------------------

head_insert = """
    manifest.json

    <meta name="theme-color" content="#fabc15">

    <meta name="apple-mobile-web-app-capable" content="yes">

    <meta name="apple-mobile-web-app-status-bar-style"
          content="default">

    <meta name="apple-mobile-web-app-title"
          content="Cream Daddy">

    assets/icons/icon-180.png
"""

if "</head>" not in html:
    fail("Could not locate </head>")

html = html.replace(
    "</head>",
    head_insert + "\n</head>",
    1
)

INDEX.write_text(html, encoding="utf-8")

print("SUCCESS: Cream Daddy PWA support installed.")
print("BACKUP:", backup.name)
print()
print("Created:")
print("  manifest.json")
print("  assets/icons/icon-180.png")
print("  assets/icons/icon-192.png")
print("  assets/icons/icon-512.png")