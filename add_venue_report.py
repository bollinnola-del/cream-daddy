#!/usr/bin/env python3
"""Safely add a Revenue by Venue report to the Cream Daddy Stats tab."""
from pathlib import Path
from datetime import datetime
import re, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "index.html"


def fail(message):
    print("ERROR:", message)
    print("No changes were saved.")
    sys.exit(1)


def find_function_end(source, start):
    brace = source.find("{", start)
    if brace < 0: fail("Function opening brace not found.")
    depth = 0; quote = None; escape = False; line = False; block = False
    i = brace
    while i < len(source):
        c = source[i]; n = source[i + 1] if i + 1 < len(source) else ""
        if line:
            if c == "\n": line = False
        elif block:
            if c == "*" and n == "/": block = False; i += 1
        elif quote:
            if escape: escape = False
            elif c == "\\": escape = True
            elif c == quote: quote = None
        else:
            if c == "/" and n == "/": line = True; i += 1
            elif c == "/" and n == "*": block = True; i += 1
            elif c in ("'", '"', "`"): quote = c
            elif c == "{": depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0: return i + 1
        i += 1
    fail("Function closing brace not found.")


if not HTML.exists():
    fail(f"index.html was not found in {ROOT}. Put this script beside index.html.")

original = HTML.read_text(encoding="utf-8")
html = original

if 'id="venue-performance-list"' in html or "function renderVenueReport()" in html:
    print("No update needed. Revenue by Venue already appears to be installed.")
    sys.exit(0)

# Add report styles.
style_anchor = "    </style>"
if html.count(style_anchor) != 1: fail("Could not uniquely locate </style>.")
styles = '''
        .venue-report-row { margin-bottom: 16px; }
        .venue-report-heading { display:flex; justify-content:space-between; gap:12px; align-items:baseline; }
        .venue-report-name { font-size:14px; font-weight:800; color:var(--brand-black); }
        .venue-report-revenue { font-size:14px; font-weight:900; color:var(--brand-pink); white-space:nowrap; }
        .venue-report-meta { font-size:11px; color:var(--text-muted); margin:3px 0 6px; }
        .venue-report-track { height:12px; background:#f3f4f6; border-radius:999px; overflow:hidden; }
        .venue-report-fill { height:100%; min-width:0; background:linear-gradient(90deg,var(--brand-pink),var(--brand-gold)); border-radius:999px; }
'''
html = html.replace(style_anchor, styles + style_anchor, 1)

# Add the card directly before Shift Receipt Log.
receipt_anchor = '''        <div class="card">
            <div class="card-title" style="margin-bottom: 10px;">📜 Shift Receipt Log</div>'''
if html.count(receipt_anchor) != 1:
    fail("Could not uniquely locate the Shift Receipt Log card.")
report_card = '''        <div class="card">
            <div class="card-header-row">
                <div class="card-title">📍 Revenue by Venue</div>
                <span style="font-size:11px;color:var(--text-muted);">Highest revenue first</span>
            </div>
            <div id="venue-performance-list"></div>
        </div>
'''
html = html.replace(receipt_anchor, report_card + receipt_anchor, 1)

# Add report renderer immediately before renderStats().
stats_marker = re.search(r"^[ \t]*function\s+renderStats\s*\(\s*\)\s*\{", html, flags=re.MULTILINE)
if not stats_marker: fail("Could not find renderStats().")
renderer = '''        function renderVenueReport() {
            const container = document.getElementById('venue-performance-list');
            if (!container) return;

            const venues = {};
            STATE.transactions.forEach(tx => {
                const venue = String(tx.venue || 'Unspecified Venue').trim() || 'Unspecified Venue';
                if (!venues[venue]) {
                    venues[venue] = { revenue: 0, sold: 0, gifted: 0, transactions: 0 };
                }
                venues[venue].revenue += Number(tx.totalPrice) || 0;
                venues[venue].sold += Number(tx.totalUnitsSold) || 0;
                venues[venue].gifted += Number(tx.totalUnitsGiven) || 0;
                venues[venue].transactions += 1;
            });

            const rows = Object.entries(venues)
                .map(([venue, values]) => ({ venue, ...values }))
                .sort((a, b) => b.revenue - a.revenue || a.venue.localeCompare(b.venue));

            if (!rows.length) {
                container.innerHTML = '<div style="font-size:12px;color:var(--text-muted);text-align:center;padding:12px;">No venue sales have been recorded yet.</div>';
                return;
            }

            const maxRevenue = Math.max(...rows.map(row => row.revenue), 1);
            container.innerHTML = rows.map(row => {
                const width = row.revenue > 0 ? Math.max(2, (row.revenue / maxRevenue) * 100) : 0;
                return `
                    <div class="venue-report-row">
                        <div class="venue-report-heading">
                            <span class="venue-report-name">${escapeHtml(row.venue)}</span>
                            <span class="venue-report-revenue">$${row.revenue.toFixed(2)}</span>
                        </div>
                        <div class="venue-report-meta">
                            ${row.transactions} transaction${row.transactions === 1 ? '' : 's'} · ${row.sold} sold · ${row.gifted} gifted
                        </div>
                        <div class="venue-report-track"><div class="venue-report-fill" style="width:${width}%"></div></div>
                    </div>`;
            }).join('');
        }

        function escapeHtml(value) {
            return String(value).replace(/[&<>"']/g, char => ({
                '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
            })[char]);
        }

'''
html = html[:stats_marker.start()] + renderer + html[stats_marker.start():]

# Add a call inside renderStats(), immediately after its opening brace.
stats_marker2 = re.search(r"function\s+renderStats\s*\(\s*\)\s*\{", html)
if not stats_marker2: fail("Could not relocate renderStats() after insertion.")
insert_at = stats_marker2.end()
html = html[:insert_at] + "\n            renderVenueReport();" + html[insert_at:]

# Validate.
for text in ['id="venue-performance-list"', 'function renderVenueReport()', 'renderVenueReport();']:
    if html.count(text) != 1: fail(f"Validation failed for {text!r}.")

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = ROOT / f"index-backup-{stamp}.html"
shutil.copy2(HTML, backup)
HTML.write_text(html, encoding="utf-8")

# Syntax check with Node if present. Restore automatically on failure.
node = shutil.which("node")
if node:
    scripts = re.findall(r"<script(?:\s[^>]*)?>([\s\S]*?)</script>", html, flags=re.I)
    if not scripts:
        shutil.copy2(backup, HTML); fail("No inline JavaScript found. Backup restored.")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(scripts[-1]); tmp = f.name
    result = subprocess.run([node, "--check", tmp], capture_output=True, text=True)
    Path(tmp).unlink(missing_ok=True)
    if result.returncode:
        shutil.copy2(backup, HTML)
        print(result.stderr)
        fail("JavaScript syntax check failed. Backup restored.")
    validation = "JavaScript syntax checked with Node."
else:
    validation = "Node not installed; check VS Code Problems before committing."

print("SUCCESS: Revenue by Venue report added to the Stats tab.")
print("BACKUP:", backup.name)
print("DATA: Uses each transaction's existing venue, revenue, sold, and gifted fields.")
print("VALIDATION:", validation)
