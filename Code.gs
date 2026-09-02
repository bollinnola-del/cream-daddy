/**
 * Cream Daddy Google Sheets API
 * Sheets created/used:
 *   Menu & Inventory: Product ID | Product Name | Price | Current Stock | Photo URL / Base64 | Updated At
 *   Sales Log: Timestamp | Venue | Business Date | Net Total | Units Sold | Units Gifted | Summary | Items JSON | Transaction ID
 *
 * Deploy as a Web app. For phones that are not signed into the script owner's Google account,
 * execute as the owner and grant access according to the deployment's intended audience.
 */
var MENU_SHEET = 'Menu & Inventory';
var SALES_SHEET = 'Sales Log';
var VENUES_SHEET = 'Venues';
// Cream Daddy Shared Venue Catalog V1

function doGet(e) {
  try {
    var action = (e && e.parameter && e.parameter.action) || '';
    if (action === 'authorize') {
      return output_(authorizeHelper_(e.parameter.accessCode || ''), e.parameter.callback || '');
    }
    if (action === 'pull_all' || action === 'pull_menu' || (e.parameter && e.parameter.callback)) {
      verifyAccessToken_(e.parameter.token || '');
      return output_(pullAll_(), e.parameter.callback || '');
    }
    return output_({status:'success', message:'Cream Daddy API is running.'}, '');
  } catch (err) {
    return output_({status:'error', code:'UNAUTHORIZED', message:String(err && err.message || err)}, callback_(e));
  }
}

function doPost(e) {
  try {
    var raw = e && e.postData ? e.postData.contents : '';
    var payload = raw ? JSON.parse(raw) : {};
    verifyAccessToken_(payload.token || '');
    delete payload.token;
    return output_(processWrite_(payload), '');
  } catch (err) {
    return output_({status:'error', code:'UNAUTHORIZED', message:String(err && err.message || err)}, '');
  }
}



// ---- 24-hour shared helper authorization ----
function authorizeHelper_(providedCode) {
  var secret = PropertiesService.getScriptProperties().getProperty('HELPER_ACCESS_CODE');
  if (!secret) throw new Error('HELPER_ACCESS_CODE is not configured.');
  if (!providedCode || String(providedCode) !== String(secret)) {
    throw new Error('Incorrect access code.');
  }
  var expiresAt = Date.now() + (24 * 60 * 60 * 1000);
  return {status:'success', token:createAccessToken_(expiresAt), expiresAt:expiresAt};
}

function createAccessToken_(expiresAt) {
  var secret = PropertiesService.getScriptProperties().getProperty('HELPER_ACCESS_CODE');
  var payload = String(expiresAt);
  var signature = Utilities.computeHmacSha256Signature(payload, secret);
  return payload + '.' + Utilities.base64EncodeWebSafe(signature).replace(/=+$/g, '');
}

function verifyAccessToken_(token) {
  var secret = PropertiesService.getScriptProperties().getProperty('HELPER_ACCESS_CODE');
  if (!secret) throw new Error('HELPER_ACCESS_CODE is not configured.');
  var parts = String(token || '').split('.');
  if (parts.length !== 2) throw new Error('Authorization required.');
  var expiresAt = Number(parts[0]);
  if (!isFinite(expiresAt) || Date.now() >= expiresAt) throw new Error('Authorization expired.');
  var expected = Utilities.base64EncodeWebSafe(
    Utilities.computeHmacSha256Signature(parts[0], secret)
  ).replace(/=+$/g, '');
  if (!constantTimeEquals_(parts[1], expected)) throw new Error('Invalid authorization.');
  return true;
}

function constantTimeEquals_(a, b) {
  a = String(a); b = String(b);
  if (a.length !== b.length) return false;
  var diff = 0;
  for (var i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function processWrite_(data) {
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var sheets = ensureSheets_();
    if (data.action === 'add_venue') {
      var addedVenue = addVenue_(sheets.venues, data.venue);
      return {status:'success', action:'add_venue', venue:addedVenue};
    }
    if (data.action === 'remove_venue') {
      var removedVenue = removeVenue_(sheets.venues, data.venue);
      return {status:'success', action:'remove_venue', venue:removedVenue};
    }
    if (data.action === 'update_menu' && Array.isArray(data.flavors)) {
      writeMenu_(sheets.menu, data.flavors);
      return {status:'success', action:'update_menu', count:data.flavors.length};
    }
    var txs = Array.isArray(data.transactions) ? data.transactions : [];
    if (txs.length) {
      var result = appendTransactions_(sheets.menu, sheets.sales, txs, data.venue, data.date);
      return {status:'success', action:'append_transactions', written:result.written, duplicates:result.duplicates};
    }
    return {status:'error', message:'No supported write action was supplied.'};
  } finally {
    lock.releaseLock();
  }
}

function pullAll_() {
  var sheets = ensureSheets_();
  var flavors = [];
  if (sheets.menu.getLastRow() > 1) {
    var rows = sheets.menu.getRange(2,1,sheets.menu.getLastRow()-1,6).getValues();
    rows.forEach(function(row, idx) {
      if (!row[1]) return;
      flavors.push({
        id: String(row[0] || ('flv_' + (idx + 1))),
        name: String(row[1]).trim(),
        price: number_(row[2]),
        startingStock: number_(row[3]),
        currentStock: number_(row[3]),
        photo: row[4] ? String(row[4]) : ''
      });
    });
  }

  var transactions = [];
  if (sheets.sales.getLastRow() > 1) {
    var salesRows = sheets.sales.getRange(2,1,sheets.sales.getLastRow()-1,9).getValues();
    salesRows.forEach(function(row, idx) {
      if (!row[0] && !row[8]) return;
      var items = parseItemsJson_(row[7]);
      if (!items.length) items = parseItemsFromSummary_(row[6]);
      transactions.push({
        id: String(row[8] || ('tx_sheet_' + (idx + 1))),
        timestamp: isoOrString_(row[0]),
        venue: String(row[1] || 'Daily Pop-Up'),
        date: dateString_(row[2]),
        totalPrice: number_(row[3]),
        totalUnitsSold: number_(row[4]),
        totalUnitsGiven: number_(row[5]),
        summary: String(row[6] || ''),
        items: items
      });
    });
  }
  transactions.reverse();
  var venues = readVenues_(sheets.venues);
  return {status:'success', serverTime:new Date().toISOString(), flavors:flavors, transactions:transactions, venues:venues};
}

function readVenues_(sheet) {
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

function writeMenu_(sheet, flavors) {
  var rows = flavors.map(function(f, idx) {
    return [
      String(f.id || ('flv_' + Utilities.getUuid())),
      String(f.name || '').trim(),
      number_(f.price),
      Math.max(0, Math.floor(number_(f.currentStock != null ? f.currentStock : f.startingStock))),
      String(f.photo || ''),
      new Date()
    ];
  }).filter(function(r){ return r[1]; });
  if (sheet.getLastRow() > 1) sheet.getRange(2,1,sheet.getLastRow()-1,6).clearContent();
  if (rows.length) sheet.getRange(2,1,rows.length,6).setValues(rows);
}

function appendTransactions_(menuSheet, salesSheet, txs, defaultVenue, defaultDate) {
  var existing = {};
  if (salesSheet.getLastRow() > 1) {
    salesSheet.getRange(2,9,salesSheet.getLastRow()-1,1).getDisplayValues().forEach(function(r){ if(r[0]) existing[r[0]] = true; });
  }
  var menuRows = menuSheet.getLastRow() > 1 ? menuSheet.getRange(2,1,menuSheet.getLastRow()-1,6).getValues() : [];
  var byId = {}, byName = {};
  menuRows.forEach(function(r, i){ byId[String(r[0])] = i; byName[String(r[1]).toLowerCase().trim()] = i; });
  var outputRows = [], written = 0, duplicates = 0;

  txs.forEach(function(tx) {
    var txId = String(tx.id || Utilities.getUuid());
    if (existing[txId]) { duplicates++; return; }
    var items = Array.isArray(tx.items) ? tx.items : [];
    var sold = 0, gifted = 0, total = 0;
    items.forEach(function(it) {
      var qty = Math.max(0, Math.floor(number_(it.qty)));
      if (!qty) return;
      var free = !!it.isComp;
      if (free) gifted += qty; else { sold += qty; total += qty * number_(it.price); }
      var menuIdx = byId[String(it.flavorId || '')];
      if (menuIdx == null) menuIdx = byName[String(it.name || '').toLowerCase().trim()];
      if (menuIdx == null) throw new Error('Unknown product: ' + String(it.name || it.flavorId || 'unnamed'));
      var remaining = Math.floor(number_(menuRows[menuIdx][3]));
      if (remaining < qty) throw new Error('Not enough stock for ' + menuRows[menuIdx][1] + '. Sheet has ' + remaining + '.');
      menuRows[menuIdx][3] = remaining - qty;
      menuRows[menuIdx][5] = new Date();
    });
    var summary = items.map(function(it){
      return Math.floor(number_(it.qty)) + 'x ' + String(it.name || '') + (it.isComp ? ' [FREE]' : ' [$' + number_(it.price).toFixed(2) + ']');
    }).join(', ');
    outputRows.push([
      new Date(), String(tx.venue || defaultVenue || 'Daily Pop-Up'), String(tx.date || defaultDate || ''),
      tx.totalPrice != null ? number_(tx.totalPrice) : total,
      tx.totalUnitsSold != null ? number_(tx.totalUnitsSold) : sold,
      tx.totalUnitsGiven != null ? number_(tx.totalUnitsGiven) : gifted,
      summary, JSON.stringify(items), txId
    ]);
    existing[txId] = true; written++;
  });

  if (menuRows.length) menuSheet.getRange(2,1,menuRows.length,6).setValues(menuRows);
  if (outputRows.length) salesSheet.getRange(salesSheet.getLastRow()+1,1,outputRows.length,9).setValues(outputRows);
  SpreadsheetApp.flush();
  return {written:written, duplicates:duplicates};
}

function ensureSheets_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var menu = ss.getSheetByName(MENU_SHEET) || ss.insertSheet(MENU_SHEET);
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
  return {menu:menu, sales:sales, venues:venues};
}

function output_(obj, callback) {
  if (callback) {
    var safe = String(callback).replace(/[^a-zA-Z0-9_$\.]/g,'');
    return ContentService.createTextOutput(safe + '(' + JSON.stringify(obj) + ');').setMimeType(ContentService.MimeType.JAVASCRIPT);
  }
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
function callback_(e){ return e && e.parameter ? e.parameter.callback || '' : ''; }
function number_(v){ var n = Number(v); return isFinite(n) ? n : 0; }
function isoOrString_(v){ return v instanceof Date ? v.toISOString() : String(v || ''); }
function dateString_(v){ return v instanceof Date ? Utilities.formatDate(v, Session.getScriptTimeZone(), 'yyyy-MM-dd') : String(v || ''); }
function parseItemsJson_(value){ try { var x = JSON.parse(String(value || '[]')); return Array.isArray(x) ? x : []; } catch(e) { return []; } }
function parseItemsFromSummary_(summary) {
  var items = [];
  String(summary || '').split(/[,;]/).forEach(function(part) {
    var m = part.trim().match(/^(\d+)x\s+(.+?)\s+\[(FREE|\$\d+(?:\.\d+)?)\]$/i);
    if (!m) return;
    var free = m[3].toUpperCase() === 'FREE';
    items.push({qty:Number(m[1]), name:m[2].trim(), isComp:free, price:free ? 0 : number_(m[3].replace('$',''))});
  });
  return items;
}
