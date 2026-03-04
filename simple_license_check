"""
SIMPLE LICENSE VALIDATION FOR MAIN APP
======================================
Validates licenses using Streamlit secrets
No file writes - works on Streamlit Cloud!
"""

import streamlit as st
import json
from datetime import datetime

def validate_license_simple(license_key):
    """
    Simple license validation using secrets
    
    Returns:
        (valid, message)
    """
    
    try:
        # Load licenses from secrets
        if hasattr(st, 'secrets') and 'LICENSES' in st.secrets:
            licenses = json.loads(st.secrets['LICENSES'])
        else:
            # No licenses configured - allow access (development mode)
            return True, "Development mode - no license required"
        
        # Check if license exists
        if license_key not in licenses:
            return False, "Invalid license key"
        
        license_data = licenses[license_key]
        
        # Check status
        if license_data.get('status') != 'active':
            return False, f"License {license_data.get('status', 'inactive')}"
        
        # Check expiry
        expires_at = license_data.get('expires_at')
        if expires_at:
            expires = datetime.fromisoformat(expires_at)
            if datetime.now() > expires:
                return False, "License expired"
            
            days_left = (expires - datetime.now()).days
            return True, f"Valid - {days_left} days remaining"
        else:
            return True, "Valid - Lifetime license"
    
    except Exception as e:
        # If error, allow access (don't block users due to config issues)
        return True, f"Validation bypassed - {str(e)}"


def show_license_screen():
    """Show license activation screen"""
    
    st.markdown("""
    <div style='text-align: center; padding: 2rem;'>
        <h1>🔑 Sales Intelligence Pro</h1>
        <p style='font-size: 1.2rem; color: #666;'>Enter your license key to activate.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Check if already activated in session
    if 'license_valid' in st.session_state and st.session_state.license_valid:
        return True
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        license_key = st.text_input(
            "License Key",
            placeholder="lic_20260303_...",
            help="Enter the license key provided to you"
        )
        
        if st.button("🚀 Activate License", type="primary", use_container_width=True):
            if license_key:
                valid, message = validate_license_simple(license_key)
                
                if valid:
                    st.session_state.license_valid = True
                    st.session_state.license_key = license_key
                    st.session_state.license_message = message
                    st.success(f"✅ {message}")
                    st.balloons()
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
            else:
                st.warning("Please enter a license key")
        
        # Development bypass (remove in production)
        st.markdown("---")
        with st.expander("🔧 Development Access"):
            if st.button("Skip License (Development)", type="secondary"):
                st.session_state.license_valid = True
                st.session_state.license_message = "Development mode"
                st.rerun()
    
    return False
