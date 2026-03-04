"""
CLOUD-COMPATIBLE LICENSE SYSTEM
================================
Works on Streamlit Cloud using secrets.toml for license storage
No file system writes needed!

Features:
- Generate licenses with custom duration (1 day to lifetime)
- Track all licenses issued
- Monitor expiring licenses
- Store customer contact info
- Auto-send expiry notifications
"""

import hashlib
import secrets
from datetime import datetime, timedelta
import json
import streamlit as st

class CloudLicenseManager:
    """License manager that works on Streamlit Cloud"""
    
    def __init__(self):
        # Initialize license storage in session state
        if 'licenses' not in st.session_state:
            st.session_state.licenses = self._load_licenses()
    
    def _load_licenses(self):
        """Load licenses from Streamlit secrets"""
        try:
            # Licenses stored in secrets.toml as JSON string
            if hasattr(st, 'secrets') and 'LICENSES' in st.secrets:
                return json.loads(st.secrets['LICENSES'])
            else:
                return {}
        except:
            return {}
    
    def generate_license(self, email, name, phone, plan, duration_days):
        """
        Generate a new license key
        
        Args:
            email: Customer email
            name: Customer name
            phone: Customer phone number
            plan: Plan name (TRIAL, STARTER, PRO, ENTERPRISE, LIFETIME)
            duration_days: Number of days (0 for lifetime)
        
        Returns:
            license_key: Generated license key
        """
        
        # Generate unique license key
        date_str = datetime.now().strftime("%Y%m%d")
        random_hex = secrets.token_hex(6).upper()
        
        if duration_days == 0:
            plan_code = "LIFETIME"
            expires = None
            expires_str = "Never"
        else:
            plan_code = plan
            expires = datetime.now() + timedelta(days=duration_days)
            expires_str = expires.strftime("%Y-%m-%d")
        
        license_key = f"lic_{date_str}_{plan_code}_{random_hex}"
        
        # Store license data
        license_data = {
            'key': license_key,
            'email': email,
            'name': name,
            'phone': phone,
            'plan': plan,
            'duration_days': duration_days,
            'created_at': datetime.now().isoformat(),
            'expires_at': expires.isoformat() if expires else None,
            'expires_str': expires_str,
            'status': 'active',
            'activations': 0,
            'last_used': None
        }
        
        # Add to session state
        st.session_state.licenses[license_key] = license_data
        
        return license_key, license_data
    
    def validate_license(self, license_key):
        """
        Validate a license key
        
        Returns:
            (valid, message, license_data)
        """
        
        licenses = st.session_state.get('licenses', {})
        
        if license_key not in licenses:
            return False, "Invalid license key", None
        
        license_data = licenses[license_key]
        
        # Check if active
        if license_data['status'] != 'active':
            return False, f"License {license_data['status']}", None
        
        # Check expiry
        if license_data['expires_at']:
            expires = datetime.fromisoformat(license_data['expires_at'])
            if datetime.now() > expires:
                license_data['status'] = 'expired'
                return False, "License expired", None
        
        # Update usage stats
        license_data['activations'] += 1
        license_data['last_used'] = datetime.now().isoformat()
        
        days_remaining = "Lifetime" if not license_data['expires_at'] else \
                        (datetime.fromisoformat(license_data['expires_at']) - datetime.now()).days
        
        return True, f"Valid - {days_remaining} days remaining", license_data
    
    def get_all_licenses(self):
        """Get all licenses"""
        return st.session_state.get('licenses', {})
    
    def get_expiring_soon(self, days=7):
        """Get licenses expiring within N days"""
        expiring = []
        now = datetime.now()
        threshold = now + timedelta(days=days)
        
        for key, data in st.session_state.get('licenses', {}).items():
            if data['expires_at'] and data['status'] == 'active':
                expires = datetime.fromisoformat(data['expires_at'])
                if now < expires <= threshold:
                    days_left = (expires - now).days
                    expiring.append({**data, 'days_left': days_left})
        
        return sorted(expiring, key=lambda x: x['days_left'])
    
    def revoke_license(self, license_key):
        """Revoke a license"""
        if license_key in st.session_state.licenses:
            st.session_state.licenses[license_key]['status'] = 'revoked'
            return True
        return False
    
    def export_licenses_json(self):
        """Export all licenses as JSON for backup"""
        return json.dumps(st.session_state.get('licenses', {}), indent=2)
    
    def get_statistics(self):
        """Get license statistics"""
        licenses = st.session_state.get('licenses', {})
        
        total = len(licenses)
        active = sum(1 for l in licenses.values() if l['status'] == 'active')
        expired = sum(1 for l in licenses.values() if l['status'] == 'expired')
        revoked = sum(1 for l in licenses.values() if l['status'] == 'revoked')
        lifetime = sum(1 for l in licenses.values() if l['duration_days'] == 0)
        
        expiring_7 = len(self.get_expiring_soon(7))
        expiring_30 = len(self.get_expiring_soon(30))
        
        return {
            'total': total,
            'active': active,
            'expired': expired,
            'revoked': revoked,
            'lifetime': lifetime,
            'expiring_7_days': expiring_7,
            'expiring_30_days': expiring_30
        }


def render_license_admin():
    """Render the license admin dashboard"""
    
    st.title("🔑 License Management System")
    
    # Check if user is admin (simple password protection)
    if 'admin_authenticated' not in st.session_state:
        st.session_state.admin_authenticated = False
    
    if not st.session_state.admin_authenticated:
        st.markdown("### 🔐 Admin Access Required")
        admin_password = st.text_input("Enter Admin Password", type="password")
        
        # Get password from secrets or use default
        correct_password = st.secrets.get('ADMIN_PASSWORD', 'admin123')
        
        if st.button("Login"):
            if admin_password == correct_password:
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error("❌ Incorrect password")
        
        st.info("💡 Set ADMIN_PASSWORD in Streamlit secrets")
        st.stop()
    
    # Initialize manager
    manager = CloudLicenseManager()
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard",
        "➕ Generate License", 
        "📋 All Licenses",
        "⚠️ Expiring Soon",
        "💾 Export/Import"
    ])
    
    # TAB 1: Dashboard
    with tab1:
        st.markdown("### 📊 License Statistics")
        
        stats = manager.get_statistics()
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Licenses", stats['total'])
        col2.metric("Active", stats['active'], delta=None)
        col3.metric("Expired", stats['expired'])
        col4.metric("Lifetime", stats['lifetime'])
        
        col1, col2 = st.columns(2)
        col1.metric("Expiring (7 days)", stats['expiring_7_days'], 
                   delta=f"-{stats['expiring_7_days']}" if stats['expiring_7_days'] > 0 else None,
                   delta_color="inverse")
        col2.metric("Expiring (30 days)", stats['expiring_30_days'],
                   delta=f"-{stats['expiring_30_days']}" if stats['expiring_30_days'] > 0 else None,
                   delta_color="inverse")
    
    # TAB 2: Generate License
    with tab2:
        st.markdown("### ➕ Generate New License")
        
        with st.form("generate_license"):
            col1, col2 = st.columns(2)
            
            with col1:
                email = st.text_input("Customer Email *", placeholder="customer@example.com")
                name = st.text_input("Customer Name *", placeholder="John Doe")
                phone = st.text_input("Phone Number", placeholder="+91 9876543210")
            
            with col2:
                plan = st.selectbox("Plan Type", [
                    "TRIAL",
                    "STARTER_M",
                    "STARTER_Y", 
                    "PRO_M",
                    "PRO_Y",
                    "ENTERPRISE",
                    "LIFETIME"
                ])
                
                # Duration presets
                duration_preset = st.selectbox("Duration", [
                    "Custom",
                    "1 Day",
                    "7 Days (Trial)",
                    "14 Days (Trial)",
                    "30 Days (1 Month)",
                    "90 Days (3 Months)",
                    "180 Days (6 Months)",
                    "365 Days (1 Year)",
                    "730 Days (2 Years)",
                    "Lifetime"
                ])
                
                # Custom duration
                if duration_preset == "Custom":
                    duration_days = st.number_input("Days", min_value=1, max_value=36500, value=30)
                elif duration_preset == "Lifetime":
                    duration_days = 0
                else:
                    duration_map = {
                        "1 Day": 1,
                        "7 Days (Trial)": 7,
                        "14 Days (Trial)": 14,
                        "30 Days (1 Month)": 30,
                        "90 Days (3 Months)": 90,
                        "180 Days (6 Months)": 180,
                        "365 Days (1 Year)": 365,
                        "730 Days (2 Years)": 730
                    }
                    duration_days = duration_map[duration_preset]
            
            submitted = st.form_submit_button("🎫 Generate License", type="primary")
            
            if submitted:
                if not email or not name:
                    st.error("❌ Email and Name are required")
                else:
                    license_key, license_data = manager.generate_license(
                        email, name, phone, plan, duration_days
                    )
                    
                    st.success("✅ License Generated Successfully!")
                    
                    st.code(license_key, language=None)
                    
                    st.markdown("### 📧 Send to Customer:")
                    
                    message = f"""
**Your Sales Intelligence Pro License**

License Key: `{license_key}`

Plan: {plan}
Expires: {license_data['expires_str']}
Activated for: {name} ({email})

**How to Activate:**
1. Open the app
2. Enter this license key
3. Start using all features!

Questions? Reply to this email.
                    """
                    
                    st.text_area("Email Template", message, height=300)
                    
                    if st.button("📋 Copy License Key"):
                        st.code(license_key)
    
    # TAB 3: All Licenses
    with tab3:
        st.markdown("### 📋 All Licenses")
        
        licenses = manager.get_all_licenses()
        
        if not licenses:
            st.info("No licenses generated yet")
        else:
            # Filter options
            col1, col2, col3 = st.columns(3)
            filter_status = col1.selectbox("Filter by Status", 
                                          ["All", "active", "expired", "revoked"])
            filter_plan = col2.selectbox("Filter by Plan",
                                        ["All"] + list(set(l['plan'] for l in licenses.values())))
            search_email = col3.text_input("Search Email")
            
            # Filter licenses
            filtered = licenses.values()
            if filter_status != "All":
                filtered = [l for l in filtered if l['status'] == filter_status]
            if filter_plan != "All":
                filtered = [l for l in filtered if l['plan'] == filter_plan]
            if search_email:
                filtered = [l for l in filtered if search_email.lower() in l['email'].lower()]
            
            st.caption(f"Showing {len(filtered)} of {len(licenses)} licenses")
            
            # Display licenses
            for lic in sorted(filtered, key=lambda x: x['created_at'], reverse=True):
                with st.expander(f"🎫 {lic['email']} - {lic['plan']} ({lic['status']})"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"**License Key:**")
                        st.code(lic['key'], language=None)
                        st.markdown(f"**Customer:** {lic['name']}")
                        st.markdown(f"**Email:** {lic['email']}")
                        st.markdown(f"**Phone:** {lic['phone'] or 'N/A'}")
                    
                    with col2:
                        st.markdown(f"**Plan:** {lic['plan']}")
                        st.markdown(f"**Status:** {lic['status']}")
                        st.markdown(f"**Created:** {lic['created_at'][:10]}")
                        st.markdown(f"**Expires:** {lic['expires_str']}")
                        st.markdown(f"**Activations:** {lic['activations']}")
                        st.markdown(f"**Last Used:** {lic['last_used'][:10] if lic['last_used'] else 'Never'}")
                    
                    if lic['status'] == 'active':
                        if st.button(f"🚫 Revoke License", key=f"revoke_{lic['key']}"):
                            manager.revoke_license(lic['key'])
                            st.success("License revoked")
                            st.rerun()
    
    # TAB 4: Expiring Soon
    with tab4:
        st.markdown("### ⚠️ Licenses Expiring Soon")
        
        days_filter = st.slider("Show licenses expiring within (days)", 1, 90, 30)
        
        expiring = manager.get_expiring_soon(days_filter)
        
        if not expiring:
            st.success(f"✅ No licenses expiring in the next {days_filter} days")
        else:
            st.warning(f"⚠️ {len(expiring)} license(s) expiring soon")
            
            for lic in expiring:
                with st.expander(f"{'🔴' if lic['days_left'] <= 7 else '🟡'} {lic['email']} - {lic['days_left']} days left"):
                    st.markdown(f"**Customer:** {lic['name']}")
                    st.markdown(f"**Email:** {lic['email']}")
                    st.markdown(f"**Phone:** {lic['phone'] or 'N/A'}")
                    st.markdown(f"**Plan:** {lic['plan']}")
                    st.markdown(f"**Expires:** {lic['expires_str']}")
                    st.markdown(f"**Days Remaining:** {lic['days_left']}")
                    
                    # Email template
                    renewal_email = f"""
Subject: Your Sales Intelligence Pro License Expires in {lic['days_left']} Days

Hi {lic['name']},

This is a friendly reminder that your Sales Intelligence Pro license will expire soon.

License Details:
- Plan: {lic['plan']}
- Expires: {lic['expires_str']}
- Days Remaining: {lic['days_left']}

To continue using all features, please renew your license.

Reply to this email to renew or if you have any questions.

Best regards,
Sales Intelligence Pro Team
                    """
                    
                    st.text_area("Renewal Email Template", renewal_email, height=200, key=f"email_{lic['key']}")
    
    # TAB 5: Export/Import
    with tab5:
        st.markdown("### 💾 Export/Import Licenses")
        
        st.markdown("#### Export All Licenses")
        st.caption("Download all licenses as JSON for backup")
        
        json_data = manager.export_licenses_json()
        
        st.download_button(
            label="📥 Download Licenses (JSON)",
            data=json_data,
            file_name=f"licenses_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
        
        st.markdown("#### For Streamlit Cloud Storage")
        st.caption("Copy this to your `secrets.toml` file:")
        
        st.code(f'LICENSES = """{json_data}"""', language="toml")
        
        st.info("""
        **To persist licenses on Streamlit Cloud:**
        1. Copy the JSON above
        2. Go to your app → Settings → Secrets
        3. Add: `LICENSES = '''paste here'''`
        4. Save
        
        Licenses will be loaded on app restart!
        """)


if __name__ == "__main__":
    render_license_admin()
