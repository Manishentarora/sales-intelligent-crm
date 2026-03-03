"""
SALES INTELLIGENCE PRO — LICENSE SYSTEM
========================================
Two uses:

  1. ADMIN — generate / manage licenses from terminal:
       python license_system.py generate --email customer@co.com --name "Acme" --days 365
       python license_system.py list
       python license_system.py revoke   --key SALE-2026-PRO1-XXXX-XXXX
       python license_system.py reset-machine --key SALE-2026-PRO1-XXXX-XXXX
       python license_system.py alerts

  2. APP — enforce licensing inside Streamlit (called from main app):
       LicenseGuard.enforce()
"""

import os, sys, json, hmac, hashlib, secrets, string, smtplib, sqlite3, platform, uuid, argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from cryptography.fernet import Fernet
    CRYPTO_OK = True
except ImportError:
    CRYPTO_OK = False

# ══════════════════════════════════════════════════════
#  ▼▼▼  EDIT THESE BEFORE DEPLOYING  ▼▼▼
# ══════════════════════════════════════════════════════
PRODUCT_NAME = "Sales Intelligence Pro"
PRODUCT_CODE = "SALE"
ADMIN_EMAIL  = "your@email.com"           # all alerts arrive here
ADMIN_SECRET = "replace-with-long-random-secret-string-min-32-chars"

SMTP_HOST    = "smtp.gmail.com"
SMTP_PORT    = 587
SMTP_USER    = "your@gmail.com"           # Gmail account
SMTP_PASS    = "xxxx xxxx xxxx xxxx"      # Gmail App Password (not main password)
# ══════════════════════════════════════════════════════

DB_PATH      = Path(__file__).parent / "licenses.db"
CACHE_FILE   = Path.home() / f".{PRODUCT_CODE.lower()}_lic"
OFFLINE_DAYS = 7

# ─────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _init_db():
    conn = _db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS licenses (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            key          TEXT    UNIQUE NOT NULL,
            email        TEXT    NOT NULL,
            name         TEXT    DEFAULT '',
            plan         TEXT    DEFAULT 'PRO',
            status       TEXT    DEFAULT 'ACTIVE',
            machine_hash TEXT    DEFAULT '',
            offline_days INTEGER DEFAULT 7,
            created_at   TEXT    DEFAULT (datetime('now')),
            expires_at   TEXT,
            last_seen    TEXT,
            activations  INTEGER DEFAULT 0,
            notes        TEXT    DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            type       TEXT,
            key        TEXT    DEFAULT '',
            machine_id TEXT    DEFAULT '',
            detail     TEXT,
            notified   INTEGER DEFAULT 0,
            ts         TEXT    DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()

# ─────────────────────────────────────────────────────
# EMAIL
# ─────────────────────────────────────────────────────
def _send_email(to: str, subject: str, body: str):
    if SMTP_USER == "your@gmail.com":
        print(f"[EMAIL not configured]\nTo: {to}\nSubject: {subject}\n{body}")
        return
    try:
        msg = MIMEMultipart()
        msg["From"]    = f"{PRODUCT_NAME} <{SMTP_USER}>"
        msg["To"]      = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        s = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)
        s.quit()
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")

def _alert_admin(alert_type: str, detail: str, key: str = "", machine_id: str = ""):
    _init_db()
    conn = _db()
    conn.execute(
        "INSERT INTO alerts (type, key, machine_id, detail) VALUES (?,?,?,?)",
        (alert_type, key, machine_id[:32] if machine_id else "", detail)
    )
    conn.commit()
    conn.close()

    mid_display = (machine_id[:24] + "...") if len(machine_id) > 24 else machine_id
    body = f"""UNAUTHORIZED USE DETECTED — {PRODUCT_NAME}

Time:        {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC
Alert Type:  {alert_type}
License Key: {key or 'NONE'}
Machine:     {mid_display or 'Unknown'}
Detail:      {detail}

Action: App hard-crashed. Customer sees error screen.

Review:
  python license_system.py list
  python license_system.py alerts

— {PRODUCT_NAME} License System
"""
    _send_email(ADMIN_EMAIL, f"🚨 LICENSE ALERT: {alert_type} — {PRODUCT_NAME}", body)

# ─────────────────────────────────────────────────────
# KEY GENERATION & VERIFICATION
# ─────────────────────────────────────────────────────
def _generate_key(plan: str = "PRO") -> str:
    """SALE-YYYY-PLAN-RAND-HMAC — only keys signed with ADMIN_SECRET are valid"""
    chars   = string.ascii_uppercase + string.digits
    year    = str(datetime.now(timezone.utc).year)
    pcodes  = {"PRO": "PRO1", "TRIAL": "TRIA", "ENTERPRISE": "ENT1"}
    p       = pcodes.get(plan.upper(), "PRO1")
    rand    = "".join(secrets.choice(chars) for _ in range(4))
    raw     = f"{PRODUCT_CODE}{year}{p}{rand}"
    sig     = hmac.new(ADMIN_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()[:4].upper()
    return f"{PRODUCT_CODE}-{year}-{p}-{rand}-{sig}"

def _verify_key_format(key: str) -> bool:
    """Reject any key not signed by this system"""
    try:
        parts = key.upper().strip().split("-")
        if len(parts) != 5:
            return False
        prod, year, plan, rand, sig = parts
        raw      = f"{prod}{year}{plan}{rand}"
        expected = hmac.new(ADMIN_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()[:4].upper()
        return hmac.compare_digest(expected, sig)
    except:
        return False

# ─────────────────────────────────────────────────────
# MACHINE ID
# ─────────────────────────────────────────────────────
def _machine_id() -> str:
    try:
        raw = f"{uuid.getnode()}:{platform.node()}:{platform.system()}{platform.release()}:{PRODUCT_CODE}"
        return hashlib.sha256(raw.encode()).hexdigest()
    except:
        return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()

# ─────────────────────────────────────────────────────
# ENCRYPTED OFFLINE CACHE
# ─────────────────────────────────────────────────────
def _cache_enc_key() -> bytes:
    import base64
    raw = f"{_machine_id()}:{ADMIN_SECRET}"
    key = hashlib.sha256(raw.encode()).digest()
    return base64.urlsafe_b64encode(key)

def _save_cache(data: dict):
    try:
        payload = json.dumps(data).encode()
        if CRYPTO_OK:
            enc = Fernet(_cache_enc_key()).encrypt(payload)
        else:
            import base64
            enc = base64.b64encode(payload)
        CACHE_FILE.write_bytes(enc)
    except:
        pass

def _load_cache() -> dict | None:
    try:
        if not CACHE_FILE.exists():
            return None
        enc = CACHE_FILE.read_bytes()
        if CRYPTO_OK:
            payload = Fernet(_cache_enc_key()).decrypt(enc)
        else:
            import base64
            payload = base64.b64decode(enc)
        data = json.loads(payload.decode())
        if data.get("machine_id") != _machine_id():
            return None
        return data
    except:
        return None

def _clear_cache():
    try:
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
    except:
        pass

# ─────────────────────────────────────────────────────
# CORE VALIDATION
# ─────────────────────────────────────────────────────
def _validate(key: str, machine: str) -> dict:
    _init_db()

    if not _verify_key_format(key):
        return {"ok": False, "reason": "FORGED_KEY",
                "msg": "Invalid license key. This attempt has been reported."}

    conn = _db()
    row  = conn.execute("SELECT * FROM licenses WHERE key = ?", (key,)).fetchone()
    conn.close()

    if not row:
        return {"ok": False, "reason": "NOT_FOUND",
                "msg": "License key not found. Contact support."}

    lic = dict(row)

    if lic["status"] == "REVOKED":
        return {"ok": False, "reason": "REVOKED",
                "msg": "This license has been revoked. Contact support."}

    if lic["status"] == "SUSPENDED":
        return {"ok": False, "reason": "SUSPENDED",
                "msg": "License suspended. Contact support."}

    if lic["expires_at"]:
        if datetime.fromisoformat(lic["expires_at"]) < datetime.now(timezone.utc).replace(tzinfo=None):
            conn = _db()
            conn.execute("UPDATE licenses SET status='EXPIRED' WHERE key=?", (key,))
            conn.commit()
            conn.close()
            return {"ok": False, "reason": "EXPIRED",
                    "msg": f"License expired on {lic['expires_at'][:10]}. Contact support to renew."}

    machine_hash   = hashlib.sha256(machine.encode()).hexdigest()[:32]
    stored_machine = lic.get("machine_hash", "")

    if stored_machine == "":
        conn = _db()
        conn.execute(
            "UPDATE licenses SET machine_hash=?, activations=activations+1, last_seen=? WHERE key=?",
            (machine_hash, datetime.now(timezone.utc).replace(tzinfo=None).isoformat(), key)
        )
        conn.commit()
        conn.close()
    elif stored_machine != machine_hash:
        return {"ok": False, "reason": "WRONG_MACHINE",
                "msg": "License is locked to a different computer. Contact support to transfer."}
    else:
        conn = _db()
        conn.execute("UPDATE licenses SET last_seen=? WHERE key=?",
                     (datetime.now(timezone.utc).replace(tzinfo=None).isoformat(), key))
        conn.commit()
        conn.close()

    return {
        "ok":           True,
        "plan":         lic["plan"],
        "name":         lic["name"],
        "email":        lic["email"],
        "expires_at":   lic["expires_at"],
        "offline_days": lic["offline_days"]
    }

# ─────────────────────────────────────────────────────
# KEY FILE (persists activated key across runs)
# ─────────────────────────────────────────────────────
_KEY_FILE = Path(__file__).parent / ".lic_key"

def _get_stored_key() -> str:
    try:
        return _KEY_FILE.read_text().strip().upper() if _KEY_FILE.exists() else ""
    except:
        return ""

def _save_key(key: str):
    try:
        _KEY_FILE.write_text(key)
    except:
        pass

# ─────────────────────────────────────────────────────
# LICENSE MANAGER  (admin operations)
# ─────────────────────────────────────────────────────
class LicenseManager:

    @staticmethod
    def create(email: str, name: str = "", plan: str = "PRO",
               days: int = 365, notes: str = "", send_email: bool = True) -> str:
        _init_db()
        key        = _generate_key(plan)
        now        = datetime.now(timezone.utc).replace(tzinfo=None)
        expires_at = (now + timedelta(days=days)).isoformat() if days else None
        offline    = {"PRO": 7, "TRIAL": 3, "ENTERPRISE": 30}.get(plan.upper(), 7)

        conn = _db()
        conn.execute(
            "INSERT INTO licenses (key, email, name, plan, expires_at, offline_days, notes) VALUES (?,?,?,?,?,?,?)",
            (key, email.lower().strip(), name, plan.upper(), expires_at, offline, notes)
        )
        conn.commit()
        conn.close()

        if send_email:
            expiry_str = expires_at[:10] if expires_at else "Lifetime"
            body = f"""Dear {name or 'Customer'},

Your {PRODUCT_NAME} license is ready.

  LICENSE KEY:  {key}

  Plan:         {plan.upper()}
  Valid Until:  {expiry_str}
  Device Limit: 1 computer

HOW TO ACTIVATE:
  1. Open {PRODUCT_NAME}
  2. Enter the key above when prompted
  3. Click Activate

IMPORTANT: This key is locked to one computer on first use.
To transfer to a new PC, reply to this email.

— {PRODUCT_NAME} Team
"""
            _send_email(email, f"Your {PRODUCT_NAME} License Key", body)

        return key

    @staticmethod
    def revoke(key: str):
        _init_db()
        conn = _db()
        conn.execute("UPDATE licenses SET status='REVOKED' WHERE key=?", (key.upper(),))
        conn.commit()
        conn.close()

    @staticmethod
    def reset_machine(key: str):
        _init_db()
        conn = _db()
        conn.execute("UPDATE licenses SET machine_hash='' WHERE key=?", (key.upper(),))
        conn.commit()
        conn.close()

    @staticmethod
    def list_all() -> list:
        _init_db()
        conn = _db()
        rows = conn.execute("SELECT * FROM licenses ORDER BY created_at DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def list_alerts() -> list:
        _init_db()
        conn = _db()
        rows = conn.execute("SELECT * FROM alerts ORDER BY ts DESC LIMIT 200").fetchall()
        conn.close()
        return [dict(r) for r in rows]

# ─────────────────────────────────────────────────────
# LICENSE GUARD  (Streamlit enforcement)
# ─────────────────────────────────────────────────────
class LicenseGuard:
    """
    Called once at app start. Handles all license states:
      valid         → green badge in sidebar, app runs
      no key        → activation screen, app blocked
      invalid key   → hard crash + admin alert
      offline       → grace period from encrypted cache
      grace expired → hard crash + admin alert
    """

    @staticmethod
    def enforce():
        import streamlit as st

        # Already validated this session
        if st.session_state.get("_lic_ok"):
            LicenseGuard._sidebar_badge()
            return

        key = _get_stored_key()

        if not key:
            LicenseGuard._activation_screen()
            st.stop()
            return

        machine = _machine_id()
        result  = _validate(key, machine)

        if result["ok"]:
            cache_data = {**result, "key": key, "machine_id": machine,
                          "last_validated": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()}
            _save_cache(cache_data)
            LicenseGuard._set_session(result, key, offline=False)
            LicenseGuard._sidebar_badge()
            return

        # Offline fallback
        if result["reason"] in ("DB_UNREACHABLE", "ERROR"):
            cached = _load_cache()
            if cached and cached.get("key") == key:
                last         = datetime.fromisoformat(cached.get("last_validated", "2000-01-01"))
                days_offline = (datetime.now(timezone.utc).replace(tzinfo=None) - last).days
                allowed      = cached.get("offline_days", OFFLINE_DAYS)
                if days_offline <= allowed:
                    LicenseGuard._set_session(cached, key, offline=True,
                                              days_left=allowed - days_offline)
                    LicenseGuard._sidebar_badge()
                    return
                else:
                    LicenseGuard._crash(st, key, machine, "OFFLINE_GRACE_EXPIRED",
                                        f"Offline limit of {allowed} days exceeded. Connect to internet.")
                    return

        # Definitive failure — crash + alert
        LicenseGuard._crash(st, key, machine, result["reason"], result["msg"])

    # ── internal helpers ──────────────────────────────

    @staticmethod
    def _crash(st, key, machine, reason, msg):
        _clear_cache()
        _alert_admin(reason, msg, key=key, machine_id=machine)

        st.markdown("""
        <style>
        [data-testid="stSidebar"]{display:none}
        .main .block-container{max-width:620px;margin:auto;padding-top:5rem}
        </style>""", unsafe_allow_html=True)

        st.markdown("## 🚫 License Error")
        st.error(f"**{msg}**")
        st.markdown(f"""
---
**Reason:** `{reason}`

**What to do:**
- Enter a valid license key below
- Contact support: **{ADMIN_EMAIL}**

*This attempt has been logged and reported to the administrator.*
""")
        new_key = st.text_input("Enter valid license key:", placeholder="SALE-YYYY-PLAN-XXXX-XXXX")
        if st.button("Retry", type="primary"):
            if new_key.strip():
                _save_key(new_key.strip().upper())
                st.rerun()
            else:
                st.warning("Please enter a license key.")
        st.stop()

    @staticmethod
    def _activation_screen():
        import streamlit as st
        st.markdown("""
        <style>
        [data-testid="stSidebar"]{display:none}
        .main .block-container{max-width:480px;margin:auto;padding-top:7rem}
        </style>""", unsafe_allow_html=True)

        st.markdown(f"## 🔑 {PRODUCT_NAME}")
        st.markdown("Enter your license key to activate.")
        st.markdown("---")

        key = st.text_input("License Key", placeholder="SALE-YYYY-PLAN-XXXX-XXXX",
                            label_visibility="collapsed")

        if st.button("Activate", type="primary", use_container_width=True):
            clean = key.strip().upper()
            if not clean:
                st.warning("Please enter your license key.")
                return
            machine = _machine_id()
            result  = _validate(clean, machine)
            if result["ok"]:
                _save_key(clean)
                cache_data = {**result, "key": clean, "machine_id": machine,
                              "last_validated": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()}
                _save_cache(cache_data)
                st.success("✅ Activated! Loading...")
                st.rerun()
            else:
                _alert_admin(f"FAILED_ACTIVATION:{result['reason']}", result["msg"],
                             key=clean, machine_id=machine)
                st.error(f"❌ {result['msg']}")
                st.caption("This attempt has been logged.")

        st.markdown("---")
        st.caption(f"Need a license? Contact: {ADMIN_EMAIL}")

    @staticmethod
    def _sidebar_badge():
        import streamlit as st
        plan    = st.session_state.get("_lic_plan", "")
        name    = st.session_state.get("_lic_name", "")
        offline = st.session_state.get("_lic_offline", False)
        days    = st.session_state.get("_lic_days_left", 0)
        with st.sidebar:
            st.markdown("---")
            if offline:
                st.warning(f"📶 Offline Mode — {days}d remaining")
            else:
                st.success(f"✅ {plan} License")
            if name:
                st.caption(f"👤 {name}")

    @staticmethod
    def _set_session(data, key, offline, days_left=0):
        import streamlit as st
        st.session_state.update({
            "_lic_ok":        True,
            "_lic_key":       key,
            "_lic_plan":      data.get("plan", ""),
            "_lic_name":      data.get("name", ""),
            "_lic_offline":   offline,
            "_lic_days_left": days_left
        })

# ─────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────
def _cli():
    ap  = argparse.ArgumentParser(description=f"{PRODUCT_NAME} — License Manager")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="Create a new license")
    g.add_argument("--email",    required=True)
    g.add_argument("--name",     default="")
    g.add_argument("--plan",     default="PRO", choices=["TRIAL", "PRO", "ENTERPRISE"])
    g.add_argument("--days",     type=int, default=365, help="Validity days (0=lifetime)")
    g.add_argument("--notes",    default="")
    g.add_argument("--no-email", action="store_true")

    sub.add_parser("list",    help="List all licenses")

    rv = sub.add_parser("revoke", help="Revoke a license immediately")
    rv.add_argument("--key", required=True)

    rs = sub.add_parser("reset-machine", help="Unlock machine (customer got new PC)")
    rs.add_argument("--key", required=True)

    sub.add_parser("alerts", help="Show all security alerts")

    args = ap.parse_args()

    if args.cmd == "generate":
        days = args.days if args.days > 0 else None
        key  = LicenseManager.create(
            email=args.email, name=args.name, plan=args.plan,
            days=days, notes=args.notes, send_email=not args.no_email
        )
        now        = datetime.now(timezone.utc).replace(tzinfo=None)
        expiry_str = (now + timedelta(days=args.days)).strftime("%Y-%m-%d") if args.days else "Lifetime"
        print(f"""
┌──────────────────────────────────────────────┐
│  LICENSE CREATED                             │
├──────────────────────────────────────────────┤
│  Key    : {key}   │
│  Plan   : {args.plan:<10}                          │
│  Email  : {args.email[:36]:<36}    │
│  Expiry : {expiry_str:<10}                          │
│  Mail   : {'Sent ✅' if not args.no_email else 'Skipped ⏭'}                               │
└──────────────────────────────────────────────┘
""")

    elif args.cmd == "list":
        licenses = LicenseManager.list_all()
        if not licenses:
            print("No licenses yet.")
            return
        icons = {"ACTIVE":"✅","EXPIRED":"⏰","REVOKED":"🚫","SUSPENDED":"⏸"}
        print(f"\n{'KEY':<29}  {'EMAIL':<28}  {'PLAN':<5}  {'STATUS':<9}  {'EXPIRES':<11}  LAST SEEN")
        print("─" * 107)
        for lic in licenses:
            exp  = lic["expires_at"][:10] if lic["expires_at"] else "Lifetime "
            seen = lic["last_seen"][:10]  if lic["last_seen"]  else "Never     "
            icon = icons.get(lic["status"], "❓")
            print(f"{lic['key']:<29}  {lic['email']:<28}  {lic['plan']:<5}  {icon} {lic['status']:<7}  {exp:<11}  {seen}")
        print(f"\n{len(licenses)} license(s)\n")

    elif args.cmd == "revoke":
        LicenseManager.revoke(args.key)
        print(f"🚫 Revoked: {args.key.upper()}")
        print("   Customer will be blocked and you will be alerted on their next run.")

    elif args.cmd == "reset-machine":
        LicenseManager.reset_machine(args.key)
        print(f"✅ Machine lock cleared: {args.key.upper()}")
        print("   Customer can now activate on their new PC.")

    elif args.cmd == "alerts":
        alerts = LicenseManager.list_alerts()
        if not alerts:
            print("No alerts.")
            return
        print(f"\n{'TYPE':<25}  {'KEY':<29}  {'DETAIL':<40}  TIMESTAMP")
        print("─" * 107)
        for a in alerts:
            print(f"{a['type']:<25}  {a['key']:<29}  {a['detail'][:40]:<40}  {a['ts'][:16]}")
        print()

if __name__ == "__main__":
    _cli()
