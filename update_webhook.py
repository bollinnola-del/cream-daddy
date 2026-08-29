#!/usr/bin/env python3
from pathlib import Path
import re
import shutil
import sys
from datetime import datetime

NEW_WEBHOOK = "https://script.google.com/macros/s/AKfycbxgCmXizdbMFcxaWJQbo0kX29JGy5Lhq-sccW7orquhq1zHYbo1hCI3XOtQ1x2BvUjt/exec"
HTML_FILE = Path(__file__).resolve().parent / "index.html"

if not HTML_FILE.exists():
    print(f"ERROR: index.html was not found in: {HTML_FILE.parent}")
    print("Put update_webhook.py in the same folder as index.html, then run it again.")
    sys.exit(1)

html = HTML_FILE.read_text(encoding="utf-8")
pattern = re.compile(r'(const\s+HARDCODED_WEBHOOK\s*=\s*)[\'\"][^\'\"]+[\'\"]\s*;')
matches = list(pattern.finditer(html))

if len(matches) == 0:
    print("ERROR: Could not find: const HARDCODED_WEBHOOK = \"...\";")
    print("No changes were made.")
    sys.exit(1)

if len(matches) > 1:
    print(f"ERROR: Found {len(matches)} HARDCODED_WEBHOOK declarations. Expected exactly 1.")
    print("No changes were made so the wrong section is not edited.")
    sys.exit(1)

current_line = matches[0].group(0)
if NEW_WEBHOOK in current_line:
    print("No update needed. index.html already contains the new webhook URL.")
    sys.exit(0)

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = HTML_FILE.with_name(f"index-backup-{stamp}.html")
shutil.copy2(HTML_FILE, backup)

updated, count = pattern.subn(rf'\1"{NEW_WEBHOOK}";', html, count=1)
if count != 1:
    print("ERROR: The webhook replacement did not complete. No changes were saved.")
    sys.exit(1)

HTML_FILE.write_text(updated, encoding="utf-8")

verification = HTML_FILE.read_text(encoding="utf-8")
if NEW_WEBHOOK not in verification:
    shutil.copy2(backup, HTML_FILE)
    print("ERROR: Verification failed. The original index.html was restored.")
    sys.exit(1)

print("SUCCESS: Updated the webhook in index.html")
print(f"BACKUP: {backup.name}")
print(f"NEW URL: {NEW_WEBHOOK}")
