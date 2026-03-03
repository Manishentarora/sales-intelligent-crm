"""
SUBSCRIPTION LICENSE SYSTEM
Monthly/Yearly plans with auto-renewal, payment webhooks, grace periods
"""

import os, sys, json, hmac, hashlib, secrets, string, smtplib, sqlite3, platform, uuid, argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from cryptography.fernet import Fernet
    CRYPTO_OK = True
except:
    CRYPTO_OK = False

# ══════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════
PRODUCT_NAME = "Sales Intelligence Pro"
PRODUCT_CODE = "SALE"
ADMIN_EMAIL  = "your@email.com"
ADMIN_SECRET = "replace-with-long-random-secret-string"

SMTP_HOST    = "smtp.gmail.com"
SMTP_PORT    = 587
SMTP_USER    = "your@gmail.com"
SMTP_PASS    = "xxxx xxxx xxxx xxxx"

DB_PATH      = Path(__file__).parent / "subscriptions.db"
CACHE_FILE   = Path.home() / f".{PRODUCT_CODE.lower()}_sub"

# Subscription Plans
PLANS = {
    'TRIAL': {
        'name': 'Free Trial',
        'price': 0,
        'billing': 'trial',
        'days': 14,
        'features': ['1 user', 'Basic analytics', '100 transactions/month'],
        'max_machines': 1,
        'offline_days': 1
    },
    'STARTER_M': {
        'name': 'Starter Monthly',
        'price': 999,
        'billing': 'monthly',
        'days': 30,
        'features': ['1 user', 'All analytics', 'Unlimited data', 'Email support'],
        'max_machines': 1,
        'offline_days': 3
    },
    'STARTER_Y': {
        'name': 'Starter Yearly',
        'price': 9999,
        'billing': 'yearly',
        'days': 365,
        'features': ['1 user', 'All analytics', 'Unlimited data', 'Email support', '2 months FREE'],
        'max_machines': 2,
        'offline_days': 7
    },
    'PRO_M': {
        'name': 'Professional Monthly',
        'price': 2999,
        'billing': 'monthly',
        'days': 30,
        'features': ['3 users', 'AI Assistant', 'OCR Support', 'Priority support'],
        'max_machines': 3,
        'offline_days': 7
    },
    'PRO_Y': {
        'name': 'Professional Yearly',
        'price': 29999,
        'billing': 'yearly',
        'days': 365,
        'features': ['3 users', 'AI Assistant', 'OCR Support', 'Priority support', '2 months FREE'],
        'max_machines': 3,
        'offline_days': 14
    },
    'ENTERPRISE': {
        'name': 'Enterprise',
        'price': 0,  # Custom pricing
        'billing': 'custom',
        'days': 365,
        'features': ['Unlimited users', 'Custom integrations', 'Dedicated support', 'SLA'],
        'max_machines': 10,
        'offline_days': 30
    }
}

# ══════════════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════════════
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _init_db():
    conn = _db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sub_id          TEXT    UNIQUE NOT NULL,
            email           TEXT    NOT NULL,
            name            TEXT    DEFAULT '',
            plan            TEXT    NOT NULL,
            status          TEXT    DEFAULT 'active',
            machine_hash    TEXT    DEFAULT '',
            billing_cycle   TEXT,
            next_bill_date  TEXT,
            created_at      TEXT    DEFAULT (datetime('now')),
            expires_at      TEXT,
            cancelled_at    TEXT,
            last_seen       TEXT,
            payment_method  TEXT,
            customer_id     TEXT,
            notes           TEXT    DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            sub_id      TEXT,
            type        TEXT,
            amount      REAL,
            status      TEXT,
            payment_id  TEXT,
            ts          TEXT    DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            type       TEXT,
            sub_id     TEXT    DEFAULT '',
            machine_id TEXT    DEFAULT '',
            detail     TEXT,
            ts         TEXT    DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()

# ══════════════════════════════════════════════════════
#  EMAIL
# ══════════════════════════════════════════════════════
def _send_email(to: str, subject: str, body: str):
    if SMTP_USER == "your@gmail.com":
        print(f"[EMAIL]\nTo: {to}\n{subject}\n{body}")
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

def _alert_admin(alert_type: str, detail: str, sub_id: str = "", machine_id: str = ""):
    _init_db()
    conn = _db()
    conn.execute(
        "INSERT INTO alerts (type, sub_id, machine_id, detail) VALUES (?,?,?,?)",
        (alert_type, sub_id, machine_id[:32] if machine_id else "", detail)
    )
    conn.commit()
    conn.close()

    body = f"""SUBSCRIPTION ALERT — {PRODUCT_NAME}

Time:          {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC
Alert:         {alert_type}
Subscription:  {sub_id or 'NONE'}
Machine:       {(machine_id[:24] + '...') if len(machine_id) > 24 else machine_id or 'Unknown'}
Detail:        {detail}

Action: Review subscriptions database.

— {PRODUCT_NAME} Subscription System
"""
    _send_email(ADMIN_EMAIL, f"🔔 ALERT: {alert_type}", body)

# ══════════════════════════════════════════════════════
#  SUBSCRIPTION ID GENERATION
# ══════════════════════════════════════════════════════
def _generate_sub_id(plan: str) -> str:
    """sub_YYYYMMDD_PLAN_RAND"""
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    rand = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"sub_{date_str}_{plan}_{rand}"

# ══════════════════════════════════════════════════════
#  MACHINE ID
# ══════════════════════════════════════════════════════
def _machine_id() -> str:
    try:
        raw = f"{uuid.getnode()}:{platform.node()}:{platform.system()}{platform.release()}:{PRODUCT_CODE}"
        return hashlib.sha256(raw.encode()).hexdigest()
    except:
        return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()

# ══════════════════════════════════════════════════════
#  ENCRYPTED CACHE
# ══════════════════════════════════════════════════════
def _cache_key():
    import base64
    raw = f"{_machine_id()}:{ADMIN_SECRET}"
    return base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())

def _save_cache(data: dict):
    try:
        payload = json.dumps(data).encode()
        if CRYPTO_OK:
            enc = Fernet(_cache_key()).encrypt(payload)
        else:
            import base64
            enc = base64.b64encode(payload)
        CACHE_FILE.write_bytes(enc)
    except:
        pass

def _load_cache():
    try:
        if not CACHE_FILE.exists():
            return None
        enc = CACHE_FILE.read_bytes()
        if CRYPTO_OK:
            payload = Fernet(_cache_key()).decrypt(enc)
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

# ══════════════════════════════════════════════════════
#  VALIDATION
# ══════════════════════════════════════════════════════
def _validate(sub_id: str, machine: str) -> dict:
    _init_db()
    
    conn = _db()
    row  = conn.execute("SELECT * FROM subscriptions WHERE sub_id = ?", (sub_id,)).fetchone()
    conn.close()
    
    if not row:
        return {"ok": False, "reason": "NOT_FOUND", "msg": "Subscription not found."}
    
    sub = dict(row)
    
    # Status check
    if sub["status"] == "cancelled":
        return {"ok": False, "reason": "CANCELLED", "msg": "Subscription cancelled."}
    
    if sub["status"] == "suspended":
        return {"ok": False, "reason": "SUSPENDED", "msg": "Subscription suspended."}
    
    # Expiry check
    if sub["expires_at"]:
        if datetime.fromisoformat(sub["expires_at"]) < datetime.now(timezone.utc).replace(tzinfo=None):
            conn = _db()
            conn.execute("UPDATE subscriptions SET status='expired' WHERE sub_id=?", (sub_id,))
            conn.commit()
            conn.close()
            return {"ok": False, "reason": "EXPIRED", "msg": "Subscription expired. Renew to continue."}
    
    # Machine lock
    machine_hash   = hashlib.sha256(machine.encode()).hexdigest()[:32]
    stored_machine = sub.get("machine_hash", "")
    
    plan_info = PLANS.get(sub["plan"], {})
    max_machines = plan_info.get("max_machines", 1)
    
    if stored_machine == "":
        # First activation
        conn = _db()
        conn.execute(
            "UPDATE subscriptions SET machine_hash=?, last_seen=? WHERE sub_id=?",
            (machine_hash, datetime.now(timezone.utc).replace(tzinfo=None).isoformat(), sub_id)
        )
        conn.commit()
        conn.close()
    elif stored_machine != machine_hash:
        # Different machine — check if plan allows multiple
        if max_machines == 1:
            return {"ok": False, "reason": "WRONG_MACHINE", 
                    "msg": "Subscription locked to another device. Contact support."}
    else:
        # Same machine — update last seen
        conn = _db()
        conn.execute("UPDATE subscriptions SET last_seen=? WHERE sub_id=?",
                     (datetime.now(timezone.utc).replace(tzinfo=None).isoformat(), sub_id))
        conn.commit()
        conn.close()
    
    return {
        "ok": True,
        "plan": sub["plan"],
        "name": sub["name"],
        "email": sub["email"],
        "expires_at": sub["expires_at"],
        "next_bill": sub["next_bill_date"],
        "offline_days": plan_info.get("offline_days", 3)
    }

# ══════════════════════════════════════════════════════
#  SUBSCRIPTION MANAGER
# ══════════════════════════════════════════════════════
class SubscriptionManager:
    
    @staticmethod
    def create(email: str, name: str, plan: str, payment_method: str = "", 
               customer_id: str = "", send_email: bool = True) -> str:
        _init_db()
        
        sub_id    = _generate_sub_id(plan)
        plan_info = PLANS.get(plan, PLANS['TRIAL'])
        
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        expires_at   = (now + timedelta(days=plan_info['days'])).isoformat()
        next_bill    = None
        billing_cycle = plan_info['billing']
        
        if billing_cycle in ['monthly', 'yearly']:
            next_bill = expires_at
        
        conn = _db()
        conn.execute("""
            INSERT INTO subscriptions 
            (sub_id, email, name, plan, expires_at, next_bill_date, billing_cycle, payment_method, customer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sub_id, email.lower(), name, plan, expires_at, next_bill, billing_cycle, payment_method, customer_id))
        conn.commit()
        conn.close()
        
        if send_email:
            SubscriptionManager._send_welcome_email(email, name, plan, sub_id, expires_at)
        
        return sub_id
    
    @staticmethod
    def renew(sub_id: str) -> bool:
        """Renew subscription for next billing cycle"""
        conn = _db()
        row  = conn.execute("SELECT * FROM subscriptions WHERE sub_id = ?", (sub_id,)).fetchone()
        
        if not row:
            conn.close()
            return False
        
        sub = dict(row)
        plan_info = PLANS.get(sub['plan'], {})
        days = plan_info.get('days', 30)
        
        new_expires = (datetime.fromisoformat(sub['expires_at']) + timedelta(days=days)).isoformat()
        new_bill    = new_expires if sub['billing_cycle'] in ['monthly', 'yearly'] else None
        
        conn.execute("""
            UPDATE subscriptions 
            SET expires_at = ?, next_bill_date = ?, status = 'active'
            WHERE sub_id = ?
        """, (new_expires, new_bill, sub_id))
        conn.commit()
        conn.close()
        
        # Log transaction
        conn = _db()
        conn.execute(
            "INSERT INTO transactions (sub_id, type, amount, status) VALUES (?, 'renewal', ?, 'completed')",
            (sub_id, plan_info.get('price', 0))
        )
        conn.commit()
        conn.close()
        
        return True
    
    @staticmethod
    def cancel(sub_id: str):
        conn = _db()
        conn.execute(
            "UPDATE subscriptions SET status='cancelled', cancelled_at=? WHERE sub_id=?",
            (datetime.now(timezone.utc).replace(tzinfo=None).isoformat(), sub_id)
        )
        conn.commit()
        conn.close()
    
    @staticmethod
    def list_all():
        _init_db()
        conn = _db()
        rows = conn.execute("SELECT * FROM subscriptions ORDER BY created_at DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    
    @staticmethod
    def list_expiring_soon(days: int = 7):
        """Get subscriptions expiring in N days"""
        _init_db()
        cutoff = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=days)).isoformat()
        conn = _db()
        rows = conn.execute(
            "SELECT * FROM subscriptions WHERE expires_at <= ? AND status='active' ORDER BY expires_at",
            (cutoff,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    
    @staticmethod
    def _send_welcome_email(email: str, name: str, plan: str, sub_id: str, expires: str):
        plan_info = PLANS.get(plan, {})
        expiry_str = expires[:10] if expires else "N/A"
        
        features = "\n".join([f"  ✅ {f}" for f in plan_info.get('features', [])])
        
        body = f"""Welcome to {PRODUCT_NAME}!

Dear {name or 'Customer'},

Your subscription is active.

📋 SUBSCRIPTION DETAILS:
  ID:       {sub_id}
  Plan:     {plan_info.get('name', plan)}
  Valid:    Until {expiry_str}
  Price:    ₹{plan_info.get('price', 0):,}/month

🎯 FEATURES:
{features}

🚀 GET STARTED:
  1. Run the application
  2. Your subscription is automatically activated
  3. Enjoy all premium features!

📧 SUPPORT:
  Reply to this email for any questions.

— {PRODUCT_NAME} Team
"""
        _send_email(email, f"Welcome to {PRODUCT_NAME} — {plan_info.get('name')}", body)

# ══════════════════════════════════════════════════════
#  SUBSCRIPTION GUARD (Streamlit Integration)
# ══════════════════════════════════════════════════════
class SubscriptionGuard:
    
    @staticmethod
    def enforce():
        import streamlit as st
        
        if st.session_state.get("_sub_ok"):
            SubscriptionGuard._sidebar_badge()
            return
        
        sub_id = SubscriptionGuard._get_stored_sub()
        
        if not sub_id:
            SubscriptionGuard._subscription_screen()
            st.stop()
            return
        
        machine = _machine_id()
        result  = _validate(sub_id, machine)
        
        if result["ok"]:
            cache_data = {**result, "sub_id": sub_id, "machine_id": machine,
                          "last_validated": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()}
            _save_cache(cache_data)
            SubscriptionGuard._set_session(result, sub_id, offline=False)
            SubscriptionGuard._sidebar_badge()
            return
        
        # Offline fallback
        if result["reason"] in ("ERROR", "NETWORK"):
            cached = _load_cache()
            if cached and cached.get("sub_id") == sub_id:
                last = datetime.fromisoformat(cached.get("last_validated", "2000-01-01"))
                days_offline = (datetime.now(timezone.utc).replace(tzinfo=None) - last).days
                allowed = cached.get("offline_days", 3)
                if days_offline <= allowed:
                    SubscriptionGuard._set_session(cached, sub_id, offline=True,
                                                    days_left=allowed - days_offline)
                    SubscriptionGuard._sidebar_badge()
                    return
                else:
                    SubscriptionGuard._crash(st, sub_id, machine, "OFFLINE_EXPIRED",
                                              f"Offline limit ({allowed}d) exceeded. Connect to internet.")
                    return
        
        SubscriptionGuard._crash(st, sub_id, machine, result["reason"], result["msg"])
    
    @staticmethod
    def _crash(st, sub_id, machine, reason, msg):
        _clear_cache()
        _alert_admin(reason, msg, sub_id=sub_id, machine_id=machine)
        
        st.markdown("""<style>[data-testid="stSidebar"]{display:none}
        .main .block-container{max-width:600px;margin:auto;padding-top:5rem}</style>""",
                    unsafe_allow_html=True)
        
        st.markdown("## 🔔 Subscription Issue")
        st.error(f"**{msg}**")
        st.markdown(f"""
---
**Reason:** `{reason}`

**Next Steps:**
- Renew your subscription
- Contact support: **{ADMIN_EMAIL}**

*This has been logged and reported.*
""")
        st.stop()
    
    @staticmethod
    def _subscription_screen():
        import streamlit as st
        st.markdown("""<style>[data-testid="stSidebar"]{display:none}
        .main .block-container{max-width:700px;margin:auto;padding-top:4rem}</style>""",
                    unsafe_allow_html=True)
        
        st.markdown(f"## 💎 {PRODUCT_NAME}")
        st.markdown("Choose your plan to get started:")
        
        # Show plans
        cols = st.columns(3)
        for i, (plan_key, plan) in enumerate(list(PLANS.items())[:3]):
            if plan['billing'] == 'trial':
                continue
            with cols[i % 3]:
                with st.container(border=True):
                    st.markdown(f"### {plan['name']}")
                    st.markdown(f"**₹{plan['price']:,}** /{plan['billing']}")
                    for feat in plan['features']:
                        st.caption(f"✅ {feat}")
                    if st.button(f"Select {plan['name']}", key=plan_key, use_container_width=True):
                        st.info(f"Contact {ADMIN_EMAIL} to activate {plan['name']}")
        
        st.markdown("---")
        st.caption(f"Already have a subscription? Contact {ADMIN_EMAIL}")
    
    @staticmethod
    def _sidebar_badge():
        import streamlit as st
        plan = st.session_state.get("_sub_plan", "")
        name = st.session_state.get("_sub_name", "")
        offline = st.session_state.get("_sub_offline", False)
        days = st.session_state.get("_sub_days_left", 0)
        
        with st.sidebar:
            st.markdown("---")
            if offline:
                st.warning(f"📶 Offline — {days}d left")
            else:
                plan_info = PLANS.get(plan, {})
                st.success(f"✅ {plan_info.get('name', plan)}")
            if name:
                st.caption(f"👤 {name}")
    
    @staticmethod
    def _set_session(data, sub_id, offline, days_left=0):
        import streamlit as st
        st.session_state.update({
            "_sub_ok": True,
            "_sub_id": sub_id,
            "_sub_plan": data.get("plan", ""),
            "_sub_name": data.get("name", ""),
            "_sub_offline": offline,
            "_sub_days_left": days_left
        })
    
    @staticmethod
    def _get_stored_sub():
        sub_file = Path(__file__).parent / ".sub_id"
        try:
            return sub_file.read_text().strip() if sub_file.exists() else ""
        except:
            return ""

# ══════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════
def _cli():
    ap = argparse.ArgumentParser(description=f"{PRODUCT_NAME} Subscription Manager")
    sub = ap.add_subparsers(dest="cmd", required=True)
    
    c = sub.add_parser("create", help="Create new subscription")
    c.add_argument("--email", required=True)
    c.add_argument("--name", default="")
    c.add_argument("--plan", required=True, choices=list(PLANS.keys()))
    
    r = sub.add_parser("renew", help="Renew subscription")
    r.add_argument("--sub-id", required=True)
    
    x = sub.add_parser("cancel", help="Cancel subscription")
    x.add_argument("--sub-id", required=True)
    
    sub.add_parser("list", help="List all subscriptions")
    
    e = sub.add_parser("expiring", help="Show expiring subscriptions")
    e.add_argument("--days", type=int, default=7)
    
    args = ap.parse_args()
    
    if args.cmd == "create":
        sub_id = SubscriptionManager.create(args.email, args.name, args.plan)
        plan_info = PLANS[args.plan]
        print(f"""
┌──────────────────────────────────────────┐
│  SUBSCRIPTION CREATED                    │
├──────────────────────────────────────────┤
│  ID    : {sub_id}         │
│  Plan  : {plan_info['name']:<30}   │
│  Email : {args.email[:35]:<35}  │
│  Price : ₹{plan_info['price']:,}/mo                   │
│  Status: Active                          │
└──────────────────────────────────────────┘
""")
    
    elif args.cmd == "renew":
        if SubscriptionManager.renew(args.sub_id):
            print(f"✅ Renewed: {args.sub_id}")
        else:
            print(f"❌ Not found: {args.sub_id}")
    
    elif args.cmd == "cancel":
        SubscriptionManager.cancel(args.sub_id)
        print(f"🚫 Cancelled: {args.sub_id}")
    
    elif args.cmd == "list":
        subs = SubscriptionManager.list_all()
        if not subs:
            print("No subscriptions.")
            return
        print(f"\n{'SUB ID':<30}  {'EMAIL':<30}  {'PLAN':<15}  {'STATUS':<10}  EXPIRES")
        print("─" * 100)
        for s in subs:
            exp = s['expires_at'][:10] if s['expires_at'] else "N/A"
            print(f"{s['sub_id']:<30}  {s['email']:<30}  {s['plan']:<15}  {s['status']:<10}  {exp}")
        print(f"\n{len(subs)} subscription(s)\n")
    
    elif args.cmd == "expiring":
        subs = SubscriptionManager.list_expiring_soon(args.days)
        print(f"\n{len(subs)} subscription(s) expiring in {args.days} days:\n")
        for s in subs:
            print(f"  {s['sub_id']:<30}  {s['email']:<30}  {s['expires_at'][:10]}")

if __name__ == "__main__":
    _cli()
