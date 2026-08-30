#!/usr/bin/env python3
"""Add product thumbnails to Revenue by Product and remove Export Shift Data."""
from pathlib import Path
from datetime import datetime
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "index.html"


def fail(message):
    print("ERROR:", message)
    print("No changes were saved.")
    sys.exit(1)


def find_matching_brace(source, opening_brace):
    depth = 0
    quote = None
    escaped = False
    line_comment = False
    block_comment = False
    i = opening_brace

    while i < len(source):
        char = source[i]
        next_char = source[i + 1] if i + 1 < len(source) else ""

        if line_comment:
            if char == "\n":
                line_comment = False
        elif block_comment:
            if char == "*" and next_char == "/":
                block_comment = False
                i += 1
        elif quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        else:
            if char == "/" and next_char == "/":
                line_comment = True
                i += 1
            elif char == "/" and next_char == "*":
                block_comment = True
                i += 1
            elif char in ("'", '"', "`"):
                quote = char
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1

    fail("Could not find a matching JavaScript closing brace.")


def get_function_range(source, function_name):
    match = re.search(
        rf"function\s+{re.escape(function_name)}\s*\([^)]*\)\s*\{{",
        source,
    )
    if not match:
        fail(f"Could not find {function_name}().")
    opening = source.find("{", match.start())
    closing = find_matching_brace(source, opening)
    return match.start(), closing + 1


if not HTML.exists():
    fail(f"index.html was not found in {ROOT}. Put this script beside index.html.")

original = HTML.read_text(encoding="utf-8")
html = original

if "product-report-thumb" in html:
    print("No update needed. Product report thumbnails already appear to be installed.")
    sys.exit(0)

required = [
    'id="product-performance-list"',
    "function renderProductReport()",
    "function escapeHtml(value)",
]
for anchor in required:
    if anchor not in html:
        fail(f"Expected code is missing: {anchor}")

# 1. Remove the complete Export Shift Data card using exact structural content.
export_card_pattern = re.compile(
    r'''\s*<div class="card">\s*
\s*<div class="card-title" style="margin-bottom:\s*10px;">📄\s*Export Shift Data</div>\s*
\s*<div style="display:\s*flex;\s*gap:\s*8px;">\s*
\s*<button class="btn-primary" style="flex:1;" onclick="copyGoogleDocSummary\(\)">[\s\S]*?</button>\s*
\s*<button class="btn-gold" style="flex:1;" onclick="exportCSV\(\)">[\s\S]*?</button>\s*
\s*</div>\s*
\s*</div>''',
    re.MULTILINE,
)
html, removed_cards = export_card_pattern.subn("", html, count=1)
if removed_cards != 1:
    fail("Could not safely locate the complete Export Shift Data card.")

# 2. Add compact thumbnail styles before </style>.
style_anchor = "    </style>"
if html.count(style_anchor) != 1:
    fail("Could not uniquely locate </style>.")
thumbnail_styles = '''
        .product-report-title {
            display: flex;
            align-items: center;
            gap: 10px;
            min-width: 0;
        }
        .product-report-thumb,
        .product-report-fallback {
            width: 32px;
            height: 32px;
            border-radius: 8px;
            flex: 0 0 32px;
            border: 1px solid var(--brand-gold);
        }
        .product-report-thumb {
            display: block;
            object-fit: cover;
            background: #f3f4f6;
        }
        .product-report-fallback {
            display: flex;
            align-items: center;
            justify-content: center;
            background: #f3f4f6;
            font-size: 18px;
        }
        .product-report-title .venue-report-name {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
'''
html = html.replace(style_anchor, thumbnail_styles + style_anchor, 1)

# 3. Replace only renderProductReport(), using brace matching rather than a broad regex.
start, end = get_function_range(html, "renderProductReport")
product_function = '''function renderProductReport() {
            const container = document.getElementById('product-performance-list');
            if (!container) return;

            const products = {};

            STATE.transactions.forEach(tx => {
                (tx.items || []).forEach(item => {
                    const name = String(item.name || 'Unknown Product').trim();

                    if (!products[name]) {
                        products[name] = {
                            revenue: 0,
                            sold: 0,
                            gifted: 0
                        };
                    }

                    const qty = Number(item.qty) || 0;
                    const price = Number(item.price) || 0;

                    if (item.isComp) {
                        products[name].gifted += qty;
                    } else {
                        products[name].sold += qty;
                        products[name].revenue += qty * price;
                    }
                });
            });

            const rows = Object.entries(products)
                .map(([name, values]) => ({ name, ...values }))
                .sort((a, b) => b.revenue - a.revenue || a.name.localeCompare(b.name));

            if (!rows.length) {
                container.innerHTML = '<div style="font-size:12px;color:var(--text-muted);text-align:center;padding:12px;">No product sales have been recorded yet.</div>';
                return;
            }

            const maxRevenue = Math.max(...rows.map(row => row.revenue), 1);

            container.innerHTML = rows.map(row => {
                const width = row.revenue > 0
                    ? Math.max(2, (row.revenue / maxRevenue) * 100)
                    : 0;

                const catalogProduct = STATE.flavors.find(flavor =>
                    String(flavor.name || '').trim().toLowerCase() === row.name.toLowerCase()
                );

                const imageHtml = catalogProduct && catalogProduct.photo
                    ? `<img class="product-report-thumb" src="${escapeHtml(catalogProduct.photo)}" alt="">`
                    : '<div class="product-report-fallback" aria-hidden="true">🍦</div>';

                return `
                    <div class="venue-report-row">
                        <div class="venue-report-heading">
                            <div class="product-report-title">
                                ${imageHtml}
                                <span class="venue-report-name">${escapeHtml(row.name)}</span>
                            </div>
                            <span class="venue-report-revenue">$${row.revenue.toFixed(2)}</span>
                        </div>
                        <div class="venue-report-meta">
                            ${row.sold} sold · ${row.gifted} gifted
                        </div>
                        <div class="venue-report-track">
                            <div class="venue-report-fill" style="width:${width}%"></div>
                        </div>
                    </div>`;
            }).join('');
        }'''
html = html[:start] + product_function + html[end:]

# 4. Validate expected final structure before writing.
checks = {
    "thumbnail CSS": ".product-report-thumb",
    "fallback CSS": ".product-report-fallback",
    "product lookup": "const catalogProduct = STATE.flavors.find",
    "report container": 'id="product-performance-list"',
    "product renderer": "function renderProductReport()",
}
for label, text in checks.items():
    if text not in html:
        fail(f"Validation failed for {label}.")

if "📄 Export Shift Data" in html:
    fail("Export Shift Data card still exists after replacement.")

# 5. Backup and write.
stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = ROOT / f"index-backup-{stamp}.html"
shutil.copy2(HTML, backup)
HTML.write_text(html, encoding="utf-8")

# 6. Syntax-check the final inline JavaScript when Node is available.
node = shutil.which("node")
if node:
    scripts = re.findall(r"<script(?:\s[^>]*)?>([\s\S]*?)</script>", html, flags=re.I)
    if not scripts:
        shutil.copy2(backup, HTML)
        fail("No inline JavaScript was found. Backup restored.")

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as temp:
        temp.write(scripts[-1])
        temp_path = temp.name

    result = subprocess.run([node, "--check", temp_path], capture_output=True, text=True)
    Path(temp_path).unlink(missing_ok=True)

    if result.returncode != 0:
        shutil.copy2(backup, HTML)
        print(result.stderr)
        fail("JavaScript syntax validation failed. Backup restored.")

    validation = "JavaScript syntax checked with Node."
else:
    validation = "Node not installed. Check VS Code Problems before committing."

print("SUCCESS: Revenue by Product v2 installed.")
print("BACKUP:", backup.name)
print("CHANGES:")
print("  - Added 32px product images to Revenue by Product")
print("  - Added 🍦 fallback when no product image is available")
print("  - Removed the Export Shift Data card")
print("VALIDATION:", validation)
