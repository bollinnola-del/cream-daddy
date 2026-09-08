#!/usr/bin/env python3
"""Replace Cream Daddy UI Polish V2 with renderer-connected V3.

V3 preserves the existing live counter IDs, so the app's current cart renderer
continues updating Paid and Free counts without observers or duplicate state.
"""
from pathlib import Path
from datetime import datetime
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"
V2_CSS = "/* Cream Daddy UI Polish V2 */"
V2_JS = "// Cream Daddy UI Polish V2"
V3_JS = "// Cream Daddy UI Polish V3"


def fail(message):
    print("ERROR:", message)
    print("No changes were saved.")
    sys.exit(1)


def remove_to_closing(text, marker, closing):
    if marker not in text:
        return text
    start = text.find(marker)
    end = text.find(closing, start)
    if end < 0:
        fail(f"Found {marker!r} but not its closing {closing!r}.")
    return text[:start] + text[end:]


if not INDEX.exists():
    fail("index.html was not found. Put this script beside index.html.")

original = INDEX.read_text(encoding="utf-8")
html = original

if V3_JS in html:
    print("No update needed. Cream Daddy UI Polish V3 is already installed.")
    sys.exit(0)

# Remove the consolidated V2 layer. V3 re-adds its retained behavior.
html = remove_to_closing(html, V2_CSS, "</style>")
html = remove_to_closing(html, V2_JS, "</script>")

for required in [
    'id="cart-paid-units"',
    'id="cart-comp-units"',
    'id="cart-total-price"',
    'id="empty-cart-message"',
    'class="cart-items-list"',
    "transactions-history-list",
    "STATE.transactions",
]:
    if required not in html:
        fail(f"Expected current app code is missing: {required}")

# Replace the exact summary markup while preserving the counter IDs used by the
# existing cart renderer.
summary_pattern = re.compile(
    r'''<div class="cart-summary">\s*
\s*<div class="summary-row">\s*
\s*<span>Paid Units Sold</span>\s*
\s*<span id="cart-paid-units">0</span>\s*
\s*</div>\s*
\s*<div class="summary-row">\s*
\s*<span>Free / Comps</span>\s*
\s*<span id="cart-comp-units">0</span>\s*
\s*</div>\s*
\s*<div class="summary-row total-row">\s*
\s*<span>Order Total</span>\s*
\s*<span id="cart-total-price">\$0\.00</span>\s*
\s*</div>\s*
\s*</div>''',
    re.I,
)
summary_replacement = '''<div class="cart-summary">
                <div class="summary-row total-row">
                    <span>
                        Order Total
                        <span class="order-total-counts">
                            (Paid: <strong id="cart-paid-units">0</strong> • Free: <strong id="cart-comp-units">0</strong>)
                        </span>
                    </span>
                    <span id="cart-total-price">$0.00</span>
                </div>
            </div>'''
html, summary_count = summary_pattern.subn(summary_replacement, html, count=1)
if summary_count != 1:
    fail("Could not safely replace the current Order Total summary markup.")

# Keep the element for any existing renderer references, but remove its copy and
# make it permanently nonvisual.
empty_pattern = re.compile(
    r'''(<div\s+id="empty-cart-message"[^>]*>)[\s\S]*?(</div>)''',
    re.I,
)
html, empty_count = empty_pattern.subn(r'''\1\2''', html, count=1)
if empty_count != 1:
    fail("Could not safely clear the empty-cart helper message.")

# Normalize literal labels in current static/template HTML. The runtime V3 helper
# also normalizes labels after each cart render.
html = re.sub(r"FREE\s*/\s*COMP", "Free", html, flags=re.I)
html = html.replace("🎁 Gift", "🎁 Free")
html = html.replace("$ Paid", "💲 Paid")
html = html.replace("$Paid", "💲 Paid")

css = r'''
        /* Cream Daddy UI Polish V3 */
        :root { --app-header-height: 54px; }

        header {
            min-height: var(--app-header-height) !important;
            height: var(--app-header-height) !important;
            padding-top: 7px !important;
            padding-bottom: 7px !important;
        }
        header .brand-logo-img { max-height: 32px !important; }
        .bottom-nav { height: var(--app-header-height) !important; }
        body { padding-bottom: calc(var(--app-header-height) + 25px) !important; }

        #tab-register .cart-section {
            position: sticky;
            top: var(--app-header-height);
            z-index: 90;
        }

        #empty-cart-message { display: none !important; }

        #tab-register .cart-items-list {
            max-height: 150px !important;
            overflow-y: auto !important;
            overscroll-behavior: contain;
            scrollbar-gutter: stable;
        }

        #tab-register .cart-item-row {
            height: 52px !important;
            min-height: 52px !important;
            flex: 0 0 52px !important;
            overflow: hidden;
        }

        #tab-register .cart-item-row .item-actions {
            align-self: stretch;
            height: calc(100% + 16px);
            min-height: calc(100% + 16px);
            margin-top: -8px;
            margin-right: -10px;
            margin-bottom: -8px;
            display: flex;
            align-items: stretch;
        }

        #tab-register .cart-item-row .item-actions > button,
        #tab-register .cart-item-row .item-actions .btn-comp-toggle,
        #tab-register .cart-item-row .item-actions .qty-stepper {
            height: 100%;
            min-height: 100%;
            border-radius: 0;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .order-total-counts {
            font-size: 12px;
            font-weight: 400;
            color: var(--text-muted);
            white-space: nowrap;
        }
        .order-total-counts strong {
            color: var(--text-dark);
            font-weight: 900;
        }

        .btn-comp-toggle.is-free {
            background: var(--success) !important;
            color: #fff !important;
            border-color: var(--success) !important;
        }

        .item-details-sub.free-item-text {
            color: var(--success) !important;
            font-weight: 800 !important;
        }

        #gift-actions .btn-checkout {
            background: var(--success) !important;
            color: #fff !important;
        }

        .receipt-log-row {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            grid-template-areas: "items total" "time venue";
            column-gap: 12px;
            row-gap: 5px;
            padding: 11px 0;
            border-bottom: 1px solid var(--border-color);
            font-size: 12px;
        }
        .receipt-log-items {
            grid-area: items;
            min-width: 0;
            color: var(--text-dark);
            font-weight: 800;
            overflow-wrap: anywhere;
        }
        .receipt-log-total {
            grid-area: total;
            color: var(--text-dark);
            font-weight: 900;
            white-space: nowrap;
            text-align: right;
        }
        .receipt-log-time {
            grid-area: time;
            color: var(--text-muted);
            font-weight: 400;
        }
        .receipt-log-venue {
            grid-area: venue;
            color: var(--text-muted);
            font-weight: 400;
            text-align: right;
            white-space: nowrap;
        }

        @media (max-width: 420px) {
            .receipt-log-row { column-gap: 8px; }
            .receipt-log-venue {
                max-width: 145px;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            .order-total-counts { font-size: 11px; }
        }
'''

if html.count("</style>") != 1:
    fail("Expected exactly one </style> tag.")
html = html.replace("</style>", css + "\n    </style>", 1)

js = r'''
        // Cream Daddy UI Polish V3
        function uiV3NormalizeCartLabels() {
            const root = document.getElementById('tab-register');
            if (!root) return;

            root.querySelectorAll('.btn-comp-toggle').forEach(button => {
                const isFree = button.classList.contains('is-free');
                button.textContent = isFree ? '🎁 Free' : '💲 Paid';
            });

            root.querySelectorAll('.item-details-sub').forEach(element => {
                const text = element.textContent.replace(/\s+/g, ' ').trim();
                if (/^free(?:\s*\/\s*comp)?$/i.test(text)) {
                    element.textContent = 'Free';
                    element.classList.add('free-item-text');
                } else {
                    element.classList.remove('free-item-text');
                }
            });

            const freeCheckout = document.querySelector('#gift-actions .btn-checkout');
            if (freeCheckout) freeCheckout.textContent = '🎁 Free';
        }

        function uiV3FormatReceiptDate(value) {
            const raw = String(value || '').trim();
            const parsed = new Date(raw);
            if (Number.isNaN(parsed.getTime())) return raw;
            const month = String(parsed.getMonth() + 1).padStart(2, '0');
            const day = String(parsed.getDate()).padStart(2, '0');
            const year = parsed.getFullYear();
            const hours = String(parsed.getHours()).padStart(2, '0');
            const minutes = String(parsed.getMinutes()).padStart(2, '0');
            const seconds = String(parsed.getSeconds()).padStart(2, '0');
            return `${month}/${day}/${year} • ${hours}:${minutes}:${seconds}`;
        }

        function uiV3ReceiptItems(tx) {
            const items = Array.isArray(tx.items) ? tx.items : [];
            if (items.length) {
                return items.map(item => {
                    const qty = Number(item.qty ?? item.quantity) || 0;
                    return `${qty}× ${String(item.name || 'Item').trim()}${item.isComp ? ' [Free]' : ''}`;
                }).join(', ');
            }
            return String(tx.summary || 'Items summary').replace(/\[FREE\]/gi, '[Free]');
        }

        function uiV3RenderReceiptLog() {
            const log = document.getElementById('transactions-history-list');
            if (!log) return;
            const transactions = typeof getFilteredTransactions === 'function'
                ? getFilteredTransactions()
                : (STATE.transactions || []);
            if (!transactions.length) {
                log.innerHTML = '<div style="font-size:12px;color:var(--text-muted);text-align:center;padding:12px;">No transactions match the selected filters.</div>';
                return;
            }

            log.innerHTML = '';
            transactions.forEach(tx => {
                const row = document.createElement('div');
                row.className = 'receipt-log-row';
                const items = document.createElement('div');
                items.className = 'receipt-log-items';
                items.textContent = uiV3ReceiptItems(tx);
                const total = document.createElement('div');
                total.className = 'receipt-log-total';
                total.textContent = `$${(Number(tx.totalPrice) || 0).toFixed(2)}`;
                const time = document.createElement('div');
                time.className = 'receipt-log-time';
                time.textContent = uiV3FormatReceiptDate(tx.timestamp || tx.date);
                const venue = document.createElement('div');
                venue.className = 'receipt-log-venue';
                venue.textContent = String(tx.venue || '');
                row.append(items, total, time, venue);
                log.appendChild(row);
            });
        }

        window.addEventListener('DOMContentLoaded', () => {
            uiV3NormalizeCartLabels();
            uiV3RenderReceiptLog();

            const register = document.getElementById('tab-register');
            if (register) {
                let queued = false;
                new MutationObserver(() => {
                    if (queued) return;
                    queued = true;
                    requestAnimationFrame(() => {
                        queued = false;
                        uiV3NormalizeCartLabels();
                    });
                }).observe(register, { childList: true, subtree: true, characterData: true });
            }

            const receiptLog = document.getElementById('transactions-history-list');
            if (receiptLog) {
                let queued = false;
                new MutationObserver(() => {
                    if (queued || receiptLog.querySelector('.receipt-log-row')) return;
                    queued = true;
                    requestAnimationFrame(() => {
                        queued = false;
                        uiV3RenderReceiptLog();
                    });
                }).observe(receiptLog, { childList: true });
            }
        });
'''

last_script = html.rfind("</script>")
if last_script < 0:
    fail("Could not locate the final </script> tag.")
html = html[:last_script] + "\n" + js + "\n" + html[last_script:]

for required in [
    V3_JS,
    'id="cart-paid-units"',
    'id="cart-comp-units"',
    "Order Total",
    "🎁 Free",
    "💲 Paid",
    "max-height: 150px",
    "height: 52px",
    "receipt-log-row",
]:
    if required not in html:
        fail(f"Final validation failed for: {required}")
if V2_CSS in html or V2_JS in html:
    fail("UI Polish V2 still remains after migration.")

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = ROOT / f"index-backup-{stamp}.html"
shutil.copy2(INDEX, backup)
INDEX.write_text(html, encoding="utf-8")

node = shutil.which("node")
if node:
    scripts = re.findall(r"<script(?:\s[^>]*)?>([\s\S]*?)</script>", html, re.I)
    if not scripts:
        shutil.copy2(backup, INDEX)
        fail("No inline JavaScript found. Backup restored.")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as temp:
        temp.write(scripts[-1])
        temp_path = temp.name
    result = subprocess.run([node, "--check", temp_path], capture_output=True, text=True)
    Path(temp_path).unlink(missing_ok=True)
    if result.returncode:
        shutil.copy2(backup, INDEX)
        print(result.stderr)
        fail("JavaScript syntax validation failed. Backup restored.")
    validation = "JavaScript syntax checked with Node."
else:
    validation = "Node not installed. Check VS Code Problems and browser Console before committing."

print("SUCCESS: Cream Daddy UI Polish V3 installed.")
print("BACKUP:", backup.name)
print("MIGRATION:")
print("  - Removed UI Polish V2 CSS and JavaScript")
print("  - Preserved the app's live cart count IDs in the Order Total line")
print("UPDATES:")
print("  - Order Total shows live Paid and Free counts")
print("  - Paid toggle displays 💲 Paid")
print("  - Free toggle and free checkout display 🎁 Free")
print("  - Free item subtext displays Free in success green")
print("  - Empty-cart prompt is hidden")
print("  - Cart rows stay 52px high and list scrolls at 150px")
print("  - Header, sticky order card, bottom nav, full-height actions, and receipt layout retained")
print("VALIDATION:", validation)
