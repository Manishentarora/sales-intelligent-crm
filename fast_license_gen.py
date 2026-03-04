"""
ULTRA-FAST LICENSE GENERATOR
============================
Generate license in 2 CLICKS!

Usage:
1. Click plan button
2. Copy key → Done!

No forms, no typing, instant generation!
"""

import streamlit as st
import secrets
from datetime import datetime, timedelta
import json

st.set_page_config(page_title="⚡ Fast License Gen", page_icon="🔑", layout="centered")

# Password protection
if 'admin_auth' not in st.session_state:
    st.session_state.admin_auth = False

if not st.session_state.admin_auth:
    st.title("🔐 Admin Access")
    pwd = st.text_input("Password", type="password", key="pwd")
    if st.button("Login"):
        # Get from secrets or use default
        correct = st.secrets.get('ADMIN_PASSWORD', 'admin123')
        if pwd == correct:
            st.session_state.admin_auth = True
            st.rerun()
        else:
            st.error("❌ Wrong password")
    st.stop()

# ═══════════════════════════════════════════════════════════
#  ULTRA-FAST GENERATION
# ═══════════════════════════════════════════════════════════

st.title("⚡ Ultra-Fast License Generator")
st.caption("Generate license in 2 clicks!")

# Initialize storage
if 'all_licenses' not in st.session_state:
    # Try to load from secrets
    try:
        if 'LICENSES' in st.secrets:
            st.session_state.all_licenses = json.loads(st.secrets['LICENSES'])
        else:
            st.session_state.all_licenses = {}
    except:
        st.session_state.all_licenses = {}

def generate_instant(plan, days):
    """Generate license instantly"""
    date_str = datetime.now().strftime("%Y%m%d%H%M")  # Include time for uniqueness
    random_hex = secrets.token_hex(4).upper()
    
    if days == 0:
        plan_code = "LIFETIME"
        expires = None
        expires_str = "Never"
    else:
        plan_code = plan
        expires = datetime.now() + timedelta(days=days)
        expires_str = expires.strftime("%Y-%m-%d")
    
    license_key = f"lic_{date_str}_{plan_code}_{random_hex}"
    
    # Store
    license_data = {
        'key': license_key,
        'plan': plan,
        'duration_days': days,
        'created_at': datetime.now().isoformat(),
        'expires_at': expires.isoformat() if expires else None,
        'expires_str': expires_str,
        'status': 'active',
        'email': 'Generated via fast-gen',
        'name': 'Quick License',
        'phone': '',
        'activations': 0,
        'last_used': None
    }
    
    st.session_state.all_licenses[license_key] = license_data
    
    return license_key, expires_str, days

# ═══════════════════════════════════════════════════════════
#  ONE-CLICK PLAN BUTTONS
# ═══════════════════════════════════════════════════════════

st.markdown("### 🚀 Click Any Plan:")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 🎯 Popular Plans")
    
    if st.button("🆓 **7-Day Trial**", use_container_width=True, type="primary"):
        key, exp, days = generate_instant("TRIAL", 7)
        st.session_state.last_generated = key
        st.rerun()
    
    if st.button("💼 **Starter Monthly** (30d)", use_container_width=True):
        key, exp, days = generate_instant("STARTER_M", 30)
        st.session_state.last_generated = key
        st.rerun()
    
    if st.button("💼 **Starter Yearly** (365d)", use_container_width=True):
        key, exp, days = generate_instant("STARTER_Y", 365)
        st.session_state.last_generated = key
        st.rerun()
    
    if st.button("⭐ **Pro Monthly** (30d)", use_container_width=True):
        key, exp, days = generate_instant("PRO_M", 30)
        st.session_state.last_generated = key
        st.rerun()

with col2:
    st.markdown("#### 🎁 Extended Plans")
    
    if st.button("⭐ **Pro Yearly** (365d)", use_container_width=True):
        key, exp, days = generate_instant("PRO_Y", 365)
        st.session_state.last_generated = key
        st.rerun()
    
    if st.button("💎 **Enterprise** (730d)", use_container_width=True):
        key, exp, days = generate_instant("ENTERPRISE", 730)
        st.session_state.last_generated = key
        st.rerun()
    
    if st.button("♾️ **LIFETIME**", use_container_width=True):
        key, exp, days = generate_instant("LIFETIME", 0)
        st.session_state.last_generated = key
        st.rerun()
    
    if st.button("⚙️ **Custom Duration**", use_container_width=True):
        st.session_state.show_custom = True

# Custom duration option
if st.session_state.get('show_custom', False):
    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    with col1:
        custom_days = st.number_input("Days", min_value=1, max_value=10000, value=30)
    with col2:
        st.write("")
        st.write("")
        if st.button("Generate"):
            key, exp, days = generate_instant("CUSTOM", custom_days)
            st.session_state.last_generated = key
            st.session_state.show_custom = False
            st.rerun()

# ═══════════════════════════════════════════════════════════
#  SHOW LAST GENERATED
# ═══════════════════════════════════════════════════════════

if 'last_generated' in st.session_state and st.session_state.last_generated:
    st.markdown("---")
    st.success("✅ License Generated!")
    
    key = st.session_state.last_generated
    data = st.session_state.all_licenses[key]
    
    # Big display
    st.markdown("### 📋 Copy & Send:")
    st.code(key, language=None)
    
    col1, col2 = st.columns(2)
    col1.metric("Plan", data['plan'])
    col2.metric("Expires", data['expires_str'])
    
    # Quick email template
    st.markdown("### 📧 Quick Message:")
    
    message = f"""Your Sales Intelligence Pro License:

{key}

Plan: {data['plan']}
Valid until: {data['expires_str']}

Activate at: https://sales-intel-crm.streamlit.app"""
    
    st.text_area("Copy this:", message, height=150)
    
    # WhatsApp quick link
    whatsapp_text = f"Your Sales Intelligence Pro License: {key}\n\nPlan: {data['plan']}\nValid until: {data['expires_str']}\n\nActivate: https://sales-intel-crm.streamlit.app"
    whatsapp_url = f"https://wa.me/?text={whatsapp_text.replace(' ', '%20').replace('\n', '%0A')}"
    
    st.markdown(f"[📱 Send via WhatsApp]({whatsapp_url})")
    
    if st.button("✅ Done - Generate Another"):
        del st.session_state.last_generated
        st.rerun()

# ═══════════════════════════════════════════════════════════
#  STATS & EXPORT
# ═══════════════════════════════════════════════════════════

st.markdown("---")

col1, col2, col3 = st.columns(3)

total = len(st.session_state.all_licenses)
active = sum(1 for l in st.session_state.all_licenses.values() if l['status'] == 'active')

col1.metric("Total Generated", total)
col2.metric("Active", active)
col3.metric("Today", sum(1 for l in st.session_state.all_licenses.values() 
                         if l['created_at'][:10] == datetime.now().isoformat()[:10]))

# Export for customer app
with st.expander("💾 Export to Customer App (Do this every 5-10 licenses)"):
    st.caption("Copy this to customer app secrets:")
    
    export_json = json.dumps(st.session_state.all_licenses, indent=2)
    
    st.code(f'LICENSES = """{export_json}"""', language="toml")
    
    st.info("""
    **Steps:**
    1. Copy the code above
    2. Go to customer app → Settings → Secrets
    3. Paste (replace old LICENSES if exists)
    4. Save
    5. Licenses are now active!
    """)

# View all licenses
with st.expander("📋 All Licenses"):
    if st.session_state.all_licenses:
        for key, data in sorted(st.session_state.all_licenses.items(), 
                               key=lambda x: x[1]['created_at'], reverse=True):
            col1, col2, col3 = st.columns([3, 1, 1])
            col1.caption(f"`{key}`")
            col2.caption(data['plan'])
            col3.caption(data['expires_str'])
    else:
        st.caption("No licenses generated yet")

# Logout
st.markdown("---")
if st.button("🚪 Logout"):
    st.session_state.admin_auth = False
    st.rerun()
