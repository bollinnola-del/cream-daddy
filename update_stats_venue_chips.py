#!/usr/bin/env python3
"""Replace the native Stats venue multiselect with a mobile-friendly chip picker."""
from pathlib import Path
from datetime import datetime
import re, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"
MARKER = "// Cream Daddy Stats Venue Chip Picker V1"


def fail(message):
    print("ERROR:", message)
    print("No changes were saved.")
    sys.exit(1)


def matching_brace(source, opening):
    depth = 0; quote = None; escaped = False; line = False; block = False
    i = opening
    while i < len(source):
        c = source[i]; n = source[i + 1] if i + 1 < len(source) else ""
        if line:
            if c == "\n": line = False
        elif block:
            if c == "*" and n == "/": block = False; i += 1
        elif quote:
            if escaped: escaped = False
            elif c == "\\": escaped = True
            elif c == quote: quote = None
        else:
            if c == "/" and n == "/": line = True; i += 1
            elif c == "/" and n == "*": block = True; i += 1
            elif c in ("'", '"', "`"): quote = c
            elif c == "{": depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0: return i
        i += 1
    fail("Could not match a JavaScript closing brace.")


def named_range(source, name):
    match = re.search(rf"function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", source)
    if not match: fail(f"Could not find {name}().")
    opening = source.find("{", match.start())
    return match.start(), matching_brace(source, opening) + 1


def assigned_range(source, name):
    match = re.search(rf"window\.{re.escape(name)}\s*=\s*(?:async\s+)?function\s*\([^)]*\)\s*\{{", source)
    if not match: fail(f"Could not find window.{name}().")
    opening = source.find("{", match.start())
    closing = matching_brace(source, opening)
    end = closing + 1
    while end < len(source) and source[end] in " \t": end += 1
    if end < len(source) and source[end] == ";": end += 1
    return match.start(), end


def replace_named(source, name, replacement):
    a, b = named_range(source, name)
    return source[:a] + replacement + source[b:]


def replace_assigned(source, name, replacement):
    a, b = assigned_range(source, name)
    return source[:a] + replacement + source[b:]


if not INDEX.exists(): fail("index.html was not found. Put this script beside index.html.")
original = INDEX.read_text(encoding="utf-8")
html = original

if MARKER in html:
    print("No update needed. Stats Venue Chip Picker V1 is already installed.")
    sys.exit(0)

for required in [
    'id="stats-venue-filter"',
    "function populateStatsVenueFilter()",
    "function syncStatsFilterControls()",
    "window.updateStatsFilters = function",
    "selectedVenues",
]:
    if required not in html: fail(f"Expected current Stats filter code is missing: {required}")

# 1. Replace the native select plus optional helper copy.
select_pattern = re.compile(
    r'''<select\s+id="stats-venue-filter"[\s\S]*?</select>(?:\s*<div class="stats-filter-helper">[\s\S]*?</div>)?''',
    re.I,
)
chip_markup = '''<div id="stats-venue-filter" class="venue-chip-picker">
                        <button id="venue-chip-trigger" class="venue-chip-trigger" type="button"
                            aria-haspopup="listbox" aria-expanded="false" onclick="toggleVenueChipPanel()">
                            <span id="venue-chip-values" class="venue-chip-values"></span>
                            <span class="venue-chip-chevron" aria-hidden="true">⌄</span>
                        </button>
                        <div id="venue-chip-panel" class="venue-chip-panel" hidden>
                            <div class="venue-chip-search-row">
                                <input id="venue-chip-search" class="form-input" type="search"
                                    placeholder="Search venues" oninput="renderVenueChipOptions()">
                            </div>
                            <div class="venue-chip-toolbar">
                                <button type="button" onclick="selectAllVenueFilters()">Select All</button>
                                <button type="button" onclick="clearAllVenueFilters()">Clear All</button>
                            </div>
                            <div id="venue-chip-options" class="venue-chip-options" role="listbox" aria-multiselectable="true"></div>
                        </div>
                    </div>'''
html, count = select_pattern.subn(chip_markup, html, count=1)
if count != 1: fail("Could not safely replace the native venue multiselect.")

# 2. Add custom picker CSS.
if html.count("</style>") != 1: fail("Expected exactly one </style> tag.")
css = '''
        /* Stats Venue Chip Picker V1 */
        .venue-chip-picker { position:relative; width:100%; }
        .venue-chip-trigger {
            width:100%; min-height:44px; display:flex; align-items:center; justify-content:space-between;
            gap:8px; padding:7px 10px; border:1px solid var(--brand-pink); border-radius:10px;
            background:#fff; color:var(--text-dark); text-align:left; cursor:pointer;
        }
        .venue-chip-values { display:flex; flex-wrap:wrap; align-items:center; gap:6px; min-width:0; flex:1; }
        .venue-chip-placeholder { color:var(--text-muted); font-size:14px; }
        .venue-filter-chip {
            display:inline-flex; align-items:center; gap:5px; max-width:100%; padding:5px 8px;
            border-radius:999px; background:#fff0f7; color:var(--brand-pink);
            border:1px solid #f3a4ce; font-size:12px; font-weight:800;
        }
        .venue-filter-chip-text { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .venue-filter-chip-remove {
            border:0; background:transparent; color:inherit; padding:0; font-size:15px;
            line-height:1; cursor:pointer;
        }
        .venue-chip-chevron { flex:0 0 auto; font-size:18px; transition:transform .15s ease; }
        .venue-chip-trigger[aria-expanded="true"] .venue-chip-chevron { transform:rotate(180deg); }
        .venue-chip-panel {
            position:absolute; z-index:1200; left:0; right:0; top:calc(100% + 6px);
            padding:10px; border:1px solid var(--border-color); border-radius:12px;
            background:#fff; box-shadow:0 12px 26px rgba(17,17,17,.18);
        }
        .venue-chip-search-row { margin-bottom:8px; }
        .venue-chip-toolbar { display:flex; gap:8px; margin-bottom:8px; }
        .venue-chip-toolbar button {
            flex:1; border:1px solid var(--border-color); background:#f9fafb; color:var(--text-dark);
            padding:7px 8px; border-radius:8px; font-size:12px; font-weight:800; cursor:pointer;
        }
        .venue-chip-options { max-height:240px; overflow-y:auto; display:flex; flex-direction:column; gap:4px; }
        .venue-chip-option {
            display:flex; align-items:center; gap:9px; padding:10px 8px; border-radius:8px;
            font-size:14px; cursor:pointer;
        }
        .venue-chip-option:hover, .venue-chip-option:active { background:#f9fafb; }
        .venue-chip-option input { width:18px; height:18px; min-height:0; accent-color:var(--brand-pink); }
        .venue-chip-empty { padding:12px; text-align:center; color:var(--text-muted); font-size:12px; }
        @media (max-width:560px) {
            .venue-chip-panel { position:fixed; left:14px; right:14px; top:auto; bottom:78px; }
            .venue-chip-options { max-height:42vh; }
        }
'''
html = html.replace("</style>", css + "    </style>", 1)

# 3. Replace venue population with a plain canonical venue array.
populate = '''function populateStatsVenueFilter() {
            const venues = [...new Set(STATE.transactions.map(tx =>
                String(tx.venue || 'Unspecified Venue').trim() || 'Unspecified Venue'
            ))].sort((a, b) => a.localeCompare(b));

            statsFilters.selectedVenues = (statsFilters.selectedVenues || [])
                .filter(venue => venues.includes(venue));
            window.statsVenueFilterOptions = venues;
            renderVenueFilterChips();
            renderVenueChipOptions();
        }'''
html = replace_named(html, "populateStatsVenueFilter", populate)

# 4. Replace sync controls so it no longer treats the component as a select.
sync = '''function syncStatsFilterControls() {
            populateStatsVenueFilter();
            const mode = document.getElementById('stats-date-mode');
            const single = document.getElementById('stats-single-date');
            const start = document.getElementById('stats-start-date');
            const end = document.getElementById('stats-end-date');
            if (mode) mode.value = statsFilters.mode;
            if (single) single.value = statsFilters.singleDate;
            if (start) start.value = statsFilters.startDate;
            if (end) end.value = statsFilters.endDate;
            updateStatsFilterVisibility();
            renderVenueFilterChips();
            renderVenueChipOptions();
        }'''
html = replace_named(html, "syncStatsFilterControls", sync)

# 5. updateStatsFilters now reads the selection array directly.
update = '''window.updateStatsFilters = function () {
            statsFilters = {
                selectedVenues: Array.isArray(statsFilters.selectedVenues) ? [...statsFilters.selectedVenues] : [],
                mode: document.getElementById('stats-date-mode')?.value || 'ALL_TIME',
                singleDate: document.getElementById('stats-single-date')?.value || '',
                startDate: document.getElementById('stats-start-date')?.value || '',
                endDate: document.getElementById('stats-end-date')?.value || ''
            };
            saveStatsFilters();
            renderStats();
        };'''
html = replace_assigned(html, "updateStatsFilters", update)

# 6. Insert picker behavior before populateStatsVenueFilter.
populate_start, _ = named_range(html, "populateStatsVenueFilter")
js = '''        // Cream Daddy Stats Venue Chip Picker V1
        window.statsVenueFilterOptions = [];

        function renderVenueFilterChips() {
            const container = document.getElementById('venue-chip-values');
            if (!container) return;
            const selected = Array.isArray(statsFilters.selectedVenues) ? statsFilters.selectedVenues : [];
            if (!selected.length) {
                container.innerHTML = '<span class="venue-chip-placeholder">All Venues</span>';
                return;
            }
            container.innerHTML = '';
            selected.forEach(venue => {
                const chip = document.createElement('span');
                chip.className = 'venue-filter-chip';
                const text = document.createElement('span');
                text.className = 'venue-filter-chip-text';
                text.textContent = venue;
                const remove = document.createElement('button');
                remove.className = 'venue-filter-chip-remove';
                remove.type = 'button';
                remove.setAttribute('aria-label', `Remove ${venue}`);
                remove.textContent = '×';
                remove.addEventListener('click', event => {
                    event.stopPropagation();
                    toggleVenueFilterValue(venue, false);
                });
                chip.append(text, remove);
                container.appendChild(chip);
            });
        }

        window.renderVenueChipOptions = function () {
            const container = document.getElementById('venue-chip-options');
            if (!container) return;
            const query = String(document.getElementById('venue-chip-search')?.value || '').trim().toLowerCase();
            const venues = (window.statsVenueFilterOptions || []).filter(venue =>
                !query || venue.toLowerCase().includes(query)
            );
            container.innerHTML = '';
            if (!venues.length) {
                container.innerHTML = '<div class="venue-chip-empty">No matching venues</div>';
                return;
            }
            venues.forEach(venue => {
                const label = document.createElement('label');
                label.className = 'venue-chip-option';
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.checked = (statsFilters.selectedVenues || []).includes(venue);
                checkbox.addEventListener('change', () => toggleVenueFilterValue(venue, checkbox.checked));
                const text = document.createElement('span');
                text.textContent = venue;
                label.append(checkbox, text);
                container.appendChild(label);
            });
        };

        window.toggleVenueFilterValue = function (venue, shouldSelect) {
            const selected = new Set(statsFilters.selectedVenues || []);
            if (shouldSelect) selected.add(venue); else selected.delete(venue);
            statsFilters.selectedVenues = [...selected];
            saveStatsFilters();
            renderVenueFilterChips();
            renderVenueChipOptions();
            renderStats();
        };

        window.selectAllVenueFilters = function () {
            statsFilters.selectedVenues = [...(window.statsVenueFilterOptions || [])];
            saveStatsFilters();
            renderVenueFilterChips();
            renderVenueChipOptions();
            renderStats();
        };

        window.clearAllVenueFilters = function () {
            statsFilters.selectedVenues = [];
            saveStatsFilters();
            renderVenueFilterChips();
            renderVenueChipOptions();
            renderStats();
        };

        window.toggleVenueChipPanel = function () {
            const panel = document.getElementById('venue-chip-panel');
            const trigger = document.getElementById('venue-chip-trigger');
            if (!panel || !trigger) return;
            const opening = panel.hidden;
            panel.hidden = !opening;
            trigger.setAttribute('aria-expanded', String(opening));
            if (opening) {
                renderVenueChipOptions();
                setTimeout(() => document.getElementById('venue-chip-search')?.focus(), 0);
            }
        };

        document.addEventListener('click', event => {
            const picker = document.getElementById('stats-venue-filter');
            const panel = document.getElementById('venue-chip-panel');
            const trigger = document.getElementById('venue-chip-trigger');
            if (picker && panel && !picker.contains(event.target)) {
                panel.hidden = true;
                trigger?.setAttribute('aria-expanded', 'false');
            }
        });

        document.addEventListener('keydown', event => {
            if (event.key !== 'Escape') return;
            const panel = document.getElementById('venue-chip-panel');
            const trigger = document.getElementById('venue-chip-trigger');
            if (panel && !panel.hidden) {
                panel.hidden = true;
                trigger?.setAttribute('aria-expanded', 'false');
                trigger?.focus();
            }
        });

'''
html = html[:populate_start] + js + html[populate_start:]

# 7. Validation.
for required in [MARKER, 'id="venue-chip-panel"',
                 "venue-filter-chip",
                 "toggleVenueFilterValue",
                 "selectAllVenueFilters",
                 "clearAllVenueFilters"]:
    if required not in html: fail(f"Final validation failed for: {required}")
if '<select id="stats-venue-filter"' in html:
    fail("The old native venue multiselect still exists.")

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = ROOT / f"index-backup-{stamp}.html"
shutil.copy2(INDEX, backup)
INDEX.write_text(html, encoding="utf-8")

node = shutil.which("node")
if node:
    scripts = re.findall(r"<script(?:\s[^>]*)?>([\s\S]*?)</script>", html, re.I)
    if not scripts:
        shutil.copy2(backup, INDEX); fail("No inline JavaScript found. Backup restored.")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as temp:
        temp.write(scripts[-1]); temp_path = temp.name
    result = subprocess.run([node, "--check", temp_path], capture_output=True, text=True)
    Path(temp_path).unlink(missing_ok=True)
    if result.returncode:
        shutil.copy2(backup, INDEX)
        print(result.stderr)
        fail("JavaScript syntax validation failed. Backup restored.")
    validation = "JavaScript syntax checked with Node."
else:
    validation = "Node not installed. Check VS Code Problems and browser Console before committing."

print("SUCCESS: Stats Venue Chip Picker installed.")
print("BACKUP:", backup.name)
print("CHANGES:")
print("  - Replaced native venue multiselect with a chip-based picker")
print("  - Added searchable checkbox dropdown")
print("  - Added Select All and Clear All")
print("  - Added removable selected-venue chips")
print("  - Preserved date filter, Reset, session persistence, and report logic")
print("VALIDATION:", validation)
