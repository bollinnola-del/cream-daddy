#!/usr/bin/env python3
"""Patch Code.gs to add a shared Google-Sheet-backed Venue catalog."""
from pathlib import Path
from datetime import datetime
import re, shutil, sys

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "Code.gs"
MARKER = "// Cream Daddy Shared Venue Catalog V1"

def fail(msg):
    print("ERROR:", msg)
    print("No changes were saved.")
    sys.exit(1)

if not TARGET.exists():
    fail("Code.gs was not found. Export/copy the current Apps Script code into Code.gs beside this patch.")

original = TARGET.read_text(encoding="utf-8")
text = original
if MARKER in text:
    print("No update needed. Shared Venue Catalog V1 is already installed in Code.gs.")
    sys.exit(0)

for required in [
    "var MENU_SHEET = 'Menu & Inventory';",
    "var SALES_SHEET = 'Sales Log';",
    "function processWrite_(data)",
    "function pullAll_()",
    "function ensureSheets_()",
]:
    if required not in text:
        fail(f"Expected backend code is missing: {required}")

# 1. Add shared sheet name.
anchor = "var SALES_SHEET = 'Sales Log';"
text = text.replace(anchor, anchor + "\nvar VENUES_SHEET = 'Venues';\n" + MARKER, 1)

# 2. Add write actions before update_menu.
write_anchor = """    var sheets = ensureSheets_();
    if (data.action === 'update_menu' && Array.isArray(data.flavors)) {"""
write_replacement = """    var sheets = ensureSheets_();
    if (data.action === 'add_venue') {
      var addedVenue = addVenue_(sheets.venues, data.venue);
      return {status:'success', action:'add_venue', venue:addedVenue};
    }
    if (data.action === 'remove_venue') {
      var removedVenue = removeVenue_(sheets.venues, data.venue);
      return {status:'success', action:'remove_venue', venue:removedVenue};
    }
    if (data.action === 'update_menu' && Array.isArray(data.flavors)) {"""
if text.count(write_anchor) != 1:
    fail("Could not uniquely locate processWrite_ action routing.")
text = text.replace(write_anchor, write_replacement, 1)

# 3. Pull the shared venue catalog and return it.
pull_return = "return {status:'success', serverTime:new Date().toISOString(), flavors:flavors, transactions:transactions};"
new_pull_return = """var venues = readVenues_(sheets.venues);
  return {status:'success', serverTime:new Date().toISOString(), flavors:flavors, transactions:transactions, venues:venues};"""
if text.count(pull_return) != 1:
    fail("Could not uniquely locate pullAll_ return object.")
text = text.replace(pull_return, new_pull_return, 1)

# 4. Add helpers immediately before writeMenu_.
helper_anchor = "function writeMenu_(sheet, flavors) {"
helpers = r'''function readVenues_(sheet) {
  if (sheet.getLastRow() <= 1) return [];
  var values = sheet.getRange(2, 1, sheet.getLastRow() - 1, 1).getDisplayValues();
  var venues = [];
  values.forEach(function(row) {
    var venue = String(row[0] || '').trim();
    if (venue && !venues.some(function(item){ return item.toLowerCase() === venue.toLowerCase(); })) {
      venues.push(venue);
    }
  });
  return venues.sort(function(a, b){ return a.localeCompare(b); });
}

function addVenue_(sheet, value) {
  var venue = String(value || '').trim();
  if (!venue) throw new Error('Venue name is required.');
  var venues = readVenues_(sheet);
  var existing = venues.filter(function(item){ return item.toLowerCase() === venue.toLowerCase(); })[0];
  if (existing) return existing;
  sheet.appendRow([venue, new Date()]);
  SpreadsheetApp.flush();
  return venue;
}

function removeVenue_(sheet, value) {
  var venue = String(value || '').trim();
  if (!venue) throw new Error('Venue name is required.');
  if (sheet.getLastRow() <= 1) return venue;
  var values = sheet.getRange(2, 1, sheet.getLastRow() - 1, 1).getDisplayValues();
  for (var i = values.length - 1; i >= 0; i--) {
    if (String(values[i][0] || '').trim().toLowerCase() === venue.toLowerCase()) {
      sheet.deleteRow(i + 2);
    }
  }
  SpreadsheetApp.flush();
  return venue;
}

'''
if text.count(helper_anchor) != 1:
    fail("Could not uniquely locate writeMenu_ for venue helper insertion.")
text = text.replace(helper_anchor, helpers + helper_anchor, 1)

# 5. Upgrade ensureSheets_.
old_ensure = """  var menu = ss.getSheetByName(MENU_SHEET) || ss.insertSheet(MENU_SHEET);
  var sales = ss.getSheetByName(SALES_SHEET) || ss.insertSheet(SALES_SHEET);
  if (menu.getLastRow() === 0) menu.appendRow(['Product ID','Product Name','Price','Current Stock','Photo URL / Base64','Updated At']);
  if (sales.getLastRow() === 0) sales.appendRow(['Timestamp','Venue','Business Date','Net Total','Units Sold','Units Gifted','Summary','Items JSON','Transaction ID']);
  return {menu:menu, sales:sales};"""
new_ensure = """  var menu = ss.getSheetByName(MENU_SHEET) || ss.insertSheet(MENU_SHEET);
  var sales = ss.getSheetByName(SALES_SHEET) || ss.insertSheet(SALES_SHEET);
  var venues = ss.getSheetByName(VENUES_SHEET) || ss.insertSheet(VENUES_SHEET);
  if (menu.getLastRow() === 0) menu.appendRow(['Product ID','Product Name','Price','Current Stock','Photo URL / Base64','Updated At']);
  if (sales.getLastRow() === 0) sales.appendRow(['Timestamp','Venue','Business Date','Net Total','Units Sold','Units Gifted','Summary','Items JSON','Transaction ID']);
  if (venues.getLastRow() === 0) venues.appendRow(['Venue','Updated At']);
  if (venues.getLastRow() === 1) {
    var seed = {};
    if (sales.getLastRow() > 1) {
      sales.getRange(2, 2, sales.getLastRow() - 1, 1).getDisplayValues().forEach(function(row) {
        var venue = String(row[0] || '').trim();
        if (venue) seed[venue.toLowerCase()] = venue;
      });
    }
    if (!Object.keys(seed).length) seed['daily pop-up'] = 'Daily Pop-Up';
    var seedRows = Object.keys(seed).sort().map(function(key){ return [seed[key], new Date()]; });
    if (seedRows.length) venues.getRange(2, 1, seedRows.length, 2).setValues(seedRows);
  }
  return {menu:menu, sales:sales, venues:venues};"""
if text.count(old_ensure) != 1:
    fail("Could not uniquely locate ensureSheets_ body.")
text = text.replace(old_ensure, new_ensure, 1)

for required in ["VENUES_SHEET", "action === 'add_venue'", "action === 'remove_venue'", "venues:venues", "function addVenue_", "function removeVenue_"]:
    if required not in text:
        fail(f"Validation failed for: {required}")

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = ROOT / f"Code-backup-{stamp}.gs"
shutil.copy2(TARGET, backup)
TARGET.write_text(text, encoding="utf-8")

print("SUCCESS: Code.gs shared venue catalog installed.")
print("BACKUP:", backup.name)
print("BACKEND CHANGES:")
print("  - Creates a Venues sheet with Venue and Updated At columns")
print("  - Seeds it from existing Sales Log venues when initially empty")
print("  - pull_all now returns venues")
print("  - add_venue and remove_venue actions update only the Venues sheet")
print("  - Historical Sales Log rows are never modified")
