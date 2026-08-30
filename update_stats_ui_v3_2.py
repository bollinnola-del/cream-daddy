#!/usr/bin/env python3
"""Refine Cream Daddy Stats filters and hide the venue bar outside Register."""
from pathlib import Path
from datetime import datetime
import re, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "index.html"

def fail(msg):
    print("ERROR:", msg)
    print("No changes were saved.")
    sys.exit(1)

def function_range(source, name):
    m = re.search(rf"function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", source)
    if not m: fail(f"Could not find {name}().")
    opening = source.find("{", m.start())
    depth = 0; quote = None; esc = False; line = False; block = False
    i = opening
    while i < len(source):
        c = source[i]; n = source[i+1] if i+1 < len(source) else ""
        if line:
            if c == "\n": line = False
        elif block:
            if c == "*" and n == "/": block = False; i += 1
        elif quote:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == quote: quote = None
        else:
            if c == "/" and n == "/": line = True; i += 1
            elif c == "/" and n == "*": block = True; i += 1
            elif c in ("'", '"', "`"): quote = c
            elif c == "{": depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0: return m.start(), i + 1
        i += 1
    fail(f"Could not match braces for {name}().")

def replace_function(source, name, replacement):
    a,b = function_range(source,name)
    return source[:a] + replacement + source[b:]

if not HTML.exists(): fail("Put this script beside index.html.")
original = HTML.read_text(encoding="utf-8")
html = original
if "stats-date-radio-group" in html:
    print("No update needed. Stats UI v3.2 is already installed.")
    sys.exit(0)
for x in ['id="stats-filter-card"','id="stats-date-mode"','id="stats-filter-summary"',
          "function updateStatsFilterSummary()","function syncStatsFilterControls()"]:
    if x not in html: fail(f"Expected V3 filter code is missing: {x}")

# CSS overrides/additions.
style_anchor = "    </style>"
if html.count(style_anchor) != 1: fail("Could not uniquely locate </style>.")
css = '''
        /* Stats UI v3.2 */
        #tab-stats .stats-grid,
        #tab-stats .stats-summary-grid {
            grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
            gap: 10px;
        }
        #stats-filter-card .card-header-row { align-items:center; margin-bottom:10px; }
        .stats-reset-button { padding:7px 12px; border-radius:999px; font-size:12px; }
        .stats-date-radio-group { display:flex; flex-wrap:wrap; gap:8px; }
        .stats-date-radio {
            display:inline-flex; align-items:center; gap:6px; min-height:38px;
            padding:7px 10px; border:1px solid var(--border-color); border-radius:999px;
            background:#fff; font-size:12px; font-weight:700; cursor:pointer;
        }
        .stats-date-radio:has(input:checked) {
            border-color:var(--brand-pink); background:#fff0f7; color:var(--brand-pink);
        }
        .stats-date-radio input { width:auto; min-height:0; margin:0; accent-color:var(--brand-pink); }
        .stats-filter-pills { display:flex; flex-wrap:wrap; gap:7px; margin-top:10px; }
        .stats-filter-pill {
            display:inline-flex; align-items:center; min-height:28px; padding:5px 10px;
            border-radius:999px; background:#f3f4f6; color:var(--text-muted);
            font-size:11px; font-weight:800;
        }
        @media (max-width:560px) {
            #tab-stats .stats-grid,
            #tab-stats .stats-summary-grid { grid-template-columns: repeat(4, minmax(0, 1fr)) !important; gap:6px; }
            #tab-stats .stat-card { padding:10px 4px !important; min-width:0; }
            #tab-stats .stat-label { font-size:9px !important; }
            #tab-stats .stat-value { font-size:18px !important; }
            .stats-date-radio-group { display:grid; grid-template-columns:1fr; }
        }
'''
html = html.replace(style_anchor, css + style_anchor, 1)

# Transform the existing filter card's title and date dropdown.
old_title = '<div class="card-title" style="margin-bottom:10px;">🔎 Analytics Filters</div>'
new_title = '''<div class="card-header-row">
                <div class="card-title">🔎 Analytics Filters</div>
                <button class="btn-secondary stats-reset-button" type="button" onclick="clearStatsFilters()">Reset</button>
            </div>'''
if html.count(old_title) != 1: fail("Could not uniquely locate the Analytics Filters title.")
html = html.replace(old_title,new_title,1)

old_date_field = '''                <div class="stats-filter-field">
                    <label for="stats-date-mode">Date</label>
                    <select id="stats-date-mode" class="form-input" onchange="updateStatsFilterVisibility(); updateStatsFilters();">
                        <option value="ALL_TIME">All Time</option>
                        <option value="SINGLE_DATE">Individual Date</option>
                        <option value="CUSTOM_RANGE">Custom Range</option>
                    </select>
                </div>'''
new_date_field = '''                <div class="stats-filter-field">
                    <label>Date</label>
                    <div id="stats-date-radio-group" class="stats-date-radio-group">
                        <label class="stats-date-radio"><input type="radio" name="stats-date-mode-radio" value="ALL_TIME" onchange="selectStatsDateMode(this.value)" checked>All Time</label>
                        <label class="stats-date-radio"><input type="radio" name="stats-date-mode-radio" value="SINGLE_DATE" onchange="selectStatsDateMode(this.value)">Individual Date</label>
                        <label class="stats-date-radio"><input type="radio" name="stats-date-mode-radio" value="CUSTOM_RANGE" onchange="selectStatsDateMode(this.value)">Custom Range</label>
                    </div>
                    <input id="stats-date-mode" type="hidden" value="ALL_TIME">
                </div>'''
if html.count(old_date_field) != 1: fail("Could not locate the original Date dropdown field.")
html = html.replace(old_date_field,new_date_field,1)

# Summary bar becomes an empty pill container; remove bottom Clear button row.
old_summary = '<div id="stats-filter-summary" class="stats-filter-summary">Showing all venues · All time</div>'
new_summary = '<div id="stats-filter-summary" class="stats-filter-pills" aria-live="polite"></div>'
if html.count(old_summary) != 1: fail("Could not locate the filter summary bar.")
html = html.replace(old_summary,new_summary,1)
old_actions = '''            <div class="stats-filter-actions">
                <button class="btn-secondary" type="button" onclick="clearStatsFilters()">Clear Filters</button>
            </div>
'''
if html.count(old_actions) != 1: fail("Could not locate the bottom Clear Filters action.")
html = html.replace(old_actions,"",1)

# Radio helper before updateStatsFilterVisibility.
anchor = re.search(r"^[ \t]*function\s+updateStatsFilterVisibility\s*\(\s*\)\s*\{",html,re.M)
if not anchor: fail("Could not locate updateStatsFilterVisibility().")
radio_js = '''        window.selectStatsDateMode = function(mode) {
            const hidden = document.getElementById('stats-date-mode');
            if (hidden) hidden.value = mode;
            updateStatsFilterVisibility();
            updateStatsFilters();
        };

        function syncStatsDateRadios() {
            document.querySelectorAll('input[name="stats-date-mode-radio"]').forEach(radio => {
                radio.checked = radio.value === statsFilters.mode;
            });
        }

'''
html = html[:anchor.start()] + radio_js + html[anchor.start():]

# Replace summary renderer with pills.
summary_fn = '''function updateStatsFilterSummary() {
            const summary = document.getElementById('stats-filter-summary');
            if (!summary) return;
            const venueLabel = statsFilters.venue === 'ALL' ? '📍 All venues' : `📍 ${statsFilters.venue}`;
            let dateLabel = '📅 All time';
            if (statsFilters.mode === 'SINGLE_DATE') dateLabel = statsFilters.singleDate ? `📅 ${statsFilters.singleDate}` : '📅 Select a date';
            if (statsFilters.mode === 'CUSTOM_RANGE') {
                dateLabel = statsFilters.startDate && statsFilters.endDate
                    ? `📅 ${statsFilters.startDate} to ${statsFilters.endDate}`
                    : '📅 Select a complete range';
            }
            const count = getFilteredTransactions().length;
            summary.innerHTML = `
                <span class="stats-filter-pill">${escapeHtml(venueLabel)}</span>
                <span class="stats-filter-pill">${escapeHtml(dateLabel)}</span>
                <span class="stats-filter-pill">🧾 ${count} transaction${count === 1 ? '' : 's'}</span>`;
        }'''
html = replace_function(html,"updateStatsFilterSummary",summary_fn)

# Ensure control sync updates radios.
sync_start,sync_end=function_range(html,"syncStatsFilterControls")
sync_code=html[sync_start:sync_end]
needle="            updateStatsFilterVisibility();"
if needle not in sync_code: fail("Could not locate visibility sync inside syncStatsFilterControls().")
sync_code=sync_code.replace(needle,"            syncStatsDateRadios();\n"+needle,1)
html=html[:sync_start]+sync_code+html[sync_end:]

# Ensure renderStats also syncs radio selection.
r_start,r_end=function_range(html,"renderStats")
r_code=html[r_start:r_end]
needle2="            updateStatsFilterVisibility();"
if needle2 not in r_code: fail("Could not locate filter visibility call in renderStats().")
r_code=r_code.replace(needle2,"            syncStatsDateRadios();\n"+needle2,1)
html=html[:r_start]+r_code+html[r_end:]

# Venue bar only on Register: runtime identification through its Change button and active tab.
startup_anchor = "        document.addEventListener('keydown', (e) => {"
if html.count(startup_anchor) != 1: fail("Could not locate the document keydown startup anchor.")
venue_js = '''        let registerVenueBar = null;
        function findRegisterVenueBar() {
            if (registerVenueBar && document.body.contains(registerVenueBar)) return registerVenueBar;
            const changeButton = [...document.querySelectorAll('button')].find(button =>
                button.textContent.trim().toLowerCase() === 'change'
            );
            registerVenueBar = changeButton ? changeButton.parentElement : null;
            return registerVenueBar;
        }
        function updateRegisterVenueBarVisibility() {
            const bar = findRegisterVenueBar();
            const registerTab = document.getElementById('tab-register');
            if (!bar || !registerTab) return;
            const registerVisible = registerTab.classList.contains('active');
            bar.style.display = registerVisible ? '' : 'none';
        }
        const tabVisibilityObserver = new MutationObserver(updateRegisterVenueBarVisibility);
        window.addEventListener('DOMContentLoaded', () => {
            document.querySelectorAll('.tab-content').forEach(tab =>
                tabVisibilityObserver.observe(tab, { attributes:true, attributeFilter:['class'] })
            );
            updateRegisterVenueBarVisibility();
        });

'''
html=html.replace(startup_anchor,venue_js+startup_anchor,1)

# Validate, backup, and syntax check.
for text in ['id="stats-date-radio-group"','stats-filter-pill','>Reset</button>',
             'function updateRegisterVenueBarVisibility()','syncStatsDateRadios();']:
    if text not in html: fail(f"Validation failed for {text!r}.")
if 'Clear Filters' in html: fail("The old Clear Filters button still exists.")

stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
backup=ROOT/f"index-backup-{stamp}.html"
shutil.copy2(HTML,backup)
HTML.write_text(html,encoding='utf-8')
node=shutil.which('node')
if node:
    scripts=re.findall(r'<script(?:\s[^>]*)?>([\s\S]*?)</script>',html,re.I)
    with tempfile.NamedTemporaryFile('w',suffix='.js',delete=False,encoding='utf-8') as f:
        f.write(scripts[-1]); tmp=f.name
    result=subprocess.run([node,'--check',tmp],capture_output=True,text=True)
    Path(tmp).unlink(missing_ok=True)
    if result.returncode:
        shutil.copy2(backup,HTML); print(result.stderr); fail("JavaScript validation failed. Backup restored.")
    validation='JavaScript syntax checked with Node.'
else:
    validation='Node not installed. Check VS Code Problems before committing.'

print('SUCCESS: Stats UI v3.2 installed.')
print('BACKUP:',backup.name)
print('CHANGES:')
print('  - Summary analytics forced to one row with four columns')
print('  - Filter card positioned before analytics through existing Stats order')
print('  - Date mode changed from dropdown to radio buttons')
print('  - Filter status changed to pill badges')
print('  - Reset button moved to top right')
print('  - Venue bar is shown only while Register is active')
print('VALIDATION:',validation)
