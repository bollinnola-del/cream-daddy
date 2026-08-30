#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import re, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parent
HTML = ROOT / 'index.html'

def fail(msg):
    print('ERROR:', msg)
    print('No changes were saved.')
    sys.exit(1)

if not HTML.exists():
    fail('Put this script in the same folder as index.html.')

original = HTML.read_text(encoding='utf-8')
html = original
if 'function getInventoryStatus(remaining)' in html:
    fail('An earlier low-stock patch is already installed. Restore index.html to the clean committed version first.')

# Visible terminology only.
replacements = {
    'Pint Inventory & Menu':'Unit Inventory & Menu',
    'Pints Sold':'Units Sold',
    'Pints Free/Comp':'Units Gifted',
    'Paid Pints Sold':'Paid Units Sold',
    'Free / Promotional Pints':'Free / Promotional Units',
    'Free Promotional Pints':'Free Promotional Units',
    'Total Pints':'Total Units',
    'Pint Inventory':'Unit Inventory',
}
for old, new in replacements.items():
    html = html.replace(old, new)
html = re.sub(r'\bPints\b', 'Units', html)
html = re.sub(r'\bPint\b', 'Unit', html)
html = re.sub(r'\bpints\b', 'units', html)
html = re.sub(r'\bpint\b', 'unit', html)

# Warning styles.
low_css = '''        .flavor-stock-tag.low {
            background: #fee2e2;
            color: var(--danger);
        }'''
if html.count(low_css) != 1:
    fail('Could not uniquely find the existing low-stock CSS.')
html = html.replace(low_css, low_css + '''
        .flavor-stock-tag.sold-out {
            background: var(--brand-black);
            color: var(--brand-white);
        }
        .flavor-card.out-of-stock { cursor: not-allowed; }
        .inventory-status-low { color:#b45309; font-weight:800; white-space:nowrap; }
        .inventory-status-out { color:var(--danger); font-weight:900; white-space:nowrap; }''', 1)

# Shared status helper.
render_anchor = re.search(r'^[ \t]*function\s+renderRegister\s*\(\s*\)\s*\{', html, re.M)
if not render_anchor:
    fail('Could not find renderRegister().')
helper = '''        function getInventoryStatus(remaining) {
            const count = Math.max(0, Number(remaining) || 0);
            if (count === 0) {
                return { text: '🚫 SOLD OUT', className: 'sold-out', inventoryClass: 'inventory-status-out' };
            }
            if (count <= 3) {
                return { text: `⚠️ ${count} Left`, className: 'low', inventoryClass: 'inventory-status-low' };
            }
            return { text: `${count} Left`, className: '', inventoryClass: '' };
        }

'''
html = html[:render_anchor.start()] + helper + html[render_anchor.start():]

# Stable sort: sold-out products go to bottom, others keep original order.
old_map = 'grid.innerHTML = STATE.flavors.map(f => {'
if html.count(old_map) != 1:
    fail('Could not uniquely find the Register product list.')
new_map = '''const sortedFlavors = STATE.flavors
                    .map((flavor, originalIndex) => ({ flavor, originalIndex }))
                    .sort((a, b) => {
                        const aOut = getFlavorStockRemaining(a.flavor) <= 0 ? 1 : 0;
                        const bOut = getFlavorStockRemaining(b.flavor) <= 0 ? 1 : 0;
                        return aOut - bOut || a.originalIndex - b.originalIndex;
                    })
                    .map(entry => entry.flavor);

                grid.innerHTML = sortedFlavors.map(f => {'''
html = html.replace(old_map, new_map, 1)

# Exact clean flavor-card block. Stock count is placed before price.
old_card = '''                    const remaining = getFlavorStockRemaining(f);
                    const isOut = remaining <= 0;
                    return `
                        <div class="flavor-card ${isOut ? 'out-of-stock' : ''}" onclick="addToCart('${f.id}')">
                            <div class="flavor-img-wrapper">
                                ${f.photo ? `<img src="${f.photo}" alt="${f.name}">` : `<span class="flavor-fallback-icon">🍦</span>`}
                            </div>
                            <div class="flavor-name">${f.name}</div>
                            <div class="flavor-price">$${f.price.toFixed(2)}</div>
                            <div class="flavor-stock-tag ${remaining <= 3 ? 'low' : ''}">${remaining} Left</div>
                        </div>
                    `;'''
new_card = '''                    const remaining = getFlavorStockRemaining(f);
                    const isOut = remaining <= 0;
                    const status = getInventoryStatus(remaining);
                    const clickAction = isOut ? '' : `onclick="addToCart('${f.id}')"`;
                    return `
                        <div class="flavor-card ${isOut ? 'out-of-stock' : ''}" ${clickAction} aria-disabled="${isOut}">
                            <div class="flavor-img-wrapper">
                                ${f.photo ? `<img src="${f.photo}" alt="${f.name}">` : `<span class="flavor-fallback-icon">🍦</span>`}
                            </div>
                            <div class="flavor-name">${f.name}</div>
                            <div class="flavor-stock-tag ${status.className}">${status.text}</div>
                            <div class="flavor-price">$${f.price.toFixed(2)}</div>
                        </div>
                    `;'''
if html.count(old_card) != 1:
    fail('The current product-card code does not match the verified clean version.')
html = html.replace(old_card, new_card, 1)

# Inventory table status.
old_setup = '''                const counts = getFlavorCounts(f.id);
                const left = Math.max(0, Number(f.currentStock != null ? f.currentStock : f.startingStock) || 0);
                return `'''
new_setup = '''                const counts = getFlavorCounts(f.id);
                const left = Math.max(0, Number(f.currentStock != null ? f.currentStock : f.startingStock) || 0);
                const inventoryStatus = getInventoryStatus(left);
                return `'''
if html.count(old_setup) != 1:
    fail('Could not find the Inventory table row setup.')
html = html.replace(old_setup, new_setup, 1)
old_cell = '''                        <td><strong style="${left <= 3 ? 'color:var(--danger);' : ''}">${left}</strong></td>'''
new_cell = '''                        <td><span class="${inventoryStatus.inventoryClass}">${inventoryStatus.text}</span></td>'''
if html.count(old_cell) != 1:
    fail('Could not find the Inventory table Left cell.')
html = html.replace(old_cell, new_cell, 1)

# Validate before writing.
for text in ['⚠️ ${count} Left', '🚫 SOLD OUT', 'const sortedFlavors = STATE.flavors',
             'const clickAction = isOut', 'const inventoryStatus = getInventoryStatus(left);']:
    if html.count(text) != 1:
        fail(f'Validation failed for {text!r}.')
if re.search(r'\b[Pp]int(?:s)?\b', html):
    fail('Visible Pint/Pints wording remains.')

stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
backup = ROOT / f'index-backup-{stamp}.html'
shutil.copy2(HTML, backup)
HTML.write_text(html, encoding='utf-8')

node = shutil.which('node')
if node:
    scripts = re.findall(r'<script(?:\s[^>]*)?>([\s\S]*?)</script>', html, re.I)
    if not scripts:
        shutil.copy2(backup, HTML); fail('No inline JavaScript found. Backup restored.')
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
        f.write(scripts[-1]); temp_js = f.name
    result = subprocess.run([node, '--check', temp_js], capture_output=True, text=True)
    Path(temp_js).unlink(missing_ok=True)
    if result.returncode:
        shutil.copy2(backup, HTML)
        print(result.stderr)
        fail('JavaScript syntax failed. Backup restored.')
    validation = 'JavaScript syntax checked with Node.'
else:
    validation = 'Node not installed. Check VS Code Problems before committing.'

print('SUCCESS: Final low-stock and Units patch installed.')
print('BACKUP:', backup.name)
print('BEHAVIOR:')
print('  - 4+: X Left')
print('  - 1-3: ⚠️ X Left')
print('  - 0: 🚫 SOLD OUT, disabled, moved to bottom')
print('  - Product cards show stock before price')
print('  - Visible Pint/Pints wording changed to Unit/Units')
print('VALIDATION:', validation)
