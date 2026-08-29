#!/usr/bin/env python3
"""Safely add Gift-only checkout behavior to Cream Daddy index.html."""
from pathlib import Path
from datetime import datetime
import re, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "index.html"

def fail(msg):
    print("ERROR:", msg)
    print("No changes were saved.")
    sys.exit(1)

def replace_js_function(source, function_name, replacement):
    """Replace a named `function name(...) { ... }` using brace matching, not regex."""
    start_match = re.search(rf"function\s+{re.escape(function_name)}\s*\([^)]*\)\s*\{{", source)
    if not start_match:
        fail(f"Could not find function {function_name}().")
    brace_start = source.find("{", start_match.start())
    depth = 0
    i = brace_start
    quote = None
    escape = False
    line_comment = False
    block_comment = False
    while i < len(source):
        c = source[i]
        n = source[i + 1] if i + 1 < len(source) else ""
        if line_comment:
            if c == "\n": line_comment = False
        elif block_comment:
            if c == "*" and n == "/": block_comment = False; i += 1
        elif quote:
            if escape: escape = False
            elif c == "\\": escape = True
            elif c == quote: quote = None
        else:
            if c == "/" and n == "/": line_comment = True; i += 1
            elif c == "/" and n == "*": block_comment = True; i += 1
            elif c in ("'", '"', "`"): quote = c
            elif c == "{": depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return source[:start_match.start()] + replacement + source[i + 1:]
        i += 1
    fail(f"Could not find the closing brace for {function_name}().")

if not HTML.exists():
    fail(f"index.html was not found in {ROOT}. Put this script beside index.html.")

original = HTML.read_text(encoding="utf-8")
html = original

# Validate baseline anchors from the uploaded working version.
for anchor in ['id="checkout-actions"', 'id="venmo-pending-actions"',
               "function showNormalCheckoutButtons()", "function showVenmoPendingButtons()"]:
    if anchor not in html:
        fail(f"Expected anchor is missing: {anchor}")
if 'id="gift-actions"' in html:
    print("No update needed. Gift checkout is already installed.")
    sys.exit(0)

# Add a separate Gift action area immediately before the Venmo-pending area.
marker = "            <!-- Only shown after Card is pressed -->"
if html.count(marker) != 1:
    fail("Could not uniquely locate the Venmo pending controls.")
gift_html = '''            <!-- Only shown when every item in the cart is free -->
            <div id="gift-actions" style="display:none;">
                <button class="btn-checkout" style="background:#10b981;color:#fff;" onclick="completeSale('gift')">
                    🎁 Gift
                </button>
            </div>
'''
html = html.replace(marker, gift_html + marker, 1)

normal_fn = '''function showNormalCheckoutButtons() {
            const emptyMessage = document.getElementById('empty-cart-message');
            const checkoutActions = document.getElementById('checkout-actions');
            const giftActions = document.getElementById('gift-actions');
            const pendingActions = document.getElementById('venmo-pending-actions');

            const cartHasItems = Array.isArray(STATE.cart) && STATE.cart.length > 0;
            const allItemsFree = cartHasItems && STATE.cart.every(item => item.isComp === true);

            if (emptyMessage) {
                emptyMessage.style.display = cartHasItems ? 'none' : 'block';
            }
            if (checkoutActions) {
                checkoutActions.style.display = cartHasItems && !allItemsFree ? 'grid' : 'none';
            }
            if (giftActions) {
                giftActions.style.display = allItemsFree ? 'block' : 'none';
            }
            if (pendingActions) {
                pendingActions.style.display = 'none';
            }
        }'''
html = replace_js_function(html, "showNormalCheckoutButtons", normal_fn)

pending_fn = '''function showVenmoPendingButtons() {
            const emptyMessage = document.getElementById('empty-cart-message');
            const checkoutActions = document.getElementById('checkout-actions');
            const giftActions = document.getElementById('gift-actions');
            const pendingActions = document.getElementById('venmo-pending-actions');

            if (emptyMessage) emptyMessage.style.display = 'none';
            if (checkoutActions) checkoutActions.style.display = 'none';
            if (giftActions) giftActions.style.display = 'none';
            if (pendingActions) pendingActions.style.display = 'grid';
        }'''
html = replace_js_function(html, "showVenmoPendingButtons", pending_fn)

# Final structural checks before writing.
checks = {
    'gift area': 'id="gift-actions"',
    'gift completion': "completeSale('gift')",
    'all-free test': 'STATE.cart.every(item => item.isComp === true)',
}
for label, text in checks.items():
    if html.count(text) != 1:
        fail(f"Validation failed for {label}; found {html.count(text)} occurrences.")

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = ROOT / f"index-backup-{stamp}.html"
shutil.copy2(HTML, backup)
HTML.write_text(html, encoding="utf-8")

# If Node is installed, syntax-check the last inline script. Roll back automatically on failure.
node = shutil.which("node")
if node:
    scripts = re.findall(r"<script(?:\s[^>]*)?>([\s\S]*?)</script>", html, flags=re.I)
    if not scripts:
        shutil.copy2(backup, HTML); fail("No inline JavaScript was found; restored backup.")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(scripts[-1]); js_path = f.name
    result = subprocess.run([node, "--check", js_path], capture_output=True, text=True)
    Path(js_path).unlink(missing_ok=True)
    if result.returncode != 0:
        shutil.copy2(backup, HTML)
        print(result.stderr)
        fail("JavaScript syntax validation failed; the backup was restored.")
    validation = "JavaScript syntax checked with Node."
else:
    validation = "Node was not installed, so use VS Code Problems to verify JavaScript syntax."

print("SUCCESS: Gift-only checkout behavior installed.")
print(f"BACKUP: {backup.name}")
print("BEHAVIOR:")
print("  - Empty cart: instructional message")
print("  - Any paid item: Cash and Card")
print("  - Every item free: Gift only")
print("  - Venmo pending: Cancel and Confirm")
print("VALIDATION:", validation)
