#!/usr/bin/env python3
"""Migrate Cream Daddy Venue Manager V4 to the shared Google Sheet venue catalog.

Expected state:
- update_venue_manager_v4.py has already modified index.html.
- Code.gs shared venue catalog backend is already deployed.

This patch:
- Keeps the existing V4 venue modal/dropdown UI.
- Removes V4 localStorage venue catalog behavior.
- Uses STATE.venues returned by pull_all.
- Sends add_venue/remove_venue actions to Apps Script.
- Keeps historical Sales Log rows untouched.
- Keeps the venue date defaulted to today's local date whenever opened.
"""
from pathlib import Path
from datetime import datetime
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "index.html"
OLD_MARKER = "// Cream Daddy Venue Manager V4"
NEW_MARKER = "// Cream Daddy Shared Venue Catalog Frontend V2"


def fail(message):
    print("ERROR:", message)
    print("No changes were saved.")
    sys.exit(1)


def matching_brace(source, opening):
    depth = 0
    quote = None
    escaped = False
    line_comment = False
    block_comment = False
    i = opening
    while i < len(source):
        c = source[i]
        n = source[i + 1] if i + 1 < len(source) else ""
        if line_comment:
            if c == "\n":
                line_comment = False
        elif block_comment:
            if c == "*" and n == "/":
                block_comment = False
                i += 1
        elif quote:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == quote:
                quote = None
        else:
            if c == "/" and n == "/":
                line_comment = True
                i += 1
            elif c == "/" and n == "*":
                block_comment = True
                i += 1
            elif c in ("'", '"', "`"):
                quote = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    fail("Could not match a JavaScript closing brace.")


def named_range(source, name):
    match = re.search(rf"function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", source)
    if not match:
        fail(f"Could not find {name}().")
    opening = source.find("{", match.start())
    return match.start(), matching_brace(source, opening) + 1


def assigned_range(source, name):
    match = re.search(rf"window\.{re.escape(name)}\s*=\s*(?:async\s+)?function\s*\([^)]*\)\s*\{{", source)
    if not match:
        fail(f"Could not find window.{name}().")
    opening = source.find("{", match.start())
    closing = matching_brace(source, opening)
    end = closing + 1
    while end < len(source) and source[end] in " \t":
        end += 1
    if end < len(source) and source[end] == ";":
        end += 1
    return match.start(), end


def replace_named(source, name, replacement):
    a, b = named_range(source, name)
    return source[:a] + replacement + source[b:]


def replace_assigned(source, name, replacement):
    a, b = assigned_range(source, name)
    return source[:a] + replacement + source[b:]


if not TARGET.exists():
    fail("index.html was not found. Put this script beside index.html.")

original = TARGET.read_text(encoding="utf-8")
html = original

if NEW_MARKER in html:
    print("No update needed. Shared Venue Catalog Frontend V2 is already installed.")
    sys.exit(0)

for required in [
    OLD_MARKER,
    'id="venue-select"',
    'id="new-venue-input"',
    'id="remove-venue-button"',
    "function getAvailableVenues()",
    "window.removeSelectedVenue = function",
    "window.saveVenue = function",
    "window.openModal = function",
    "sendSheetPayload(payloadObj)",
]:
    if required not in html:
        fail(f"Expected V4 frontend code is missing: {required}")

# 1. Add shared venues to STATE.
if re.search(r"\n\s*venues:\s*\[\],", html):
    pass
else:
    state_anchor = "            transactions: [],"
    if html.count(state_anchor) != 1:
        fail("Could not uniquely locate STATE.transactions.")
    html = html.replace(state_anchor, state_anchor + "\n            venues: [],", 1)

# 2. Capture venues returned by pull_all.
sync_anchor = """                if (Array.isArray(data.transactions)) {
                    STATE.transactions = data.transactions;
                }"""
if "STATE.venues = data.venues" not in html:
    if html.count(sync_anchor) != 1:
        fail("Could not uniquely locate the pull_all transaction response handler.")
    html = html.replace(
        sync_anchor,
        sync_anchor + """
                if (Array.isArray(data.venues)) {
                    STATE.venues = data.venues;
                }""",
        1,
    )

# 3. Remove V4 local venue storage declarations.
html = re.sub(r"\n\s*const VENUE_LOCAL_KEY = 'cream_daddy_local_venues';", "", html, count=1)
html = re.sub(r"\n\s*const VENUE_HIDDEN_KEY = 'cream_daddy_hidden_venues';", "", html, count=1)

# Remove V4 localStorage helper functions completely.
for function_name in ["readVenueList", "writeVenueList"]:
    if re.search(rf"function\s+{function_name}\s*\(", html):
        a, b = named_range(html, function_name)
        html = html[:a] + html[b:]

# 4. Make the dropdown authoritative from STATE.venues.
shared_available = '''function getAvailableVenues() {
            const venues = Array.isArray(STATE.venues) ? [...STATE.venues] : [];
            const active = String(STATE.venue || '').trim();

            if (active && !venues.some(venue => String(venue).trim().toLowerCase() === active.toLowerCase())) {
                venues.push(active);
            }

            const unique = [];
            venues.forEach(value => {
                const clean = String(value || '').trim();
                if (clean && !unique.some(item => item.toLowerCase() === clean.toLowerCase())) {
                    unique.push(clean);
                }
            });

            return unique.sort((a, b) => a.localeCompare(b));
        }'''
html = replace_named(html, "getAvailableVenues", shared_available)

# 5. Add or remove venues through Code.gs, then pull the authoritative catalog.
shared_remove = '''window.removeSelectedVenue = async function () {
            const select = document.getElementById('venue-select');
            if (!select || !select.value || select.value === VENUE_ADD_NEW) return;

            const venue = select.value;
            const confirmed = confirm(
                `Remove "${venue}" from the shared venue list?\n\nHistorical Sales Log records will remain unchanged.`
            );
            if (!confirmed) return;

            STATE.venues = (STATE.venues || []).filter(
                item => String(item).toLowerCase() !== venue.toLowerCase()
            );
            populateVenueSelect();

            await sendSheetPayload({ action: 'remove_venue', venue: venue });
            setTimeout(() => fetchFromGoogleSheet(false), 1200);
        };'''
html = replace_assigned(html, "removeSelectedVenue", shared_remove)

shared_save = '''window.saveVenue = async function () {
            const select = document.getElementById('venue-select');
            const newInput = document.getElementById('new-venue-input');
            const isNew = select && select.value === VENUE_ADD_NEW;
            const venue = isNew
                ? String(newInput?.value || '').trim()
                : String(select?.value || '').trim();

            if (!venue) {
                alert('Please select a venue or enter a new venue name.');
                return;
            }

            STATE.venue = venue;
            STATE.date = document.getElementById('venue-date').value || localTodayDate();

            if (isNew) {
                if (!Array.isArray(STATE.venues)) STATE.venues = [];
                if (!STATE.venues.some(item => String(item).toLowerCase() === venue.toLowerCase())) {
                    STATE.venues.push(venue);
                }
                await sendSheetPayload({ action: 'add_venue', venue: venue });
                setTimeout(() => fetchFromGoogleSheet(false), 1200);
            }

            persistState();
            closeModal('venue-modal');
            renderShiftBar();
        };'''
html = replace_assigned(html, "saveVenue", shared_save)

# 6. Update explanatory copy if V4 wording is present.
html = html.replace(
    "Removing a venue only hides it from this device. Google Sheet history is unchanged.",
    "Removing a venue removes it from the shared venue list only. Historical Sales Log records remain unchanged.",
)

# 7. Replace marker so reruns are safe.
html = html.replace(OLD_MARKER, NEW_MARKER, 1)

# 8. Validate migration.
for required in [
    NEW_MARKER,
    "STATE.venues = data.venues",
    "Array.isArray(STATE.venues)",
    "action: 'add_venue'",
    "action: 'remove_venue'",
    "setTimeout(() => fetchFromGoogleSheet(false), 1200)",
    "document.getElementById('venue-date').value = localTodayDate()",
]:
    if required not in html:
        fail(f"Final validation failed for: {required}")

for forbidden in [
    "cream_daddy_local_venues",
    "cream_daddy_hidden_venues",
    "readVenueList(",
    "writeVenueList(",
]:
    if forbidden in html:
        fail(f"Local-only V4 venue logic remains: {forbidden}")

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = ROOT / f"index-backup-{stamp}.html"
shutil.copy2(TARGET, backup)
TARGET.write_text(html, encoding="utf-8")

node = shutil.which("node")
if node:
    scripts = re.findall(r"<script(?:\s[^>]*)?>([\s\S]*?)</script>", html, re.I)
    if not scripts:
        shutil.copy2(backup, TARGET)
        fail("No inline JavaScript found. Backup restored.")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as temp:
        temp.write(scripts[-1])
        temp_path = temp.name
    result = subprocess.run([node, "--check", temp_path], capture_output=True, text=True)
    Path(temp_path).unlink(missing_ok=True)
    if result.returncode:
        shutil.copy2(backup, TARGET)
        print(result.stderr)
        fail("JavaScript syntax validation failed. Backup restored.")
    validation = "JavaScript syntax checked with Node."
else:
    validation = "Node not installed. Check VS Code Problems and browser Console before committing."

print("SUCCESS: V4 migrated to the shared Google Sheet venue catalog.")
print("BACKUP:", backup.name)
print("CHANGES:")
print("  - Existing V4 dropdown UI retained")
print("  - Local-only venue storage removed")
print("  - pull_all venues are stored in STATE.venues")
print("  - Add and Remove venue actions use the deployed Apps Script backend")
print("  - Catalog refreshes after shared venue writes")
print("  - Historical Sales Log data remains unchanged")
print("  - Date continues to default to today's local date")
print("VALIDATION:", validation)
