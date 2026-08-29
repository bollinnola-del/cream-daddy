#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime
import shutil
import sys

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "index.html"

if not HTML.exists():
    print("ERROR: index.html not found")
    sys.exit(1)

original = HTML.read_text(encoding="utf-8")

target = """
        <div class="card-header-row">
            <div class="card-title">Select Flavor</div>
            <button class="btn-primary" onclick="openModal('flavor-modal')">+ Add Flavor</button>
        </div>
        <div id="register-flavors-grid" class="grid-flavors"></div>
"""

replacement = """
        <div id="register-flavors-grid" class="grid-flavors"></div>

        <button
            class="btn-primary"
            style="
                width:100%;
                margin-top:12px;
            "
            onclick="openModal('flavor-modal')"
        >
            + Add Flavor
        </button>
"""

if target not in original:
    print("ERROR: Could not find the Select Flavor block.")
    print("No changes made.")
    sys.exit(1)

updated = original.replace(target, replacement)

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = ROOT / f"index-backup-{stamp}.html"

shutil.copy2(HTML, backup)

HTML.write_text(updated, encoding="utf-8")

print("SUCCESS")
print(f"Backup created: {backup.name}")
print("Select Flavor header removed.")
print("Add Flavor button moved below flavor list.")