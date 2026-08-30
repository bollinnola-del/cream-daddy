#!/usr/bin/env python3
"""Cream Daddy Stats UI V3.3.2, built for the committed V3.2 baseline."""
from pathlib import Path
from datetime import datetime
import re, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "index.html"


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
            if c == "\n": line_comment = False
        elif block_comment:
            if c == "*" and n == "/": block_comment = False; i += 1
        elif quote:
            if escaped: escaped = False
            elif c == "\\": escaped = True
            elif c == quote: quote = None
        else:
            if c == "/" and n == "/": line_comment = True; i += 1
            elif c == "/" and n == "*": block_comment = True; i += 1
            elif c in ("'", '"', "`"): quote = c
            elif c == "{": depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0: return i
        i += 1
    fail("Could not match a JavaScript closing brace.")


def named_function_range(source, name):
    match = re.search(rf"function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", source)
    if not match: fail(f"Could not find {name}().")
    opening = source.find("{", match.start())
    return match.start(), matching_brace(source, opening) + 1


def assigned_function_range(source, object_name, function_name):
    match = re.search(
        rf"{re.escape(object_name)}\.{re.escape(function_name)}\s*=\s*function\s*\([^)]*\)\s*\{{",
        source,
    )
    if not match: fail(f"Could not find {object_name}.{function_name}().")
    opening = source.find("{", match.start())
    closing = matching_brace(source, opening)
    end = closing + 1
    while end < len(source) and source[end] in " \t": end += 1
    if end < len(source) and source[end] == ";": end += 1
    return match.start(), end


def replace_named(source, name, replacement):
    a, b = named_function_range(source, name)
    return source[:a] + replacement + source[b:]


def replace_assigned(source, object_name, function_name, replacement):
    a, b = assigned_function_range(source, object_name, function_name)
    return source[:a] + replacement + source[b:]


def html_div_block(source, marker):
    marker_pos = source.find(marker)
    if marker_pos < 0: fail(f"Could not find HTML marker: {marker}")
    start = source.rfind("<div", 0, marker_pos + 1)
    if start < 0: fail("Could not find filter card opening div.")
    depth = 0
    pattern = re.compile(r"<(/?)div\b[^>]*>", re.I)
    for tag in pattern.finditer(source, start):
        depth += -1 if tag.group(1) else 1
        if depth == 0:
            return start, tag.end()
    fail("Could not find filter card closing div.")


if not HTML.exists(): fail("Put this script beside index.html.")
original = HTML.read_text(encoding="utf-8")
html = original

if 'class="stats-venue-multiselect"' in html:
    print("No update needed. Stats UI V3.3.2 is already installed.")
    sys.exit(0)

# Require the clean committed V3.2 baseline.
for expected in [
    'id="stats-filter-card"',
    'id="stats-date-radio-group"',
    'id="stats-filter-summary" class="stats-filter-pills"',
    "function getFilteredTransactions()",
    "function populateStatsVenueFilter()",
    "window.updateStatsFilters = function()",
    "window.clearStatsFilters = function()",
]:
    if expected not in html: fail(f"Expected V3.2 code is missing: {expected}")

# 1. Add V3.3.2 CSS. Old V3.2 radio/pill CSS may remain unused safely.
style_anchor = "    </style>"
if html.count(style_anchor) != 1: fail("Could not uniquely locate </style>.")
css = '''
        /* Stats UI V3.3.2 */
        .stats-venue-multiselect {
            width: 100%; min-height: 118px; padding: 6px;
            border: 1px solid var(--border-color); border-radius: 8px;
            background: #fff; font: inherit;
        }
        .stats-venue-multiselect option { padding: 7px 8px; }
        .stats-filter-helper { margin-top: 4px; font-size: 10px; color: var(--text-muted); }
        #stats-date-mode { min-height: 42px; }
'''
html = html.replace(style_anchor, css + style_anchor, 1)

# 2. Native venue multiselect.
old_venue = '''<select id="stats-venue-filter" class="form-input" onchange="updateStatsFilters()">
                        <option value="ALL">All Venues</option>
                    </select>'''
new_venue = '''<select id="stats-venue-filter" class="stats-venue-multiselect" multiple size="4" onchange="updateStatsFilters()">
                        <option value="ALL">All Venues</option>
                    </select>
                    <div class="stats-filter-helper">Select one or more venues. Select All Venues to clear venue-specific filtering.</div>'''
if html.count(old_venue) != 1: fail("Could not uniquely locate the V3.2 Venue select.")
html = html.replace(old_venue, new_venue, 1)

# 3. Date dropdown replaces the exact V3.2 radio field.
old_date = '''<div class="stats-filter-field">
                    <label>Date</label>
                    <div id="stats-date-radio-group" class="stats-date-radio-group">
                        <label class="stats-date-radio"><input type="radio" name="stats-date-mode-radio" value="ALL_TIME" onchange="selectStatsDateMode(this.value)" checked>All Time</label>
                        <label class="stats-date-radio"><input type="radio" name="stats-date-mode-radio" value="SINGLE_DATE" onchange="selectStatsDateMode(this.value)">Individual Date</label>
                        <label class="stats-date-radio"><input type="radio" name="stats-date-mode-radio" value="CUSTOM_RANGE" onchange="selectStatsDateMode(this.value)">Custom Range</label>
                    </div>
                    <input id="stats-date-mode" type="hidden" value="ALL_TIME">
                </div>'''
new_date = '''<div class="stats-filter-field">
                    <label for="stats-date-mode">Date</label>
                    <select id="stats-date-mode" class="form-input" onchange="updateStatsFilterVisibility(); updateStatsFilters();">
                        <option value="ALL_TIME">All Time</option>
                        <option value="SINGLE_DATE">Individual Date</option>
                        <option value="CUSTOM_RANGE">Custom Range</option>
                    </select>
                </div>'''
if html.count(old_date) != 1: fail("Could not uniquely locate the V3.2 Date radio group.")
html = html.replace(old_date, new_date, 1)

# 4. Remove filter pill/status markup.
summary = '<div id="stats-filter-summary" class="stats-filter-pills" aria-live="polite"></div>'
if html.count(summary) != 1: fail("Could not uniquely locate the V3.2 pill container.")
html = html.replace(summary, "", 1)

# 5. Move filter card above the analytics grid.
start, end = html_div_block(html, 'id="stats-filter-card"')
line_start = html.rfind("\n", 0, start) + 1
end_with_ws = end
while end_with_ws < len(html) and html[end_with_ws] in " \t": end_with_ws += 1
if end_with_ws < len(html) and html[end_with_ws] == "\n": end_with_ws += 1
filter_card = html[line_start:end_with_ws]
without = html[:line_start] + html[end_with_ws:]
stats_tab = without.find('<div id="tab-stats" class="tab-content">')
grid = without.find('<div class="stats-grid">', stats_tab)
if stats_tab < 0 or grid < 0: fail("Could not locate Stats tab or analytics grid.")
grid_line = without.rfind("\n", 0, grid) + 1
html = without[:grid_line] + filter_card + without[grid_line:]

# 6. Remove radio helper functions and their calls.
if re.search(r"function\s+syncStatsDateRadios\s*\(", html):
    a, b = named_function_range(html, "syncStatsDateRadios")
    html = html[:a] + html[b:]
if re.search(r"window\.selectStatsDateMode\s*=\s*function", html):
    a, b = assigned_function_range(html, "window", "selectStatsDateMode")
    html = html[:a] + html[b:]
html = html.replace("            syncStatsDateRadios();\n", "")

# 7. Convert filter state and migrate any current session value.
old_state = '''let statsFilters = {
            venue: 'ALL',
            mode: 'ALL_TIME',
            singleDate: '',
            startDate: '',
            endDate: ''
        };'''
new_state = '''let statsFilters = {
            selectedVenues: [],
            mode: 'ALL_TIME',
            singleDate: '',
            startDate: '',
            endDate: ''
        };'''
if html.count(old_state) != 1: fail("Could not uniquely locate the V3.2 filter state.")
html = html.replace(old_state, new_state, 1)

load_fn = '''function loadStatsFilters() {
            try {
                const stored = sessionStorage.getItem(STATS_FILTER_KEY);
                if (stored) {
                    const parsed = JSON.parse(stored);
                    statsFilters = { ...statsFilters, ...parsed };
                    if (!Array.isArray(statsFilters.selectedVenues)) {
                        statsFilters.selectedVenues = parsed.venue && parsed.venue !== 'ALL' ? [parsed.venue] : [];
                    }
                    delete statsFilters.venue;
                }
            } catch (error) {
                console.warn('Could not restore analytics filters:', error);
            }
        }'''
html = replace_named(html, "loadStatsFilters", load_fn)

filtered_fn = '''function getFilteredTransactions() {
            return STATE.transactions.filter(tx => {
                const txVenue = String(tx.venue || 'Unspecified Venue').trim() || 'Unspecified Venue';
                const venueMatches = statsFilters.selectedVenues.length === 0 || statsFilters.selectedVenues.includes(txVenue);
                if (!venueMatches) return false;

                if (statsFilters.mode === 'ALL_TIME') return true;
                const txDate = transactionDateKey(tx);
                if (!txDate) return false;

                if (statsFilters.mode === 'SINGLE_DATE') {
                    return Boolean(statsFilters.singleDate) && txDate === statsFilters.singleDate;
                }
                if (statsFilters.mode === 'CUSTOM_RANGE') {
                    if (!statsFilters.startDate || !statsFilters.endDate) return false;
                    return txDate >= statsFilters.startDate && txDate <= statsFilters.endDate;
                }
                return true;
            });
        }'''
html = replace_named(html, "getFilteredTransactions", filtered_fn)

populate_fn = '''function populateStatsVenueFilter() {
            const select = document.getElementById('stats-venue-filter');
            if (!select) return;

            const venues = [...new Set(STATE.transactions.map(tx =>
                String(tx.venue || 'Unspecified Venue').trim() || 'Unspecified Venue'
            ))].sort((a, b) => a.localeCompare(b));

            statsFilters.selectedVenues = statsFilters.selectedVenues.filter(venue => venues.includes(venue));
            select.innerHTML = '<option value="ALL">All Venues</option>' + venues.map(venue =>
                `<option value="${escapeHtml(venue)}">${escapeHtml(venue)}</option>`
            ).join('');

            [...select.options].forEach(option => {
                option.selected = option.value === 'ALL'
                    ? statsFilters.selectedVenues.length === 0
                    : statsFilters.selectedVenues.includes(option.value);
            });
        }'''
html = replace_named(html, "populateStatsVenueFilter", populate_fn)

sync_fn = '''function syncStatsFilterControls() {
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
        }'''
html = replace_named(html, "syncStatsFilterControls", sync_fn)

# Safe brace-aware replacement prevents the duplicate block that broke V3.3.1.
update_fn = '''window.updateStatsFilters = function() {
            const venueSelect = document.getElementById('stats-venue-filter');
            let selectedVenues = venueSelect
                ? [...venueSelect.selectedOptions].map(option => option.value)
                : [];

            if (selectedVenues.includes('ALL')) selectedVenues = [];

            statsFilters = {
                selectedVenues,
                mode: document.getElementById('stats-date-mode')?.value || 'ALL_TIME',
                singleDate: document.getElementById('stats-single-date')?.value || '',
                startDate: document.getElementById('stats-start-date')?.value || '',
                endDate: document.getElementById('stats-end-date')?.value || ''
            };
            saveStatsFilters();
            renderStats();
        };'''
html = replace_assigned(html, "window", "updateStatsFilters", update_fn)

clear_fn = '''window.clearStatsFilters = function() {
            statsFilters = { selectedVenues: [], mode: 'ALL_TIME', singleDate: '', startDate: '', endDate: '' };
            saveStatsFilters();
            syncStatsFilterControls();
            renderStats();
        };'''
html = replace_assigned(html, "window", "clearStatsFilters", clear_fn)

# Keep function available if old code calls it, but it renders nothing.
summary_fn = '''function updateStatsFilterSummary() {
            return;
        }'''
html = replace_named(html, "updateStatsFilterSummary", summary_fn)
html = html.replace("            updateStatsFilterSummary();\n", "")

# 8. Validation before writing.
for expected in [
    'class="stats-venue-multiselect"',
    'multiple size="4"',
    '<option value="CUSTOM_RANGE">Custom Range</option>',
    "selectedVenues: []",
    "statsFilters.selectedVenues.includes(txVenue)",
]:
    if expected not in html: fail(f"Final validation failed: {expected}")
for forbidden in [
    'id="stats-date-radio-group"',
    'id="stats-filter-summary"',
    'class="stats-filter-pill"',
]:
    if forbidden in html: fail(f"Old V3.2 UI remains: {forbidden}")
stats_tab = html.find('<div id="tab-stats" class="tab-content">')
filter_pos = html.find('id="stats-filter-card"', stats_tab)
grid_pos = html.find('class="stats-grid"', stats_tab)
if not (stats_tab < filter_pos < grid_pos): fail("Filter card was not moved above analytics.")
if html.count("window.updateStatsFilters = function()") != 1:
    fail("updateStatsFilters() is not unique after patching.")

# 9. Backup and write.
stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = ROOT / f"index-backup-{stamp}.html"
shutil.copy2(HTML, backup)
HTML.write_text(html, encoding="utf-8")

# 10. Syntax check with Node when installed; otherwise give a clear manual validation step.
node = shutil.which("node")
if node:
    scripts = re.findall(r"<script(?:\s[^>]*)?>([\s\S]*?)</script>", html, re.I)
    if not scripts:
        shutil.copy2(backup, HTML); fail("No inline JavaScript found. Backup restored.")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as temp:
        temp.write(scripts[-1]); temp_path = temp.name
    result = subprocess.run([node, "--check", temp_path], capture_output=True, text=True)
    Path(temp_path).unlink(missing_ok=True)
    if result.returncode:
        shutil.copy2(backup, HTML)
        print(result.stderr)
        fail("JavaScript syntax validation failed. Backup restored.")
    validation = "JavaScript syntax checked with Node."
else:
    validation = "Node not installed. Check VS Code Problems and browser Console before committing."

print("SUCCESS: Stats UI V3.3.2 installed.")
print("BACKUP:", backup.name)
print("CHANGES:")
print("  - Filter card moved above the four-column analytics row")
print("  - Native venue multiselect installed")
print("  - Date filter restored to a dropdown")
print("  - Active-filter pills removed")
print("  - Reset remains in the upper-right")
print("  - Session persistence and native date pickers retained")
print("VALIDATION:", validation)
