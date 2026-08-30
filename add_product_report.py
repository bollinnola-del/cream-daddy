#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime
import shutil
import re
import sys

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "index.html"

def fail(msg):
    print("ERROR:", msg)
    sys.exit(1)

if not HTML.exists():
    fail("index.html not found")

html = HTML.read_text(encoding="utf-8")

if 'id="product-performance-list"' in html:
    fail("Revenue by Product already appears to be installed")

# --------------------------------------------------
# Add card directly below Revenue by Venue
# --------------------------------------------------

venue_card = """
        <div class="card">
            <div class="card-header-row">
                <div class="card-title">📍 Revenue by Venue</div>
                <span style="font-size:11px;color:var(--text-muted);">Highest revenue first</span>
            </div>
            <div id="venue-performance-list"></div>
        </div>
"""

product_card = """
        <div class="card">
            <div class="card-header-row">
                <div class="card-title">🍦 Revenue by Product</div>
                <span style="font-size:11px;color:var(--text-muted);">Highest revenue first</span>
            </div>
            <div id="product-performance-list"></div>
        </div>
"""

if venue_card not in html:
    fail("Could not locate Revenue by Venue card")

html = html.replace(
    venue_card,
    venue_card + "\n" + product_card,
    1
)

# --------------------------------------------------
# Add renderProductReport()
# --------------------------------------------------

anchor = "function renderVenueReport() {"

if anchor not in html:
    fail("Could not locate renderVenueReport()")

product_renderer = """
        function renderProductReport() {
            const container = document.getElementById('product-performance-list');
            if (!container) return;

            const products = {};

            STATE.transactions.forEach(tx => {
                (tx.items || []).forEach(item => {

                    const name =
                        String(item.name || 'Unknown Product').trim();

                    if (!products[name]) {
                        products[name] = {
                            revenue: 0,
                            sold: 0,
                            gifted: 0
                        };
                    }

                    const qty =
                        Number(item.qty) || 0;

                    const price =
                        Number(item.price) || 0;

                    if (item.isComp) {
                        products[name].gifted += qty;
                    } else {
                        products[name].sold += qty;
                        products[name].revenue += qty * price;
                    }
                });
            });

            const rows = Object.entries(products)
                .map(([name, values]) => ({
                    name,
                    ...values
                }))
                .sort((a, b) =>
                    b.revenue - a.revenue ||
                    a.name.localeCompare(b.name)
                );

            if (!rows.length) {
                container.innerHTML =
                    '<div style="font-size:12px;color:var(--text-muted);text-align:center;padding:12px;">No product sales have been recorded yet.</div>';
                return;
            }

            const maxRevenue =
                Math.max(
                    ...rows.map(r => r.revenue),
                    1
                );

            container.innerHTML = rows.map(row => {

                const width =
                    row.revenue > 0
                        ? Math.max(
                            2,
                            (row.revenue / maxRevenue) * 100
                          )
                        : 0;

                return `
                    <div class="venue-report-row">
                        <div class="venue-report-heading">
                            <span class="venue-report-name">
                                ${escapeHtml(row.name)}
                            </span>

                            <span class="venue-report-revenue">
                                $${row.revenue.toFixed(2)}
                            </span>
                        </div>

                        <div class="venue-report-meta">
                            ${row.sold} sold · ${row.gifted} gifted
                        </div>

                        <div class="venue-report-track">
                            <div
                                class="venue-report-fill"
                                style="width:${width}%">
                            </div>
                        </div>

                    </div>
                `;
            }).join('');
        }

"""

html = html.replace(
    anchor,
    product_renderer + "\n" + anchor,
    1
)

# --------------------------------------------------
# Call renderProductReport() in renderStats()
# --------------------------------------------------

render_stats_line = """
            renderVenueReport();
"""

if render_stats_line not in html:
    fail("Could not locate renderVenueReport() call")

html = html.replace(
    render_stats_line,
    """
            renderVenueReport();
            renderProductReport();
""",
    1
)

# --------------------------------------------------
# Backup and write
# --------------------------------------------------

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

backup = ROOT / f"index-backup-{stamp}.html"

shutil.copy2(HTML, backup)

HTML.write_text(
    html,
    encoding="utf-8"
)

print("SUCCESS: Revenue by Product report added")
print("BACKUP:", backup.name)
print("")
print("Features:")
print("  ✓ Revenue by Product")
print("  ✓ Units Sold")
print("  ✓ Units Gifted")
print("  ✓ Revenue Bars")
print("  ✓ Highest Revenue First")