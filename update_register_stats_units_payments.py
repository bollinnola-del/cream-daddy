#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import re, shutil, sys

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("index.html")
if not path.exists():
    raise SystemExit("ERROR: index.html not found. Put this script beside index.html.")
text = path.read_text(encoding="utf-8")
original = text

def one(old, new, label):
    global text
    if new in text:
        print("SKIP:", label)
        return
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"ERROR: {label}: expected 1 match, found {n}. No changes saved.")
    text = text.replace(old, new, 1)
    print("APPLY:", label)

one("""            } else {
                grid.innerHTML = STATE.flavors.map(f => {
                    const remaining = getFlavorStockRemaining(f);""",
"""            } else {
                const registerFlavors = [...STATE.flavors].sort((a, b) => {
                    const aSoldOut = getFlavorStockRemaining(a) <= 0;
                    const bSoldOut = getFlavorStockRemaining(b) <= 0;
                    return Number(aSoldOut) - Number(bSoldOut);
                });
                grid.innerHTML = registerFlavors.map(f => {
                    const remaining = getFlavorStockRemaining(f);""",
"sold-out register items last")

one("""            STATE.transactions.forEach(tx => {
                const venue = String(tx.venue || 'Unspecified Venue').trim() || 'Unspecified Venue';""",
"""            getFilteredTransactions().forEach(tx => {
                const venue = String(tx.venue || 'Unspecified Venue').trim() || 'Unspecified Venue';""",
"filter Revenue by Venue")

# Stats summary and receipt fallback use the active filters.
text = text.replace("            let totalComp = 0;\n\n            STATE.transactions.forEach(tx => {", "            let totalComp = 0;\n            const filteredTransactions = getFilteredTransactions();\n\n            filteredTransactions.forEach(tx => {")
text = text.replace("                totalRevenue += (tx.totalPrice || 0);", "                totalRevenue += Number(tx.totalPrice) || 0;")
text = text.replace("                totalSold += (tx.totalUnitsSold || 0);", "                totalSold += Number(tx.totalUnitsSold) || 0;")
text = text.replace("                totalComp += (tx.totalUnitsGiven || 0);", "                totalComp += Number(tx.totalUnitsGiven) || 0;")
text = text.replace("document.getElementById('stat-txs').textContent = STATE.transactions.length;", "document.getElementById('stat-txs').textContent = filteredTransactions.length;")
text = text.replace("if (STATE.transactions.length === 0)", "if (filteredTransactions.length === 0)", 1)
text = text.replace("log.innerHTML = STATE.transactions.map(tx => {", "log.innerHTML = filteredTransactions.map(tx => {", 1)

for old,new in [("Pint Inventory & Menu","Unit Inventory & Menu"),("Pints Sold","Units Sold"),("Pints Free/Comp","Units Free/Comp"),("Paid Pints Sold:","Paid Units Sold:"),("Free / Promotional Pints:","Free / Promotional Units:")]:
    text=text.replace(old,new)

one("""                if (Array.isArray(data.transactions)) {
                    STATE.transactions = data.transactions;
                }""",
"""                if (Array.isArray(data.transactions)) {
                    STATE.transactions = data.transactions.map(tx => ({
                        ...tx,
                        paymentMethod: String(tx.paymentMethod || tx.payment || 'unknown').toLowerCase()
                    }));
                }""",
"read payment method from Sheet")

one("""                venue.className = 'receipt-log-venue';
                venue.textContent = String(tx.venue || '');""",
"""                venue.className = 'receipt-log-venue';
                const paymentLabel = ({ cash: 'Cash', card: 'Card', gift: 'Free' })[String(tx.paymentMethod || '').toLowerCase()] || 'Unknown';
                venue.textContent = `${String(tx.venue || '')} • ${paymentLabel}`;""",
"show payment method in receipt log")

text=text.replace('Timestamp,Venue,Date,OrderTotal,PaidUnits,FreeUnits,ItemsSummary', 'Timestamp,Venue,Date,PaymentMethod,OrderTotal,PaidUnits,FreeUnits,ItemsSummary')
old_csv="\"${t.date || ''}\",${t.totalPrice || 0},${t.totalUnitsSold || 0}"
new_csv="\"${t.date || ''}\",\"${t.paymentMethod || 'unknown'}\",${t.totalPrice || 0},${t.totalUnitsSold || 0}"
if old_csv in text: text=text.replace(old_csv,new_csv,1)

if re.search(r"\bPints?\b", text, re.I):
    raise SystemExit("ERROR: A Pint/Pints reference remains. No changes saved.")
for required in ["const registerFlavors = [...STATE.flavors].sort", "const filteredTransactions = getFilteredTransactions();", "PaymentMethod,OrderTotal", "paymentMethod: paymentMethod"]:
    if required not in text: raise SystemExit("ERROR: validation missing "+required)
if text == original:
    print("No changes needed.")
    raise SystemExit(0)
backup=path.with_name(f"{path.name}.backup-{datetime.now():%Y%m%d-%H%M%S}")
shutil.copy2(path,backup)
path.write_text(text,encoding="utf-8")
print("SUCCESS:",path)
print("BACKUP:",backup.name)
print("NOTE: HTML now sends/reads paymentMethod. Code.gs must write/read a Payment Method column; upload Code.gs for an exact backend patch.")
