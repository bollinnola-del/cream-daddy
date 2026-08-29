#!/usr/bin/env python3
"""Patch Cream Daddy index.html with improved empty-cart and checkout UX."""
from pathlib import Path
from datetime import datetime
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "index.html"


def stop(message):
    print(f"ERROR: {message}")
    print("No changes were saved.")
    sys.exit(1)


if not HTML.exists():
    stop(f"index.html was not found in {ROOT}. Put this script beside index.html.")

original = HTML.read_text(encoding="utf-8")
html = original

# 1. Remove only order-completion success alerts. Keep error and confirmation dialogs.
html = re.sub(
    r"^[ \t]*alert\(\s*([\'\"])(?:✅\s*)?(?:(?:Cash|Card|Venmo)\s+transaction\s+recorded!|Order\s+completed!)\1\s*\);[ \t]*\n?",
    "",
    html,
    flags=re.MULTILINE | re.IGNORECASE,
)
# Also support the dynamic success alert used by an earlier build.
html = re.sub(
    r"^[ \t]*alert\(\s*([\'\"])✅\s*[\'\"]\s*\+\s*\(paymentMethod\s*===\s*[\'\"]card[\'\"]\s*\?\s*[\'\"]Venmo[\'\"]\s*:\s*[\'\"]Cash[\'\"]\)\s*\+\s*[\'\"] transaction recorded![\'\"]\s*\);[ \t]*\n?",
    "",
    html,
    flags=re.MULTILINE,
)

# 2. Remove the empty-cart instructional message from the cart item list.
empty_cart_pattern = re.compile(
    r"(if\s*\(STATE\.cart\.length\s*===\s*0\)\s*\{)\s*"
    r"cartList\.innerHTML\s*=\s*([\'\"])[\s\S]*?Tap a flavor card below to start an order\.[\s\S]*?\2\s*;",
    re.MULTILINE,
)
html, empty_replacements = empty_cart_pattern.subn(
    r"\1\n                cartList.innerHTML = '';",
    html,
    count=1,
)
if empty_replacements == 0 and "Tap a flavor card below to start an order." in html:
    stop("Found the empty-cart wording, but its code shape was unexpected.")

# 3. Insert the message directly above checkout-actions if not already present.
message_block = '''            <div id="empty-cart-message" style="text-align:center;padding:12px;color:var(--text-muted);font-size:13px;">
                Tap a flavor card below to start an order.
            </div>
'''
if 'id="empty-cart-message"' not in html:
    marker = re.search(r'^[ \t]*<div\s+id="checkout-actions"', html, flags=re.MULTILINE)
    if not marker:
        stop('Could not find <div id="checkout-actions">.')
    html = html[:marker.start()] + message_block + html[marker.start():]

# 4. Replace showNormalCheckoutButtons with cart-aware behavior.
normal_function = '''        function showNormalCheckoutButtons() {
            const emptyMessage = document.getElementById('empty-cart-message');
            const checkoutActions = document.getElementById('checkout-actions');
            const pendingActions = document.getElementById('venmo-pending-actions');

            const cartHasItems = Array.isArray(STATE.cart) && STATE.cart.length > 0;

            if (emptyMessage) {
                emptyMessage.style.display = cartHasItems ? 'none' : 'block';
            }

            if (checkoutActions) {
                checkoutActions.style.display = cartHasItems ? 'grid' : 'none';
            }

            if (pendingActions) {
                pendingActions.style.display = 'none';
            }
        }
'''
normal_pattern = re.compile(
    r"^[ \t]*function\s+showNormalCheckoutButtons\s*\(\s*\)\s*\{[\s\S]*?^\s*\}\s*(?=\n\s*function\s+showVenmoPendingButtons)",
    re.MULTILINE,
)
html, normal_replacements = normal_pattern.subn(normal_function.rstrip(), html, count=1)
if normal_replacements != 1:
    stop("Could not safely replace showNormalCheckoutButtons().")

# 5. Ensure pending state also hides the empty message.
pending_match = re.search(
    r"function\s+showVenmoPendingButtons\s*\(\s*\)\s*\{[\s\S]*?^\s*\}",
    html,
    flags=re.MULTILINE,
)
if not pending_match:
    stop("Could not find showVenmoPendingButtons().")
pending_code = pending_match.group(0)
if "empty-cart-message" not in pending_code:
    insertion = "\n            const emptyMessage = document.getElementById('empty-cart-message');\n            if (emptyMessage) emptyMessage.style.display = 'none';\n"
    brace = pending_code.find("{") + 1
    pending_code = pending_code[:brace] + insertion + pending_code[brace:]
    html = html[:pending_match.start()] + pending_code + html[pending_match.end():]

# 6. Ensure renderRegister refreshes the checkout controls after every cart render.
render_match = re.search(
    r"function\s+renderRegister\s*\(\s*\)\s*\{[\s\S]*?\n\s*\}\s*(?=\n\s*function\s+renderInventoryTable)",
    html,
)
if not render_match:
    stop("Could not find the complete renderRegister() function.")
render_code = render_match.group(0)
if "showNormalCheckoutButtons();" not in render_code:
    last_brace = render_code.rfind("}")
    render_code = render_code[:last_brace] + "            showNormalCheckoutButtons();\n        " + render_code[last_brace:]
    html = html[:render_match.start()] + render_code + html[render_match.end():]

# 7. Validation.
required = [
    'id="empty-cart-message"',
    'id="checkout-actions"',
    'id="venmo-pending-actions"',
    "function showNormalCheckoutButtons()",
    "function showVenmoPendingButtons()",
]
missing = [item for item in required if item not in html]
if missing:
    stop("Validation failed. Missing: " + ", ".join(missing))
if html == original:
    print("No update needed. The requested UX changes already appear to be installed.")
    sys.exit(0)

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = ROOT / f"index-backup-{stamp}.html"
shutil.copy2(HTML, backup)
HTML.write_text(html, encoding="utf-8")

print("SUCCESS: Updated checkout UX in index.html")
print(f"BACKUP: {backup.name}")
print("CHANGES:")
print("  - Removed order-completion success alerts")
print("  - Moved the empty-cart instruction to the checkout area")
print("  - Cash and Card stay hidden until the cart has an item")
print("  - Venmo pending controls continue to replace Cash and Card")
