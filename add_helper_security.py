#!/usr/bin/env python3
"""Patch Cream Daddy index.html and Code.gs with 24-hour helper access."""
from pathlib import Path
from datetime import datetime
import re, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "index.html"
GS = ROOT / "Code.gs"


def fail(msg):
    print("ERROR:", msg)
    print("No changes were saved.")
    sys.exit(1)


def replace_braced_function(source, name, replacement):
    m = re.search(rf"function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", source)
    if not m:
        fail(f"Could not find function {name}().")
    start = m.start()
    brace = source.find("{", start)
    depth = 0; quote = None; esc = False; line = False; block = False; i = brace
    while i < len(source):
        c = source[i]; n = source[i+1] if i+1 < len(source) else ""
        if line:
            if c == "\n": line = False
        elif block:
            if c == "*" and n == "/": block = False; i += 1
        elif quote:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == quote: quote = None
        else:
            if c == "/" and n == "/": line = True; i += 1
            elif c == "/" and n == "*": block = True; i += 1
            elif c in "'\"`": quote = c
            elif c == "{": depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return source[:start] + replacement + source[i+1:]
        i += 1
    fail(f"Could not match braces for {name}().")


if not HTML.exists() or not GS.exists():
    fail("Put this script in the same folder as index.html and Code.gs.")

html0 = HTML.read_text(encoding="utf-8")
gs0 = GS.read_text(encoding="utf-8")
html = html0; gs = gs0
if "cream_daddy_auth_token" in html or "authorizeHelper_" in gs:
    fail("Security code appears to be already installed.")

# ---------- Apps Script backend ----------
do_get = '''function doGet(e) {
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
}'''

do_post = '''function doPost(e) {
  try {
    var raw = e && e.postData ? e.postData.contents : '';
    var payload = raw ? JSON.parse(raw) : {};
    verifyAccessToken_(payload.token || '');
    delete payload.token;
    return output_(processWrite_(payload), '');
  } catch (err) {
    return output_({status:'error', code:'UNAUTHORIZED', message:String(err && err.message || err)}, '');
  }
}'''

gs = replace_braced_function(gs, "doGet", do_get)
gs = replace_braced_function(gs, "doPost", do_post)

security_helpers = r'''

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
'''
# Insert helpers before processWrite_ to keep the file organized.
anchor = "function processWrite_(data) {"
if gs.count(anchor) != 1: fail("Could not safely locate processWrite_() in Code.gs.")
gs = gs.replace(anchor, security_helpers + "\n" + anchor, 1)

# ---------- Frontend lock screen ----------
css_anchor = "    </style>"
lock_css = '''
        #access-lock {
            position: fixed; inset: 0; z-index: 5000; display: none;
            align-items: center; justify-content: center; padding: 20px;
            background: var(--brand-black);
        }
        #access-lock.active { display: flex; }
        .access-card { width: min(420px, 100%); background: #fff; border-radius: 16px; padding: 22px; text-align: center; }
        .access-card h1 { font-size: 22px; margin-bottom: 8px; }
        .access-card p { color: var(--text-muted); font-size: 13px; margin-bottom: 14px; }
        #helper-access-code { width: 100%; font-size: 18px; text-align: center; margin-bottom: 10px; }
        #access-error { min-height: 20px; color: var(--danger); font-size: 13px; margin-top: 8px; }
'''
if html.count(css_anchor) != 1: fail("Could not locate </style> in index.html.")
html = html.replace(css_anchor, lock_css + css_anchor, 1)

body_anchor = "<body>"
lock_html = '''<body>
    <div id="access-lock" class="active" aria-modal="true" role="dialog">
        <div class="access-card">
            <div style="font-size:42px;margin-bottom:8px;">🍦</div>
            <h1>Cream Daddy Team Access</h1>
            <p>Enter the helper access code. This device stays unlocked for 24 hours.</p>
            <input id="helper-access-code" class="form-input" type="password" autocomplete="current-password" placeholder="Access code">
            <button id="unlock-register" class="btn-primary" style="width:100%;padding:12px;" onclick="authorizeHelper()">Unlock Register</button>
            <div id="access-error" role="alert"></div>
        </div>
    </div>'''
if html.count(body_anchor) != 1: fail("Could not locate <body> in index.html.")
html = html.replace(body_anchor, lock_html, 1)

# Add auth helpers immediately before loadSavedState.
js_anchor = "        function loadSavedState() {"
auth_js = r'''        const AUTH_TOKEN_KEY = 'cream_daddy_auth_token';
        const AUTH_EXPIRY_KEY = 'cream_daddy_auth_expiry';

        function getAccessToken() {
            const token = localStorage.getItem(AUTH_TOKEN_KEY) || '';
            const expiry = Number(localStorage.getItem(AUTH_EXPIRY_KEY) || 0);
            if (!token || Date.now() >= expiry) {
                localStorage.removeItem(AUTH_TOKEN_KEY);
                localStorage.removeItem(AUTH_EXPIRY_KEY);
                return '';
            }
            return token;
        }

        function setLocked(isLocked, message = '') {
            const lock = document.getElementById('access-lock');
            const error = document.getElementById('access-error');
            if (lock) lock.classList.toggle('active', isLocked);
            if (error) error.textContent = message;
            document.body.style.overflow = isLocked ? 'hidden' : '';
        }

        function clearAuthorization(message = 'Please enter the helper access code.') {
            localStorage.removeItem(AUTH_TOKEN_KEY);
            localStorage.removeItem(AUTH_EXPIRY_KEY);
            setLocked(true, message);
        }

        window.handleHelperAuthorization = function(data) {
            if (data && data.status === 'success' && data.token && data.expiresAt) {
                localStorage.setItem(AUTH_TOKEN_KEY, data.token);
                localStorage.setItem(AUTH_EXPIRY_KEY, String(data.expiresAt));
                document.getElementById('helper-access-code').value = '';
                setLocked(false);
                haptic('success');
                fetchFromGoogleSheet(false);
            } else {
                clearAuthorization((data && data.message) || 'Incorrect access code.');
                haptic('error');
            }
        };

        window.authorizeHelper = function() {
            const input = document.getElementById('helper-access-code');
            const code = (input && input.value || '').trim();
            if (!code) {
                setLocked(true, 'Enter the helper access code.');
                return;
            }
            document.getElementById('access-error').textContent = 'Checking access…';
            const old = document.getElementById('helper-auth-script');
            if (old) old.remove();
            const script = document.createElement('script');
            script.id = 'helper-auth-script';
            script.src = STATE.scriptUrl + '?action=authorize&accessCode=' + encodeURIComponent(code)
                + '&callback=handleHelperAuthorization&t=' + Date.now();
            script.onerror = () => setLocked(true, 'Could not contact the server. Check connectivity and try again.');
            document.body.appendChild(script);
        };

'''
if html.count(js_anchor) != 1: fail("Could not locate loadSavedState() in index.html.")
html = html.replace(js_anchor, auth_js + js_anchor, 1)

# Protect pull: return when no token and add token query parameter.
old_fetch_start = """        function fetchFromGoogleSheet(isManual = false) {
            if (STATE.isSyncing) return;"""
new_fetch_start = """        function fetchFromGoogleSheet(isManual = false) {
            const token = getAccessToken();
            if (!token) {
                setLocked(true);
                return;
            }
            if (STATE.isSyncing) return;"""
if html.count(old_fetch_start) != 1: fail("Could not locate fetchFromGoogleSheet() start.")
html = html.replace(old_fetch_start, new_fetch_start, 1)
old_src = "script.src = STATE.scriptUrl + '?action=pull_all&callback=handleGoogleSheetSyncResponse&t=' + Date.now();"
new_src = "script.src = STATE.scriptUrl + '?action=pull_all&token=' + encodeURIComponent(token) + '&callback=handleGoogleSheetSyncResponse&t=' + Date.now();"
if html.count(old_src) != 1: fail("Could not locate the JSONP pull URL.")
html = html.replace(old_src, new_src, 1)

# Handle unauthorized pull responses.
response_anchor = "        window.handleGoogleSheetSyncResponse = function (data) {\n            if (data && data.status === 'success') {"
response_new = """        window.handleGoogleSheetSyncResponse = function (data) {
            if (data && data.status === 'error' && data.code === 'UNAUTHORIZED') {
                STATE.isSyncing = false;
                clearAuthorization(data.message || 'Authorization expired.');
                return;
            }
            if (data && data.status === 'success') {"""
if html.count(response_anchor) != 1: fail("Could not locate sync response handler.")
html = html.replace(response_anchor, response_new, 1)

# Protect writes by adding token to a copied payload.
send_anchor = """        async function sendSheetPayload(payloadObj) {
            const body = JSON.stringify(payloadObj);"""
send_new = """        async function sendSheetPayload(payloadObj) {
            const token = getAccessToken();
            if (!token) {
                clearAuthorization('Authorization required before saving.');
                return false;
            }
            const securedPayload = { ...payloadObj, token };
            const body = JSON.stringify(securedPayload);"""
if html.count(send_anchor) != 1: fail("Could not locate sendSheetPayload().")
html = html.replace(send_anchor, send_new, 1)

# Startup: only sync after authorization.
startup = """            // Automatically fetch live menu & sales log via JSONP on launch
            fetchFromGoogleSheet(false);
            flushPendingWrites();"""
startup_new = """            // Only contact the Sheet after this device has a valid 24-hour authorization.
            if (getAccessToken()) {
                setLocked(false);
                fetchFromGoogleSheet(false);
                flushPendingWrites();
            } else {
                setLocked(true);
            }"""
if html.count(startup) != 1: fail("Could not locate startup sync block.")
html = html.replace(startup, startup_new, 1)

# Enter key submits access code.
dom_anchor = "        document.addEventListener('click', (e) => {"
enter_js = """        document.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && document.getElementById('access-lock')?.classList.contains('active')) {
                authorizeHelper();
            }
        });
"""
if html.count(dom_anchor) != 1: fail("Could not locate document click handler.")
html = html.replace(dom_anchor, enter_js + dom_anchor, 1)

# Backups, write, syntax checks.
stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
html_bak = ROOT / f'index-backup-{stamp}.html'
gs_bak = ROOT / f'Code-backup-{stamp}.gs'
shutil.copy2(HTML, html_bak); shutil.copy2(GS, gs_bak)
HTML.write_text(html, encoding='utf-8'); GS.write_text(gs, encoding='utf-8')

node = shutil.which('node')
if node:
    scripts = re.findall(r'<script(?:\s[^>]*)?>([\s\S]*?)</script>', html, flags=re.I)
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
        f.write(scripts[-1]); tmp = f.name
    result = subprocess.run([node, '--check', tmp], capture_output=True, text=True)
    Path(tmp).unlink(missing_ok=True)
    if result.returncode:
        shutil.copy2(html_bak, HTML); shutil.copy2(gs_bak, GS)
        print(result.stderr); fail('Frontend syntax check failed. Both backups were restored.')

print('SUCCESS: 24-hour helper security installed in index.html and Code.gs')
print('BACKUPS:', html_bak.name, 'and', gs_bak.name)
print('NEXT: Paste the updated Code.gs into Apps Script, save, and deploy a new version.')
