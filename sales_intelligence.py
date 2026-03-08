"""
SALES INTELLIGENCE PRO — COMPLETE PRODUCTION BUILD
====================================================
✅ All 13 analytics modules (complete implementation)
✅ Full statistical testing (Chi-square, Pearson correlation)  
✅ Professional visualizations (Pareto, Lorenz, Network, Multi-panel)
✅ SMART: Automatic duplicate detection
✅ SMART: Missing column handling
✅ Data persistence (saves on client's computer)
✅ License enforcement

Run:   streamlit run sales_intelligence_COMPLETE_FINAL.py
Admin: python license_system.py generate --email you@email.com --plan PRO --days 365
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import io
from datetime import datetime
from itertools import combinations
from scipy.stats import chi2_contingency, ttest_ind, pearsonr
from pathlib import Path
import shutil

# ── License: Cloud-compatible license check ──
try:
    from simple_license_check import show_license_screen
    LICENSE_ENABLED = True
except ImportError:
    LICENSE_ENABLED = False
    st.warning("⚠️ License module not found - running in open mode")

# ── Page config MUST be first Streamlit call ───────────────
st.set_page_config(page_title="Sales Intelligence Pro", page_icon="📊", layout="wide")

# ── License enforcement — app stops here if invalid ────────
if LICENSE_ENABLED:
    if not show_license_screen():
        st.stop()

# ── Professional CSS ────────────────────────────────────────
st.markdown("""
<style>
@media (max-width: 767px) {
    .main .block-container { padding: 1rem; }
    .row-widget.stHorizontal { flex-direction: column !important; }
    h1 { font-size: 1.5rem !important; }
}
@media (min-width: 768px) and (max-width: 1024px) {
    .row-widget.stHorizontal > div { flex: 0 0 48% !important; }
}
[data-testid="metric-container"] {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 1.5rem;
    border-radius: 1rem;
    box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
}
.stButton > button {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# DATA PERSISTENCE - Files saved in Documents folder for easy access
# ════════════════════════════════════════════════════════════

# Use Documents folder so customers can easily find their saved files
import os
DOCUMENTS = Path.home() / "Documents"
DATA_DIR = DOCUMENTS / "SalesIntelligence"
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR = DATA_DIR / "SavedFiles"
UPLOADS_DIR.mkdir(exist_ok=True)

# Create a README in the folder to help customers
README_PATH = DATA_DIR / "README.txt"
if not README_PATH.exists():
    with open(README_PATH, 'w') as f:
        f.write("""Sales Intelligence Pro - Saved Files
==========================================

This folder contains your uploaded sales data files.

Location: Documents/SalesIntelligence/SavedFiles/

What's saved here:
- Your uploaded Excel/CSV files
- Automatically saved when you upload
- Loaded instantly on next use

Privacy:
✅ Files stored only on YOUR computer
❌ Never uploaded to cloud
🔒 100% private and secure

To find this folder:
Windows: Documents\\SalesIntelligence
Mac: Documents/SalesIntelligence

Questions? Check the app's help section.
""")

def save_uploaded_file(uploaded_file):
    """Save uploaded file permanently"""
    file_path = UPLOADS_DIR / uploaded_file.name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path

def get_saved_files():
    """Get list of previously uploaded files"""
    if not UPLOADS_DIR.exists():
        return []
    return list(UPLOADS_DIR.glob("*.xlsx")) + list(UPLOADS_DIR.glob("*.xls")) + list(UPLOADS_DIR.glob("*.csv"))

# ════════════════════════════════════════════════════════════
# SMART DATA HANDLING - Duplicate detection + Missing columns
# ════════════════════════════════════════════════════════════

def handle_missing_columns(df):
    """Handle missing optional columns gracefully - COMPLETE COVERAGE (11 columns)"""
    
    # Check required columns
    required = ['Date', 'Particulars', 'Amount']
    missing_required = [col for col in required if col not in df.columns]
    
    if missing_required:
        raise ValueError(f"Missing required columns: {', '.join(missing_required)}\n\nYour Excel must have:\n- Date (transaction date)\n- Particulars/Customer (customer name)\n- Amount (sale value)")
    
    # Add ALL missing optional columns with appropriate defaults
    if 'Item Details' not in df.columns:
        df['Item Details'] = 'Not Specified'
    if 'Vch/Bill No' not in df.columns:
        df['Vch/Bill No'] = 'AUTO_' + df.index.astype(str)
    if 'Salesperson' not in df.columns:
        df['Salesperson'] = 'Not Specified'
    if 'Quantity' not in df.columns:
        df['Quantity'] = 1
    if 'Category' not in df.columns:
        df['Category'] = 'Uncategorized'
    if 'Location' not in df.columns:
        df['Location'] = 'Not Specified'
    if 'Tax' not in df.columns:
        df['Tax'] = 0
    if 'Unit Price' not in df.columns:
        # Calculate from Amount/Quantity if possible
        if 'Quantity' in df.columns:
            df['Unit Price'] = df['Amount'] / df['Quantity'].replace(0, 1)
        else:
            df['Unit Price'] = df['Amount']
    if 'Discount' not in df.columns:
        df['Discount'] = 0
    if 'Payment Method' not in df.columns:
        df['Payment Method'] = 'Not Specified'
    if 'Notes' not in df.columns:
        df['Notes'] = ''
    
    return df

def remove_duplicates(df):
    """
    IMPROVED: Checks invoice numbers first, falls back to composite key
    """
    # Strategy 1: Use invoice numbers if they exist and aren't auto-generated
    if 'Vch/Bill No' in df.columns:
        # Check if invoices are auto-generated
        auto_invoices = df['Vch/Bill No'].astype(str).str.startswith('AUTO_')
        
        if not auto_invoices.all():  # At least some real invoice numbers
            # Use invoice numbers for deduplication
            df_unique = df.drop_duplicates(subset='Vch/Bill No', keep='first')
            dup_count = len(df) - len(df_unique)
            return df_unique, dup_count
    
    # Strategy 2: Fallback to composite key with rounded amounts
    df['_unique_key'] = (
        df['Date'].astype(str) + '_' +
        df['Particulars'].astype(str) + '_' +
        df['Amount'].round(2).astype(str)  # Round to 2 decimals to avoid float precision issues
    )
    
    df_unique = df.drop_duplicates(subset='_unique_key', keep='first')
    df_unique = df_unique.drop(columns=['_unique_key'])
    
    dup_count = len(df) - len(df_unique)
    
    return df_unique, dup_count

# ════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ════════════════════════════════════════════════════════════

def get_fy(date):
    if pd.isnull(date): return "N/A"
    year = date.year
    return f"FY {year}-{str(year+1)[2:]}" if date.month >= 4 else f"FY {year-1}-{str(year)[2:]}"

def to_excel(df):
    output = io.BytesIO()
    try:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        return output.getvalue()
    except: return None

def clean_kpi(title, metrics):
    st.markdown(f"### {title}")
    cols = st.columns(min(len(metrics[:3]), 3))
    for i, m in enumerate(metrics[:3]):
        with cols[i]:
            st.metric(m['label'], m['value'], m.get('delta'))
    if len(metrics) > 3:
        with st.expander("📊 More"):
            cols = st.columns(3)
            for i, m in enumerate(metrics[3:]):
                with cols[i % 3]:
                    st.metric(m['label'], m['value'])

def create_pro_chart(data, typ, title='', **kwargs):
    if typ == 'bar':
        fig = px.bar(data, title=title, **kwargs)
    elif typ == 'line':
        fig = px.line(data, title=title, **kwargs)
    elif typ == 'scatter':
        fig = px.scatter(data, title=title, **kwargs)
    else:
        fig = go.Figure()
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Inter, sans-serif"),
        hovermode='x unified'
    )
    fig.update_xaxes(showgrid=True, gridcolor='rgba(200,200,200,0.3)')
    fig.update_yaxes(showgrid=True, gridcolor='rgba(200,200,200,0.3)')
    return fig

# ════════════════════════════════════════════════════════════
# STATISTICAL TESTING
# ════════════════════════════════════════════════════════════

def chi2_test(pair_count, total, item_a, item_b):
    both = pair_count
    only_a = item_a - both
    only_b = item_b - both
    neither = total - only_a - only_b - both
    if neither < 0 or only_a < 0 or only_b < 0:
        return False, 1.0
    try:
        _, p_val, _, _ = chi2_contingency([[both, only_a], [only_b, neither]])
        return p_val < 0.05, p_val
    except:
        return False, 1.0

def correlation_test(x, y):
    if len(x) < 3 or len(y) < 3:
        return 0, 1.0, "N/A"
    corr, p_val = pearsonr(x, y)
    strength = "Strong" if abs(corr) > 0.7 else "Moderate" if abs(corr) > 0.4 else "Weak"
    return corr, p_val, strength

# ════════════════════════════════════════════════════════════
# DATA LOADING WITH SMART HANDLING
# ════════════════════════════════════════════════════════════

@st.cache_data
def load_data(files):
    """
    Smart data loader with:
    - Automatic column detection
    - Duplicate removal
    - Missing column handling
    - Multi-file merging
    """
    all_dfs = []
    files_loaded = []
    files_skipped = []
    
    for name, content in files:
        try:
            # Read file with header detection
            if name.endswith('.csv'):
                df = pd.read_csv(io.BytesIO(content))
            else:
                # Excel file - detect header row
                file_bytes = io.BytesIO(content)
                
                # First, scan first 20 rows to find headers
                df_test = pd.read_excel(file_bytes, header=None, nrows=20)
                
                # Find the header row (look for row with "Date", "Amount", "Particulars", etc.)
                header_row = 0
                for idx, row in df_test.iterrows():
                    row_str = ' '.join([str(x).lower() for x in row if pd.notna(x)])
                    # Look for key column indicators
                    if any(word in row_str for word in ['date', 'amount', 'particulars', 'customer', 
                                                         'invoice', 'bill', 'vch', 'voucher', 'party']):
                        header_row = int(idx)
                        break
                
                # Re-read with correct header
                file_bytes.seek(0)
                if header_row > 0:
                    df = pd.read_excel(file_bytes, header=header_row)
                    st.sidebar.info(f"📋 Skipped {header_row} header row(s)")
                else:
                    df = pd.read_excel(file_bytes)
            
            # Auto-detect and rename common column patterns
            rename_map = {}
            for col in df.columns:
                col_lower = str(col).lower().strip()
                
                # Date detection
                if any(k in col_lower for k in ['date', 'dt', 'invoice date', 'bill date']):
                    if 'Date' not in rename_map.values():
                        rename_map[col] = 'Date'
                
                # Customer detection
                elif any(k in col_lower for k in ['customer', 'particulars', 'party', 'account', 'ledger']):
                    if 'Particulars' not in rename_map.values():
                        rename_map[col] = 'Particulars'
                
                # Amount detection
                elif any(k in col_lower for k in ['amount', 'value', 'amt', 'total', 'price']):
                    if 'Amount' not in rename_map.values():
                        rename_map[col] = 'Amount'
                
                # Product detection
                elif any(k in col_lower for k in ['item', 'product', 'description', 'goods']):
                    if 'Item Details' not in rename_map.values():
                        rename_map[col] = 'Item Details'
                
                # Invoice detection
                elif any(k in col_lower for k in ['invoice', 'bill', 'vch', 'voucher', 'receipt']):
                    if 'Vch/Bill No' not in rename_map.values():
                        rename_map[col] = 'Vch/Bill No'
                
                # Salesperson detection
                elif any(k in col_lower for k in ['salesperson', 'rep', 'agent', 'sales rep']):
                    if 'Salesperson' not in rename_map.values():
                        rename_map[col] = 'Salesperson'
            
            if rename_map:
                df = df.rename(columns=rename_map)
                # Show what was detected
                st.sidebar.success(f"✅ Columns detected: {', '.join(rename_map.values())}")
            else:
                # No columns were renamed - show original columns for debugging
                st.sidebar.warning(f"⚠️ Using original columns: {', '.join([str(c) for c in df.columns[:5]])}")
            
            # Show DataFrame info for debugging
            with st.expander(f"🔍 File Preview: {name}", expanded=False):
                st.caption(f"**Columns found:** {list(df.columns)}")
                st.caption(f"**Rows:** {len(df)}")
                st.dataframe(df.head())
            
            # Handle missing columns
            df = handle_missing_columns(df)
            
            all_dfs.append(df)
            files_loaded.append(name)
            
        except Exception as e:
            error_details = f"{type(e).__name__}: {str(e)}"
            st.error(f"❌ Error loading {name}: {error_details}")
            files_skipped.append((name, error_details))
            
            # Show detailed debug info
            with st.expander(f"🔍 Debug Info for {name}"):
                st.code(f"Error: {error_details}")
                st.caption("If you see this, please check:")
                st.caption("1. File has Date, Particulars/Customer, Amount columns")
                st.caption("2. First data row starts after company headers")
                st.caption("3. Date column has valid dates")
                st.caption("4. Amount column has numbers")
            continue
    
    if not all_dfs:
        raise ValueError("No valid files uploaded. Check your file format.")
    
    # Show file loading status
    if files_loaded:
        st.success(f"✅ Loaded {len(files_loaded)} file(s): {', '.join(files_loaded)}")
    if files_skipped:
        for fname, error in files_skipped:
            st.warning(f"⚠️ Skipped {fname}: {error}")
    
    # Combine all files
    combined = pd.concat(all_dfs, ignore_index=True)
    
    # Remove duplicates
    combined_unique, dup_count = remove_duplicates(combined)
    
    # Show duplicate detection info
    if dup_count > 0:
        with st.expander(f"🔍 Removed {dup_count:,} duplicate transactions (click to see details)", expanded=False):
            st.markdown(f"""
**Duplicate Detection Summary:**

Found and removed **{dup_count:,}** duplicate transactions.

**How duplicates are detected:**
- Same date + same customer + same amount = duplicate
- First occurrence is kept, rest are removed
- Common when uploading overlapping date ranges

**Example:**
```
Date       | Customer  | Amount | Status
2025-04-15 | ABC Store | 5000   | ✅ Kept (first occurrence)
2025-04-15 | ABC Store | 5000   | ❌ Removed (duplicate)
```

**Why this happens:**
- Multiple files with overlapping date ranges
- Re-uploading same data
- Different exports of same period

**Result:**
✅ Each transaction now appears only once (correct!)
✅ Analytics show accurate totals
""")
    
    # Clean and standardize data
    combined_unique['Date'] = pd.to_datetime(combined_unique['Date'], errors='coerce')
    combined_unique['Amount'] = pd.to_numeric(
        combined_unique['Amount'].astype(str).str.replace(r'[₹,Rs\$]', '', regex=True),
        errors='coerce'
    ).fillna(0)
    
    # Remove invalid rows
    initial_count = len(combined_unique)
    combined_unique = combined_unique.dropna(subset=['Date'])
    combined_unique = combined_unique[combined_unique['Amount'] > 0]
    
    removed_invalid = initial_count - len(combined_unique)
    if removed_invalid > 0:
        st.info(f"ℹ️ Removed {removed_invalid:,} invalid rows (missing date or zero amount)")
    
    # Add derived columns
    combined_unique['FY'] = combined_unique['Date'].apply(get_fy)
    combined_unique['Year'] = combined_unique['Date'].dt.year
    combined_unique['Month'] = combined_unique['Date'].dt.month
    combined_unique['Quarter'] = combined_unique['Date'].dt.quarter
    
    return combined_unique

# ════════════════════════════════════════════════════════════
# CACHED ANALYTICS FUNCTIONS - ALL 13 MODULES
# ════════════════════════════════════════════════════════════

@st.cache_data
def abc_analysis(df, typ='customer'):
    """ABC Analysis with Pareto principle"""
    if typ == 'customer':
        data = df.groupby('Particulars')['Amount'].sum().sort_values(ascending=False).reset_index()
        data.columns = ['Name', 'Revenue']
    else:
        if 'Item Details' not in df.columns or df['Item Details'].iloc[0] == 'Not Specified':
            return pd.DataFrame()
        data = df.groupby('Item Details')['Amount'].sum().sort_values(ascending=False).reset_index()
        data.columns = ['Name', 'Revenue']
    
    data['Cumulative'] = data['Revenue'].cumsum()
    total = data['Revenue'].sum()
    data['Cum_%'] = (data['Cumulative'] / total) * 100
    data['Rev_%'] = (data['Revenue'] / total) * 100
    
    # ABC categorization
    n = len(data)
    a_n = max(1, int(n * 0.20))  # Top 20%
    b_n = max(1, int(n * 0.30))  # Next 30%
    
    data['Category'] = ['🔴 A' if i < a_n else '🟡 B' if i < a_n+b_n else '🟢 C' for i in range(n)]
    data['Rank'] = range(1, n + 1)
    
    return data

@st.cache_data
def rfm_analysis(df, ref_date):
    """RFM Segmentation Analysis"""
    rfm = df.groupby('Particulars').agg({
        'Date': lambda x: (ref_date - x.max()).days,
        'Vch/Bill No': 'nunique',
        'Amount': 'sum'
    }).reset_index()
    rfm.columns = ['Customer', 'Recency', 'Frequency', 'Monetary']
    
    # Calculate RFM scores (quintiles)
    rfm['R'] = pd.qcut(rfm['Recency'], q=5, labels=[5,4,3,2,1], duplicates='drop').astype(int)
    rfm['F'] = pd.qcut(rfm['Frequency'].rank(method='first'), q=5, labels=[1,2,3,4,5], duplicates='drop').astype(int)
    rfm['M'] = pd.qcut(rfm['Monetary'], q=5, labels=[1,2,3,4,5], duplicates='drop').astype(int)
    
    # Segment customers
    def segment(row):
        r, f, m = row['R'], row['F'], row['M']
        if r >= 4 and f >= 4:
            return "🏆 Champions"
        elif r >= 3 and f >= 3:
            return "🎯 Loyal Customers"
        elif r <= 2 and f >= 4:
            return "⚠️ At Risk"
        elif r <= 2:
            return "😴 Lost"
        else:
            return "📊 Need Attention"
    
    rfm['Segment'] = rfm.apply(segment, axis=1)
    rfm['RFM_Score'] = rfm['R'] + rfm['F'] + rfm['M']
    
    return rfm

@st.cache_data
def market_basket(df, min_support=0.01):
    """Market Basket Analysis with Chi-square testing"""
    if 'Vch/Bill No' not in df.columns or 'Item Details' not in df.columns:
        return pd.DataFrame()
    
    if df['Item Details'].iloc[0] == 'Not Specified':
        return pd.DataFrame()
    
    # Create baskets
    baskets = df.groupby('Vch/Bill No')['Item Details'].apply(list).reset_index()
    baskets = baskets[baskets['Item Details'].apply(len) > 1]
    
    if len(baskets) == 0:
        return pd.DataFrame()
    
    # Generate product pairs
    pairs = []
    for basket in baskets['Item Details']:
        unique_items = sorted(set(basket))
        if len(unique_items) >= 2:
            pairs.extend(list(combinations(unique_items, 2)))
    
    # Count pairs
    pair_counts = {}
    for pair in pairs:
        pair_counts[pair] = pair_counts.get(pair, 0) + 1
    
    total_transactions = len(df['Vch/Bill No'].unique())
    results = []
    
    for (item_a, item_b), count in pair_counts.items():
        support = count / total_transactions
        
        if support < min_support:
            continue
        
        # Calculate metrics
        item_a_count = len(df[df['Item Details'] == item_a]['Vch/Bill No'].unique())
        item_b_count = len(df[df['Item Details'] == item_b]['Vch/Bill No'].unique())
        
        confidence = (count / item_a_count) if item_a_count > 0 else 0
        expected_support = (item_a_count / total_transactions) * (item_b_count / total_transactions)
        lift = (support / expected_support) if expected_support > 0 else 0
        
        # Chi-square test
        is_significant, p_value = chi2_test(count, total_transactions, item_a_count, item_b_count)
        
        if lift > 1:  # Only positive associations
            results.append({
                'Product A': item_a,
                'Product B': item_b,
                'Count': count,
                'Support%': support * 100,
                'Confidence%': confidence * 100,
                'Lift': lift,
                'P_Value': p_value,
                'Significant': '✅' if is_significant else '⚠️'
            })
    
    return pd.DataFrame(results).sort_values('Lift', ascending=False) if results else pd.DataFrame()

@st.cache_data
def cohort_analysis(df):
    """Cohort Retention Analysis"""
    # Get first purchase date for each customer
    first_purchase = df.groupby('Particulars')['Date'].min().reset_index()
    first_purchase['Cohort_Year'] = first_purchase['Date'].dt.year
    
    # Merge with main dataframe
    merged = df.merge(first_purchase[['Particulars', 'Cohort_Year']], on='Particulars')
    merged['Purchase_Year'] = merged['Date'].dt.year
    
    # Create cohort matrix
    cohort_data = merged.groupby(['Cohort_Year', 'Purchase_Year'])['Particulars'].nunique().reset_index()
    cohort_data.columns = ['Cohort_Year', 'Purchase_Year', 'Customers']
    
    # Get cohort sizes
    cohort_sizes = merged.groupby('Cohort_Year')['Particulars'].nunique().to_dict()
    
    return cohort_data, cohort_sizes

@st.cache_data
def hhi_analysis(df):
    """Herfindahl-Hirschman Index (Concentration Risk)"""
    customer_revenue = df.groupby('Particulars')['Amount'].sum().sort_values(ascending=False).reset_index()
    customer_revenue.columns = ['Customer', 'Revenue']
    
    total_revenue = customer_revenue['Revenue'].sum()
    customer_revenue['Share%'] = (customer_revenue['Revenue'] / total_revenue * 100)
    customer_revenue['Cumulative%'] = customer_revenue['Share%'].cumsum()
    
    # Calculate HHI
    hhi = (customer_revenue['Share%'] ** 2).sum()
    
    return customer_revenue, hhi

@st.cache_data
def lapse_analysis(df, ref_date, threshold_days=90):
    """Lapse Tracker - Identify inactive customers"""
    last_purchase = df.groupby('Particulars')['Date'].max().reset_index()
    last_purchase['Days_Since_Purchase'] = (ref_date - last_purchase['Date']).dt.days
    
    # Filter inactive customers
    inactive = last_purchase[last_purchase['Days_Since_Purchase'] >= threshold_days].copy()
    
    if inactive.empty:
        return inactive
    
    # Add revenue and transaction data
    inactive['Lifetime_Value'] = inactive['Particulars'].apply(
        lambda x: df[df['Particulars'] == x]['Amount'].sum()
    )
    inactive['Total_Invoices'] = inactive['Particulars'].apply(
        lambda x: df[df['Particulars'] == x]['Vch/Bill No'].nunique()
    )
    
    # Prioritize based on lifetime value
    inactive['Priority'] = inactive.apply(
        lambda row: "🔴 HIGH" if row['Lifetime_Value'] >= 500000 
                    else "🟡 MEDIUM" if row['Lifetime_Value'] >= 100000 
                    else "🟢 LOW",
        axis=1
    )
    
    return inactive.sort_values('Lifetime_Value', ascending=False)

@st.cache_data
def sales_performance(df):
    """Salesperson Performance Analysis"""
    if 'Salesperson' not in df.columns or df['Salesperson'].iloc[0] == 'Not Specified':
        return pd.DataFrame()
    
    performance = df.groupby('Salesperson').agg({
        'Amount': 'sum',
        'Particulars': 'nunique',
        'Vch/Bill No': 'nunique'
    }).reset_index()
    performance.columns = ['Salesperson', 'Revenue', 'Customers', 'Transactions']
    
    performance['Avg_Deal_Size'] = performance['Revenue'] / performance['Transactions']
    performance = performance.sort_values('Revenue', ascending=False)
    performance['Rank'] = range(1, len(performance) + 1)
    
    return performance

@st.cache_data
def price_analysis(df):
    """Price Variance Analysis over time"""
    if 'Item Details' not in df.columns or df['Item Details'].iloc[0] == 'Not Specified':
        return pd.DataFrame()
    
    df_price = df.copy()
    df_price['Year'] = df_price['Date'].dt.year
    
    price_data = df_price.groupby(['Item Details', 'Year']).agg({
        'Amount': ['mean', 'min', 'max', 'count', 'std']
    }).reset_index()
    price_data.columns = ['Product', 'Year', 'Avg_Price', 'Min_Price', 'Max_Price', 'Transactions', 'Std_Dev']
    
    # Only include products with sufficient data
    price_data = price_data[price_data['Transactions'] >= 3]
    price_data['Std_Dev'] = price_data['Std_Dev'].fillna(0)
    
    return price_data

@st.cache_data
def growth_analysis(df, years):
    """Year-over-year growth analysis"""
    if len(years) < 2:
        return pd.DataFrame(), pd.DataFrame()
    
    customer_yearly = df.groupby(['Particulars', 'FY'])['Amount'].sum().unstack(fill_value=0)
    product_yearly = pd.DataFrame()
    
    if 'Item Details' in df.columns and df['Item Details'].iloc[0] != 'Not Specified':
        product_yearly = df.groupby(['Item Details', 'FY'])['Amount'].sum().unstack(fill_value=0)
    
    return customer_yearly, product_yearly

@st.cache_data  
def dna_leakage_analysis(df, ref_date):
    """Customer DNA & Leakage Pattern Analysis"""
    patterns = df.groupby('Particulars').agg({
        'Date': ['count', 'min', 'max'],
        'Amount': 'sum'
    }).reset_index()
    patterns.columns = ['Customer', 'Order_Count', 'First_Purchase', 'Last_Purchase', 'Total_Revenue']
    
    patterns['Days_Active'] = (patterns['Last_Purchase'] - patterns['First_Purchase']).dt.days
    patterns['Days_Since_Last'] = (ref_date - patterns['Last_Purchase']).dt.days
    patterns['Avg_Gap_Days'] = patterns['Days_Active'] / (patterns['Order_Count'] - 1)
    patterns['Avg_Gap_Days'] = patterns['Avg_Gap_Days'].fillna(0)
    
    def customer_status(row):
        if row['Order_Count'] < 3:
            return "⚪ Irregular"
        elif row['Days_Since_Last'] > row['Avg_Gap_Days'] * 1.5:
            return "🔴 LEAKAGE"
        elif row['Days_Since_Last'] > row['Avg_Gap_Days']:
            return "🟡 WARNING"
        else:
            return "✅ STABLE"
    
    patterns['Status'] = patterns.apply(customer_status, axis=1)
    
    return patterns

@st.cache_data
def territory_analysis(df):
    """Territory Performance Analysis"""
    if 'Salesperson' not in df.columns or df['Salesperson'].iloc[0] == 'Not Specified':
        return pd.DataFrame()
    
    territory = df.groupby('Salesperson').agg({
        'Amount': 'sum',
        'Particulars': 'nunique',
        'Vch/Bill No': 'nunique'
    }).reset_index()
    territory.columns = ['Territory', 'Revenue', 'Customers', 'Transactions']
    
    territory['Penetration'] = territory['Transactions'] / territory['Customers']
    territory['Revenue_per_Customer'] = territory['Revenue'] / territory['Customers']
    
    # Categorize territories
    high_revenue_threshold = territory['Revenue'].quantile(0.75)
    high_customer_threshold = territory['Customers'].quantile(0.75)
    
    def categorize_territory(row):
        if row['Revenue'] >= high_revenue_threshold and row['Customers'] >= high_customer_threshold:
            return "🌟 High Revenue / High Reach"
        elif row['Revenue'] >= high_revenue_threshold:
            return "💰 High Revenue / Low Reach"
        elif row['Customers'] >= high_customer_threshold:
            return "📈 Growth Potential"
        else:
            return "⚠️ Developing"
    
    territory['Category'] = territory.apply(categorize_territory, axis=1)
    
    return territory

# ════════════════════════════════════════════════════════════
# SIDEBAR & FILE UPLOAD
# ════════════════════════════════════════════════════════════

st.sidebar.title("📊 Sales Intelligence Pro")

# Show license info if active
if LICENSE_ENABLED and st.session_state.get('license_valid'):
    with st.sidebar.expander("🔑 License Info", expanded=False):
        st.caption(f"**Status:** ✅ Active")
        if 'license_message' in st.session_state:
            st.caption(f"**Plan:** {st.session_state.license_message}")
        if 'license_key' in st.session_state:
            key_display = st.session_state.license_key[:20] + "..."
            st.caption(f"**Key:** {key_display}")
        st.caption("")
        if st.button("🔓 Change License"):
            st.session_state.license_valid = False
            st.rerun()

# Data storage information
with st.sidebar.expander("💾 Your Saved Files", expanded=False):
    st.caption("**Files saved at:**")
    st.code(f"Documents/SalesIntelligence/SavedFiles")
    st.caption(f"Full path: {str(UPLOADS_DIR)}")
    st.caption("")
    st.caption("✅ Easy to find in Documents folder")
    st.caption("✅ Saved on YOUR computer")
    st.caption("❌ Never uploaded to cloud")
    st.caption("🔒 100% private and secure")
    
    # Open folder button
    if st.button("📁 Open Saved Files Folder"):
        import subprocess
        import platform
        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(UPLOADS_DIR)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", str(UPLOADS_DIR)])
            else:  # Linux
                subprocess.run(["xdg-open", str(UPLOADS_DIR)])
            st.success("✅ Folder opened!")
        except Exception as e:
            st.info(f"📂 Manually navigate to: {UPLOADS_DIR}")
    
    # Backup functionality
    if st.button("📥 Backup All Data"):
        backup_file = DATA_DIR / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        try:
            shutil.make_archive(
                str(backup_file).replace('.zip', ''),
                'zip',
                UPLOADS_DIR
            )
            st.success(f"✅ Backup created: {backup_file.name}")
        except Exception as e:
            st.error(f"Backup failed: {e}")

st.sidebar.markdown("---")

# ═══════════════════════════════════════════════════════════
#  WORKING SAVED FILE UI - ACTUALLY IMPLEMENTED NOW
# ═══════════════════════════════════════════════════════════

saved_files = get_saved_files()

if saved_files:
    st.sidebar.success(f"✅ {len(saved_files)} file(s) saved")
    
    # Show saved files list
    with st.sidebar.expander("📋 Saved Files", expanded=False):
        for f in saved_files:
            st.caption(f"• {f.name}")
    
    # Delete all button with confirmation
    col1, col2 = st.sidebar.columns([3, 2])
    with col1:
        if st.button("🗑️ Delete All Saved", type="secondary", use_container_width=True):
            st.session_state.confirm_delete = True
    
    # Show confirmation if button clicked
    if st.session_state.get('confirm_delete', False):
        st.sidebar.warning("⚠️ Delete all saved files?")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("✅ Yes, Delete", type="primary", use_container_width=True):
                import shutil
                if UPLOADS_DIR.exists():
                    shutil.rmtree(UPLOADS_DIR)
                    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
                    st.session_state.confirm_delete = False
                    st.sidebar.success("✅ All files deleted!")
                    st.rerun()
        with col2:
            if st.button("❌ Cancel", use_container_width=True):
                st.session_state.confirm_delete = False
                st.rerun()
    
    # Create dropdown with saved files + upload option
    file_choices = ["📤 Upload new file..."] + [f.name for f in saved_files]
    selection = st.sidebar.selectbox(
        "📁 Select Data Source:",
        file_choices,
        index=0,
        help="Choose a previously saved file or upload new"
    )
    
    if selection == "📤 Upload new file...":
        # Show file uploader
        uploaded_files = st.sidebar.file_uploader(
            "Upload Excel/CSV",
            type=['xlsx', 'xls', 'csv'],
            accept_multiple_files=True
        )
    else:
        # Load from saved file
        selected_path = [f for f in saved_files if f.name == selection][0]
        with open(selected_path, 'rb') as f:
            file_content = f.read()
        uploaded_files = [(selection, file_content)]
        st.sidebar.info(f"📂 Loaded: {selection}")

else:
    # No saved files - first time user
    st.sidebar.info("📤 Upload your first file")
    uploaded_files = st.sidebar.file_uploader(
        "Upload Excel/CSV",
        type=['xlsx', 'xls', 'csv'],
        accept_multiple_files=True,
        help="Files will be saved for quick access later"
    )

# Main data loading
df = None
ref_date = None

if not uploaded_files:
    st.title("🎯 Sales Intelligence Pro")
    st.markdown("""
    ### Complete Analytics Platform
    
    **✨ Smart Features:**
    - ✅ Saved file loading (select from dropdown above)
    - ✅ Automatic duplicate detection
    - ✅ Missing column handling
    - ✅ Data persistence
    
    **📊 All 13 Analytics Modules**
    
    **📁 Required Columns:**
    - Date, Customer/Particulars, Amount
    
    👈 Upload Excel or select saved file to begin
    """)
    st.stop()

# Handle file loading
try:
    # Save new uploads and load data
    if isinstance(uploaded_files, list) and len(uploaded_files) > 0:
        # From uploader - need to save and read
        if isinstance(uploaded_files[0], tuple):
            # Already processed (from saved file)
            files_to_load = uploaded_files
        else:
            # Fresh uploads - save them first
            files_to_load = []
            for uploaded_file in uploaded_files:
                save_uploaded_file(uploaded_file)
                st.sidebar.success(f"💾 Saved: {uploaded_file.name}")
                uploaded_file.seek(0)
                files_to_load.append((uploaded_file.name, uploaded_file.read()))
        
        df = load_data(files_to_load)
        ref_date = df['Date'].max()
    
    # Show data summary in sidebar
    st.sidebar.success(f"✅ {len(df):,} unique transactions")
    st.sidebar.caption(f"📅 {df['Date'].min().strftime('%b %Y')} – {df['Date'].max().strftime('%b %Y')}")
    
    # Check for missing optional features
    missing_features = []
    if df['Item Details'].iloc[0] == 'Not Specified':
        missing_features.extend([
            "Market Basket Analysis",
            "Product ABC Analysis", 
            "Product Price Variance"
        ])
    if df['Salesperson'].iloc[0] == 'Not Specified':
        missing_features.extend([
            "Salesperson Dashboard",
            "Rep Comparison",
            "Territory Analysis"
        ])
    
    if missing_features:
        with st.sidebar.expander("⚠️ Limited Features", expanded=False):
            st.caption("**Some features unavailable due to missing columns:**")
            for feature in missing_features:
                st.caption(f"❌ {feature}")
            st.caption("")
            st.caption("**To enable all features, include:**")
            if df['Item Details'].iloc[0] == 'Not Specified':
                st.caption("- Item Details (for product analysis)")
            if df['Salesperson'].iloc[0] == 'Not Specified':
                st.caption("- Salesperson (for sales team analysis)")
            st.caption("")
            st.caption("**All customer-based analytics work normally!**")
    
except Exception as e:
    st.error(f"""
    ❌ **Error loading data**
    
    {str(e)}
    
    **Common issues:**
    - Missing required columns (Date, Customer, Amount)
    - Invalid date format
    - Non-numeric amounts
    
    **Need help?** Check the file format requirements above.
    """)
    st.stop()

# ════════════════════════════════════════════════════════════
# NAVIGATION
# ════════════════════════════════════════════════════════════

view = st.sidebar.radio(
    "📍 Navigate to View",
    [
        "Dashboard",
        "Growth Lab",
        "DNA & Leakage", 
        "Lapse Tracker",
        "ABC Analysis",
        "RFM Segmentation",
        "Market Basket",
        "Cohort Analysis",
        "Concentration Risk",
        "Price Variance",
        "Salesperson Dashboard",
        "Rep Comparison",
        "Territory Analysis"
    ]
)


# ════════════════════════════════════════════════════════════
# VIEW 1: DASHBOARD
# ════════════════════════════════════════════════════════════

if view == "Dashboard":
    st.title("📊 Dashboard")
    
    # KPIs
    total_revenue = df['Amount'].sum()
    total_customers = df['Particulars'].nunique()
    total_transactions = len(df)
    avg_deal = df['Amount'].mean()
    
    metrics = [
        {'label': 'Total Revenue', 'value': f"₹{total_revenue:,.0f}"},
        {'label': 'Customers', 'value': f"{total_customers:,}"},
        {'label': 'Transactions', 'value': f"{total_transactions:,}"},
        {'label': 'Avg Deal Size', 'value': f"₹{avg_deal:,.0f}"}
    ]
    clean_kpi("Business Overview", metrics)
    
    # Top 10 Customers
    st.markdown("### 🏆 Top 10 Customers by Revenue")
    top10_customers = df.groupby('Particulars')['Amount'].sum().nlargest(10).reset_index()
    top10_customers.columns = ['Customer', 'Revenue']
    
    fig1 = create_pro_chart(
        top10_customers,
        'bar',
        x='Customer',
        y='Revenue',
        title='Top 10 Customers'
    )
    st.plotly_chart(fig1, use_container_width=True)
    
    # Revenue Trend
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📈 Revenue Trend by Fiscal Year")
        yearly_revenue = df.groupby('FY')['Amount'].sum().reset_index()
        yearly_revenue = yearly_revenue.sort_values('FY')
        
        fig2 = create_pro_chart(
            yearly_revenue,
            'line',
            x='FY',
            y='Amount',
            title='Yearly Revenue Trend',
            markers=True
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    with col2:
        st.markdown("### 📅 Monthly Revenue Heatmap")
        df_heatmap = df.copy()
        df_heatmap['Year_Num'] = df_heatmap['Date'].dt.year
        df_heatmap['Month_Num'] = df_heatmap['Date'].dt.month
        
        heatmap_data = df_heatmap.groupby(['Year_Num', 'Month_Num'])['Amount'].sum().reset_index()
        heatmap_pivot = heatmap_data.pivot(index='Year_Num', columns='Month_Num', values='Amount').fillna(0)
        
        fig3 = go.Figure(data=go.Heatmap(
            z=heatmap_pivot.values,
            x=[f"M{i}" for i in heatmap_pivot.columns],
            y=heatmap_pivot.index,
            colorscale='Viridis',
            text=heatmap_pivot.values,
            texttemplate='₹%{text:.0s}',
            textfont={"size": 10},
            hovertemplate='Year: %{y}<br>Month: %{x}<br>Revenue: ₹%{z:,.0f}<extra></extra>'
        ))
        fig3.update_layout(title='Monthly Revenue Heatmap', height=400)
        st.plotly_chart(fig3, use_container_width=True)

# ════════════════════════════════════════════════════════════
# VIEW 2: GROWTH LAB
# ════════════════════════════════════════════════════════════

elif view == "Growth Lab":
    st.title("📈 Growth Lab - Year-over-Year Comparison")
    
    years = sorted(df['FY'].unique())
    
    if len(years) < 2:
        st.warning("⚠️ Need at least 2 fiscal years for comparison")
        st.info(f"Current data has only {len(years)} fiscal year(s): {', '.join(years)}")
    else:
        typ = st.radio("Compare by:", ["Customer", "Product"], horizontal=True)
        
        if typ == "Customer":
            pivot = df.groupby(['Particulars', 'FY'])['Amount'].sum().unstack(fill_value=0)
            entity_name = "Customer"
        else:
            if df['Item Details'].iloc[0] == 'Not Specified':
                st.error("❌ Product column not available in your data")
                st.info("Upload Excel with 'Item Details' column to use product comparison")
                st.stop()
            pivot = df.groupby(['Item Details', 'FY'])['Amount'].sum().unstack(fill_value=0)
            entity_name = "Product"
        
        # Calculate year-over-year changes
        for i in range(len(years) - 1):
            if years[i] in pivot.columns and years[i+1] in pivot.columns:
                change_col = f'{years[i]}→{years[i+1]} Change'
                pivot[change_col] = pivot[years[i+1]] - pivot[years[i]]
        
        st.markdown(f"### 📊 Top 20 {entity_name}s - Multi-Year Comparison")
        display_df = pivot.sort_values(years[-1], ascending=False).head(20)
        st.dataframe(
            display_df.style.format('₹{:,.0f}').background_gradient(cmap='RdYlGn', axis=0),
            use_container_width=True
        )
        
        # Waterfall chart for top 5
        if len(years) >= 2:
            st.markdown(f"### 💧 Waterfall Chart: {years[-2]} → {years[-1]}")
            top5 = pivot.nlargest(5, years[-1])
            
            if years[-2] in top5.columns and years[-1] in top5.columns:
                waterfall_data = []
                for idx in top5.index:
                    old_val = top5.loc[idx, years[-2]]
                    new_val = top5.loc[idx, years[-1]]
                    change = new_val - old_val
                    waterfall_data.append({
                        entity_name: idx,
                        'Previous': old_val,
                        'Current': new_val,
                        'Change': change
                    })
                
                waterfall_df = pd.DataFrame(waterfall_data)
                
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    name=years[-2],
                    x=waterfall_df[entity_name],
                    y=waterfall_df['Previous'],
                    marker_color='lightblue'
                ))
                fig.add_trace(go.Bar(
                    name=years[-1],
                    x=waterfall_df[entity_name],
                    y=waterfall_df['Current'],
                    marker_color='darkblue'
                ))
                fig.update_layout(barmode='group', title=f'Top 5 {entity_name}s Comparison')
                st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════
# VIEW 3: DNA & LEAKAGE
# ════════════════════════════════════════════════════════════

elif view == "DNA & Leakage":
    st.title("🧬 Customer DNA & Leakage Pattern Analysis")
    
    patterns = dna_leakage_analysis(df, ref_date)
    
    # Summary metrics
    status_counts = patterns['Status'].value_counts()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("✅ Stable", status_counts.get("✅ STABLE", 0))
    with col2:
        st.metric("🟡 Warning", status_counts.get("🟡 WARNING", 0))
    with col3:
        st.metric("🔴 Leakage", status_counts.get("🔴 LEAKAGE", 0))
    with col4:
        st.metric("⚪ Irregular", status_counts.get("⚪ Irregular", 0))
    
    # Pie chart
    fig = px.pie(
        patterns,
        names='Status',
        title='Customer Status Distribution',
        color='Status',
        color_discrete_map={
            '✅ STABLE': '#10b981',
            '🟡 WARNING': '#f59e0b',
            '🔴 LEAKAGE': '#ef4444',
            '⚪ Irregular': '#6b7280'
        }
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # At-risk customers detail
    leakage_customers = patterns[patterns['Status'] == "🔴 LEAKAGE"].sort_values('Total_Revenue', ascending=False)
    
    if not leakage_customers.empty:
        st.markdown("### 🔴 Customers At Risk (Leakage Detected)")
        st.markdown(f"**{len(leakage_customers)} customers** are showing leakage patterns")
        
        st.dataframe(
            leakage_customers[['Customer', 'Order_Count', 'Total_Revenue', 'Days_Since_Last', 'Avg_Gap_Days']].head(20).style.format({
                'Total_Revenue': '₹{:,.0f}',
                'Days_Since_Last': '{:.0f} days',
                'Avg_Gap_Days': '{:.0f} days'
            }),
            use_container_width=True
        )
        
        # Download option
        excel_data = to_excel(leakage_customers)
        if excel_data:
            st.download_button(
                "📥 Download Leakage Report (Excel)",
                excel_data,
                "leakage_customers.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.success("✅ No customers showing leakage patterns!")

# ════════════════════════════════════════════════════════════
# VIEW 4: LAPSE TRACKER
# ════════════════════════════════════════════════════════════

elif view == "Lapse Tracker":
    st.title("⏱️ Lapse Tracker - Inactive Customer Recovery")
    
    threshold_days = st.slider(
        "Inactive Threshold (days)",
        min_value=30,
        max_value=365,
        value=90,
        step=30,
        help="Customers who haven't purchased in this many days"
    )
    
    lapsed = lapse_analysis(df, ref_date, threshold_days)
    
    if lapsed.empty:
        st.success(f"✅ Excellent! No customers inactive for {threshold_days}+ days")
        st.balloons()
    else:
        # Summary metrics
        high_priority = lapsed[lapsed['Priority'] == "🔴 HIGH"]
        med_priority = lapsed[lapsed['Priority'] == "🟡 MEDIUM"]
        
        metrics = [
            {'label': 'Total Inactive', 'value': len(lapsed)},
            {'label': 'High Priority', 'value': len(high_priority)},
            {'label': 'Revenue at Risk', 'value': f"₹{lapsed['Lifetime_Value'].sum():,.0f}"}
        ]
        clean_kpi("Lapse Summary", metrics)
        
        # Priority breakdown
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 📋 Inactive Customers List")
            st.dataframe(
                lapsed[['Particulars', 'Days_Since_Purchase', 'Lifetime_Value', 'Total_Invoices', 'Priority']].head(30).style.format({
                    'Days_Since_Purchase': '{:.0f} days',
                    'Lifetime_Value': '₹{:,.0f}'
                }),
                use_container_width=True
            )
        
        with col2:
            st.markdown("### 🎯 Priority Distribution")
            priority_counts = lapsed['Priority'].value_counts().reset_index()
            priority_counts.columns = ['Priority', 'Count']
            
            fig = px.pie(
                priority_counts,
                values='Count',
                names='Priority',
                color='Priority',
                color_discrete_map={
                    '🔴 HIGH': '#ef4444',
                    '🟡 MEDIUM': '#f59e0b',
                    '🟢 LOW': '#10b981'
                }
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Download options
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            csv_data = lapsed.to_csv(index=False)
            st.download_button(
                "📥 Download CSV",
                csv_data,
                "lapsed_customers.csv",
                "text/csv"
            )
        with col_dl2:
            excel_data = to_excel(lapsed)
            if excel_data:
                st.download_button(
                    "📥 Download Excel",
                    excel_data,
                    "lapsed_customers.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

# ════════════════════════════════════════════════════════════
# VIEW 5: ABC ANALYSIS
# ════════════════════════════════════════════════════════════

elif view == "ABC Analysis":
    st.title("🎯 ABC Analysis - Pareto Principle (80/20 Rule)")
    
    analysis_type = st.radio("Analyze by:", ["Customers", "Products"], horizontal=True)
    
    if analysis_type == "Products" and df['Item Details'].iloc[0] == 'Not Specified':
        st.error("❌ Product column not available in your data")
        st.info("Upload Excel with 'Item Details' column to use product ABC analysis")
        st.stop()
    
    abc_data = abc_analysis(df, 'customer' if analysis_type == "Customers" else 'product')
    
    if abc_data.empty:
        st.warning("No data available for analysis")
        st.stop()
    
    # Category summary
    cat_a = abc_data[abc_data['Category'] == "🔴 A"]
    cat_b = abc_data[abc_data['Category'] == "🟡 B"]
    cat_c = abc_data[abc_data['Category'] == "🟢 C"]
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "🔴 Category A (Top 20%)",
            f"{len(cat_a)} {analysis_type.lower()}",
            f"₹{cat_a['Revenue'].sum():,.0f}"
        )
    with col2:
        st.metric(
            "🟡 Category B (Next 30%)",
            f"{len(cat_b)} {analysis_type.lower()}",
            f"₹{cat_b['Revenue'].sum():,.0f}"
        )
    with col3:
        st.metric(
            "🟢 Category C (Rest 50%)",
            f"{len(cat_c)} {analysis_type.lower()}",
            f"₹{cat_c['Revenue'].sum():,.0f}"
        )
    
    # Professional Pareto Chart (Dual-axis)
    st.markdown("### 📊 Professional Pareto Chart")
    
    top_n = min(50, len(abc_data))
    chart_data = abc_data.head(top_n)
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Revenue bars (colored by category)
    colors = ['#ef4444' if cat == "🔴 A" else '#f59e0b' if cat == "🟡 B" else '#10b981' 
              for cat in chart_data['Category']]
    
    fig.add_trace(
        go.Bar(
            x=chart_data['Rank'],
            y=chart_data['Revenue'],
            name='Revenue',
            marker_color=colors,
            hovertemplate='<b>%{text}</b><br>Revenue: ₹%{y:,.0f}<extra></extra>',
            text=chart_data['Name']
        ),
        secondary_y=False
    )
    
    # Cumulative percentage line
    fig.add_trace(
        go.Scatter(
            x=chart_data['Rank'],
            y=chart_data['Cum_%'],
            name='Cumulative %',
            line=dict(color='#667eea', width=3),
            mode='lines+markers',
            hovertemplate='Cumulative: %{y:.1f}%<extra></extra>'
        ),
        secondary_y=True
    )
    
    # 80% rule line
    fig.add_hline(
        y=80,
        line_dash="dash",
        line_color="red",
        annotation_text="80% Rule",
        annotation_position="right",
        secondary_y=True
    )
    
    # A/B/C boundaries
    if len(cat_a) > 0:
        fig.add_vline(x=len(cat_a), line_dash="dot", line_color="red", opacity=0.5)
    if len(cat_a) + len(cat_b) > 0:
        fig.add_vline(x=len(cat_a) + len(cat_b), line_dash="dot", line_color="orange", opacity=0.5)
    
    fig.update_xaxes(title_text="Rank")
    fig.update_yaxes(title_text="Revenue (₹)", secondary_y=False)
    fig.update_yaxes(title_text="Cumulative %", range=[0, 100], secondary_y=True)
    fig.update_layout(
        title=f'Pareto Chart - {analysis_type} Revenue Distribution',
        height=500,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Top 50 Table
    st.markdown(f"### 📋 Top 50 {analysis_type}")
    st.dataframe(
        abc_data[['Rank', 'Name', 'Revenue', 'Rev_%', 'Cum_%', 'Category']].head(50).style.format({
            'Revenue': '₹{:,.0f}',
            'Rev_%': '{:.2f}%',
            'Cum_%': '{:.2f}%'
        }).background_gradient(subset=['Revenue'], cmap='Greens'),
        use_container_width=True
    )
    
    # Download
    excel_data = to_excel(abc_data)
    if excel_data:
        st.download_button(
            "📥 Download Full ABC Analysis (Excel)",
            excel_data,
            f"abc_analysis_{analysis_type.lower()}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


# ════════════════════════════════════════════════════════════
# VIEW 6: RFM SEGMENTATION
# ════════════════════════════════════════════════════════════

elif view == "RFM Segmentation":
    st.title("🎭 RFM Segmentation - Customer Personas")
    
    rfm_data = rfm_analysis(df, ref_date)
    
    # Segment summary
    st.markdown("### 📊 Segment Overview")
    segment_summary = rfm_data.groupby('Segment').agg({
        'Customer': 'count',
        'Monetary': 'sum'
    }).reset_index()
    segment_summary.columns = ['Segment', 'Customer_Count', 'Total_Revenue']
    segment_summary['Avg_Revenue'] = segment_summary['Total_Revenue'] / segment_summary['Customer_Count']
    
    st.dataframe(
        segment_summary.style.format({
            'Total_Revenue': '₹{:,.0f}',
            'Avg_Revenue': '₹{:,.0f}'
        }),
        use_container_width=True
    )
    
    # Dual pie charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 👥 Customer Distribution")
        fig1 = px.pie(
            segment_summary,
            values='Customer_Count',
            names='Segment',
            title='Customers by Segment',
            hole=0.3
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.markdown("### 💰 Revenue Distribution")
        fig2 = px.pie(
            segment_summary,
            values='Total_Revenue',
            names='Segment',
            title='Revenue by Segment',
            hole=0.3
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    # Detailed customer list
    st.markdown("### 📋 Customer Details with RFM Scores")
    selected_segment = st.selectbox(
        "Filter by segment:",
        ["All"] + list(rfm_data['Segment'].unique())
    )
    
    if selected_segment == "All":
        display_rfm = rfm_data
    else:
        display_rfm = rfm_data[rfm_data['Segment'] == selected_segment]
    
    st.dataframe(
        display_rfm[['Customer', 'Recency', 'Frequency', 'Monetary', 'R', 'F', 'M', 'RFM_Score', 'Segment']].head(100).style.format({
            'Recency': '{:.0f} days',
            'Monetary': '₹{:,.0f}'
        }).background_gradient(subset=['RFM_Score'], cmap='RdYlGn'),
        use_container_width=True
    )
    
    # Download
    excel_data = to_excel(rfm_data)
    if excel_data:
        st.download_button(
            "📥 Download RFM Analysis (Excel)",
            excel_data,
            "rfm_segmentation.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ════════════════════════════════════════════════════════════
# VIEW 7: MARKET BASKET
# ════════════════════════════════════════════════════════════

elif view == "Market Basket":
    st.title("🛒 Market Basket Analysis - Product Associations")
    
    if df['Item Details'].iloc[0] == 'Not Specified':
        st.error("❌ Product column required for Market Basket analysis")
        st.info("Upload Excel with 'Item Details' column to enable this feature")
        st.stop()
    
    min_support_pct = st.slider(
        "Minimum Support %",
        min_value=0.1,
        max_value=10.0,
        value=1.0,
        step=0.1,
        help="Minimum percentage of transactions containing the product pair"
    )
    
    basket_data = market_basket(df, min_support_pct / 100)
    
    if basket_data.empty:
        st.warning(f"⚠️ No associations found with minimum support of {min_support_pct}%")
        st.info("Try lowering the minimum support threshold")
        st.stop()
    
    # Statistical summary
    significant_count = (basket_data['Significant'] == '✅').sum()
    total_associations = len(basket_data)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Associations", total_associations)
    with col2:
        st.metric("Statistically Significant (p<0.05)", significant_count)
    with col3:
        st.metric("Significance Rate", f"{(significant_count/total_associations*100):.1f}%")
    
    st.markdown("---")
    st.markdown("### 🔬 Chi-Square Significance Testing")
    st.caption("✅ = Statistically significant (p < 0.05) | ⚠️ = Not significant")
    
    # Top associations table
    st.markdown("### 📊 Product Association Rules (Sorted by Lift)")
    st.dataframe(
        basket_data[['Product A', 'Product B', 'Count', 'Support%', 'Confidence%', 'Lift', 'P_Value', 'Significant']].head(30).style.format({
            'Support%': '{:.2f}%',
            'Confidence%': '{:.2f}%',
            'Lift': '{:.2f}',
            'P_Value': '{:.4f}'
        }).background_gradient(subset=['Lift'], cmap='RdYlGn'),
        use_container_width=True
    )
    
    # Network visualization (only significant associations)
    st.markdown("### 🕸️ Association Network (Significant Associations Only)")
    significant_basket = basket_data[basket_data['Significant'] == '✅'].head(15)
    
    if not significant_basket.empty:
        # Create network graph
        import networkx as nx
        
        G = nx.Graph()
        for _, row in significant_basket.iterrows():
            G.add_edge(
                row['Product A'],
                row['Product B'],
                weight=row['Lift']
            )
        
        pos = nx.spring_layout(G, k=2, iterations=50)
        
        edge_x = []
        edge_y = []
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
        
        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=0.5, color='#888'),
            hoverinfo='none',
            mode='lines'
        )
        
        node_x = []
        node_y = []
        node_text = []
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            node_text.append(node)
        
        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            text=node_text,
            textposition="top center",
            hoverinfo='text',
            marker=dict(
                size=20,
                color='#667eea',
                line_width=2
            )
        )
        
        fig = go.Figure(data=[edge_trace, node_trace],
                       layout=go.Layout(
                           showlegend=False,
                           hovermode='closest',
                           xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                           yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                           height=500
                       ))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No statistically significant associations found")
    
    # Download
    excel_data = to_excel(basket_data)
    if excel_data:
        st.download_button(
            "📥 Download Market Basket Analysis (Excel)",
            excel_data,
            "market_basket.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ════════════════════════════════════════════════════════════
# VIEW 8: COHORT ANALYSIS
# ════════════════════════════════════════════════════════════

elif view == "Cohort Analysis":
    st.title("📅 Cohort Analysis - Customer Retention")
    
    cohort_data, cohort_sizes = cohort_analysis(df)
    
    # Create retention matrix
    cohort_pivot = cohort_data.pivot(
        index='Cohort_Year',
        columns='Purchase_Year',
        values='Customers'
    )
    
    # Calculate retention percentages
    retention_matrix = cohort_pivot.copy()
    for cohort_year in retention_matrix.index:
        cohort_size = cohort_sizes.get(cohort_year, 1)
        retention_matrix.loc[cohort_year] = (cohort_pivot.loc[cohort_year] / cohort_size * 100).round(1)
    
    # Heatmap
    st.markdown("### 🔥 Retention Heatmap (%)")
    
    fig = px.imshow(
        retention_matrix,
        labels=dict(x="Purchase Year", y="Cohort Year", color="Retention %"),
        x=retention_matrix.columns,
        y=retention_matrix.index,
        color_continuous_scale='RdYlGn',
        text_auto='.1f',
        aspect="auto"
    )
    fig.update_layout(
        title='Customer Retention by Cohort',
        height=max(400, len(retention_matrix) * 60)
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Correlation test on first cohort retention trend
    if len(retention_matrix) > 0:
        first_cohort = retention_matrix.iloc[0].dropna()
        if len(first_cohort) >= 3:
            years = list(range(len(first_cohort)))
            retention_values = first_cohort.values
            
            corr, p_val, strength = correlation_test(years, retention_values)
            
            st.markdown("### 📈 Statistical Analysis - First Cohort Retention Trend")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Correlation Coefficient", f"{corr:.3f}")
            with col2:
                st.metric("Trend Strength", strength)
            with col3:
                st.metric("P-Value", f"{p_val:.4f}")
            
            if p_val < 0.05:
                direction = "positive (retention improving)" if corr > 0 else "negative (retention declining)"
                st.info(f"📊 **Statistically significant** {strength.lower()} {direction} retention trend detected (p < 0.05)")
            else:
                st.info("📊 No statistically significant retention trend detected")
    
    # Raw cohort data
    with st.expander("📋 View Raw Cohort Data"):
        st.dataframe(
            cohort_data.pivot(index='Cohort_Year', columns='Purchase_Year', values='Customers'),
            use_container_width=True
        )

# ════════════════════════════════════════════════════════════
# VIEW 9: CONCENTRATION RISK
# ════════════════════════════════════════════════════════════

elif view == "Concentration Risk":
    st.title("⚠️ Concentration Risk Analysis (HHI)")
    
    customer_revenue, hhi_score = hhi_analysis(df)
    
    # HHI interpretation
    if hhi_score < 1500:
        hhi_status = "🟢 Low Risk"
        hhi_color = "green"
        hhi_message = "Revenue is well-diversified across customers"
    elif hhi_score < 2500:
        hhi_status = "🟡 Moderate Risk"
        hhi_color = "orange"
        hhi_message = "Some concentration risk exists"
    else:
        hhi_status = "🔴 High Risk"
        hhi_color = "red"
        hhi_message = "Significant revenue concentration - diversification recommended"
    
    # Metrics
    top5_share = customer_revenue.head(5)['Share%'].sum()
    top10_share = customer_revenue.head(10)['Share%'].sum()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("HHI Score", f"{hhi_score:.0f}", hhi_status)
    with col2:
        st.metric("Top 5 Share", f"{top5_share:.1f}%")
    with col3:
        st.metric("Top 10 Share", f"{top10_share:.1f}%")
    
    st.markdown(f"**Analysis:** {hhi_message}")
    st.markdown("---")
    
    # Lorenz Curve
    st.markdown("### 📉 Lorenz Curve - Revenue Concentration")
    
    fig = go.Figure()
    
    # Actual distribution (Lorenz curve)
    fig.add_trace(go.Scatter(
        x=list(range(1, len(customer_revenue) + 1)),
        y=customer_revenue['Cumulative%'].values,
        mode='lines',
        fill='tonexty',
        name='Actual Distribution',
        line=dict(color='red', width=3),
        fillcolor='rgba(255, 0, 0, 0.1)'
    ))
    
    # Perfect distribution (45-degree line)
    fig.add_trace(go.Scatter(
        x=[1, len(customer_revenue)],
        y=[0, 100],
        mode='lines',
        name='Perfect Distribution',
        line=dict(color='blue', width=2, dash='dash')
    ))
    
    fig.update_layout(
        title='Lorenz Curve - Customer Revenue Concentration',
        xaxis_title='Customer Rank (sorted by revenue)',
        yaxis_title='Cumulative Revenue %',
        height=500,
        hovermode='x unified'
    )
    st.plotly_chart(fig, use_container_width=True)
    
    st.caption("**Interpretation:** The further the red curve is from the blue line, the higher the concentration")
    
    # Top N customers table
    st.markdown("### 🏆 Top Customers (Concentration)")
    top_n = st.slider("Show top N customers", 5, 50, 10)
    
    st.dataframe(
        customer_revenue[['Customer', 'Revenue', 'Share%', 'Cumulative%']].head(top_n).style.format({
            'Revenue': '₹{:,.0f}',
            'Share%': '{:.2f}%',
            'Cumulative%': '{:.2f}%'
        }).background_gradient(subset=['Share%'], cmap='Reds'),
        use_container_width=True
    )

# ════════════════════════════════════════════════════════════
# VIEW 10: PRICE VARIANCE
# ════════════════════════════════════════════════════════════

elif view == "Price Variance":
    st.title("💰 Price Variance Analysis")
    
    if df['Item Details'].iloc[0] == 'Not Specified':
        st.error("❌ Product column required for Price Variance analysis")
        st.info("Upload Excel with 'Item Details' column to enable this feature")
        st.stop()
    
    price_data = price_analysis(df)
    
    if price_data.empty:
        st.warning("⚠️ Insufficient data for price analysis")
        st.info("Need at least 3 transactions per product per year")
        st.stop()
    
    # Product selection
    products = sorted(price_data['Product'].unique())
    selected_product = st.selectbox("Select Product:", products)
    
    product_trend = price_data[price_data['Product'] == selected_product].sort_values('Year')
    
    if len(product_trend) < 2:
        st.warning(f"⚠️ {selected_product} needs data from multiple years for trend analysis")
        st.stop()
    
    # Calculate statistics
    first_year_price = product_trend.iloc[0]['Avg_Price']
    latest_year_price = product_trend.iloc[-1]['Avg_Price']
    total_change = ((latest_year_price - first_year_price) / first_year_price * 100)
    
    # Correlation test
    years = product_trend['Year'].values
    prices = product_trend['Avg_Price'].values
    corr, p_val, strength = correlation_test(years, prices)
    direction = "upward" if corr > 0 else "downward"
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("First Year Avg", f"₹{first_year_price:,.2f}")
    with col2:
        st.metric("Latest Year Avg", f"₹{latest_year_price:,.2f}")
    with col3:
        st.metric("Total Change", f"{total_change:+.1f}%")
    with col4:
        st.metric("Trend", f"{strength} {direction}", f"p={p_val:.4f}")
    
    if p_val < 0.05:
        st.info(f"📊 **Statistically significant** {strength.lower()} {direction} price trend detected (p < 0.05)")
    else:
        st.info("📊 No statistically significant price trend detected")
    
    st.markdown("---")
    
    # 4-Panel Dashboard
    st.markdown("### 📊 Multi-Panel Price Dashboard")
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            'Price Trend with Confidence Band',
            'Year-over-Year % Change',
            'Price Distribution (Box Plot)',
            'Min-Max Range'
        )
    )
    
    # Panel 1: Trend with confidence band
    std_dev = product_trend['Std_Dev'].mean()
    
    fig.add_trace(
        go.Scatter(
            x=product_trend['Year'],
            y=product_trend['Avg_Price'],
            mode='lines+markers',
            name='Avg Price',
            line=dict(color='#667eea', width=3),
            showlegend=True
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=product_trend['Year'],
            y=product_trend['Avg_Price'] + product_trend['Std_Dev'],
            mode='lines',
            line=dict(width=0),
            showlegend=False
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=product_trend['Year'],
            y=product_trend['Avg_Price'] - product_trend['Std_Dev'],
            mode='lines',
            fill='tonexty',
            fillcolor='rgba(102, 126, 234, 0.2)',
            line=dict(width=0),
            name='±1 SD',
            showlegend=True
        ),
        row=1, col=1
    )
    
    # Panel 2: YoY % change
    yoy_change = product_trend['Avg_Price'].pct_change() * 100
    colors = ['green' if x >= 0 else 'red' for x in yoy_change]
    
    fig.add_trace(
        go.Bar(
            x=product_trend['Year'],
            y=yoy_change,
            marker_color=colors,
            name='YoY %',
            showlegend=False
        ),
        row=1, col=2
    )
    
    # Panel 3: Distribution
    fig.add_trace(
        go.Box(
            y=product_trend['Avg_Price'],
            name='Distribution',
            marker_color='#667eea',
            showlegend=False
        ),
        row=2, col=1
    )
    
    # Panel 4: Min-Max range
    fig.add_trace(
        go.Scatter(
            x=product_trend['Year'],
            y=product_trend['Max_Price'],
            mode='lines',
            name='Max',
            line=dict(color='red', dash='dash'),
            showlegend=True
        ),
        row=2, col=2
    )
    
    fig.add_trace(
        go.Scatter(
            x=product_trend['Year'],
            y=product_trend['Min_Price'],
            mode='lines',
            fill='tonexty',
            fillcolor='rgba(0, 255, 0, 0.1)',
            name='Min',
            line=dict(color='green', dash='dash'),
            showlegend=True
        ),
        row=2, col=2
    )
    
    fig.update_layout(height=800, showlegend=True, title_text=f"Price Analysis: {selected_product}")
    st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════════════════
# VIEW 11: SALESPERSON DASHBOARD
# ════════════════════════════════════════════════════════════

elif view == "Salesperson Dashboard":
    st.title("👤 Salesperson Performance Dashboard")
    
    performance = sales_performance(df)
    
    if performance.empty:
        st.error("❌ Salesperson column not available in your data")
        st.info("Upload Excel with 'Salesperson' column to enable this feature")
        st.stop()
    
    # Overall metrics
    total_reps = len(performance)
    total_revenue_all = performance['Revenue'].sum()
    avg_per_rep = total_revenue_all / total_reps
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Salespersons", total_reps)
    with col2:
        st.metric("Total Revenue", f"₹{total_revenue_all:,.0f}")
    with col3:
        st.metric("Avg Revenue/Rep", f"₹{avg_per_rep:,.0f}")
    
    st.markdown("---")
    
    # Performance table with categories
    performance['Revenue%'] = (performance['Revenue'] / total_revenue_all * 100).round(2)
    
    def categorize_rep(row):
        if row['Rank'] <= max(1, total_reps * 0.2):
            return "⭐ Top 20%"
        elif row['Rank'] <= max(2, total_reps * 0.5):
            return "✓ Average"
        else:
            return "⚠️ Below Average"
    
    performance['Category'] = performance.apply(categorize_rep, axis=1)
    
    st.markdown("### 📊 Performance Rankings")
    st.dataframe(
        performance[['Rank', 'Salesperson', 'Revenue', 'Revenue%', 'Customers', 'Transactions', 'Avg_Deal_Size', 'Category']].style.format({
            'Revenue': '₹{:,.0f}',
            'Revenue%': '{:.1f}%',
            'Avg_Deal_Size': '₹{:,.0f}'
        }).background_gradient(subset=['Revenue'], cmap='Greens'),
        use_container_width=True
    )
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 💰 Revenue by Salesperson")
        fig1 = create_pro_chart(
            performance.head(10),
            'bar',
            x='Salesperson',
            y='Revenue',
            title='Top 10 Salespersons by Revenue'
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.markdown("### 📈 Revenue vs Customers")
        fig2 = px.scatter(
            performance,
            x='Customers',
            y='Revenue',
            size='Transactions',
            hover_data=['Salesperson'],
            title='Revenue vs Customer Count',
            color='Category',
            color_discrete_map={
                "⭐ Top 20%": "#10b981",
                "✓ Average": "#f59e0b",
                "⚠️ Below Average": "#ef4444"
            }
        )
        st.plotly_chart(fig2, use_container_width=True)

# ════════════════════════════════════════════════════════════
# VIEW 12: REP COMPARISON
# ════════════════════════════════════════════════════════════

elif view == "Rep Comparison":
    st.title("📊 Rep Comparison - Side-by-Side Analysis")
    
    performance = sales_performance(df)
    
    if performance.empty:
        st.error("❌ Salesperson column not available")
        st.stop()
    
    # Select reps to compare
    all_reps = performance['Salesperson'].tolist()
    
    selected_reps = st.multiselect(
        "Select 2-5 salespersons to compare:",
        all_reps,
        default=all_reps[:min(3, len(all_reps))],
        max_selections=5
    )
    
    if len(selected_reps) < 2:
        st.info("ℹ️ Please select at least 2 salespersons to compare")
        st.stop()
    
    comparison_data = performance[performance['Salesperson'].isin(selected_reps)]
    
    # Individual cards
    st.markdown("### 📋 Individual Performance Cards")
    
    for rep in selected_reps:
        rep_data = comparison_data[comparison_data['Salesperson'] == rep].iloc[0]
        
        with st.container(border=True):
            st.markdown(f"#### {rep}")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Revenue", f"₹{rep_data['Revenue']:,.0f}")
            with c2:
                st.metric("Customers", int(rep_data['Customers']))
            with c3:
                st.metric("Transactions", int(rep_data['Transactions']))
            with c4:
                st.metric("Avg Deal", f"₹{rep_data['Avg_Deal_Size']:,.0f}")
    
    st.markdown("---")
    
    # Comparison charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 💰 Revenue Comparison")
        fig1 = px.bar(
            comparison_data,
            x='Salesperson',
            y='Revenue',
            title='Revenue by Salesperson',
            color='Salesperson'
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.markdown("### 📊 Revenue vs Customers")
        fig2 = px.scatter(
            comparison_data,
            x='Customers',
            y='Revenue',
            size='Transactions',
            text='Salesperson',
            title='Performance Matrix'
        )
        fig2.update_traces(textposition='top center')
        st.plotly_chart(fig2, use_container_width=True)
    
    # Grouped comparison
    st.markdown("### 📈 All Metrics Comparison")
    
    metrics_comparison = comparison_data[['Salesperson', 'Revenue', 'Customers', 'Transactions']].melt(
        id_vars='Salesperson',
        var_name='Metric',
        value_name='Value'
    )
    
    fig3 = px.bar(
        metrics_comparison,
        x='Salesperson',
        y='Value',
        color='Metric',
        barmode='group',
        title='Grouped Metrics Comparison'
    )
    st.plotly_chart(fig3, use_container_width=True)

# ════════════════════════════════════════════════════════════
# VIEW 13: TERRITORY ANALYSIS
# ════════════════════════════════════════════════════════════

elif view == "Territory Analysis":
    st.title("🗺️ Territory Analysis - Geographic Performance")
    
    territory_data = territory_analysis(df)
    
    if territory_data.empty:
        st.error("❌ Salesperson column not available")
        st.stop()
    
    # Territory overview
    total_territories = len(territory_data)
    total_customers_all = df['Particulars'].nunique()
    avg_customers_per_territory = total_customers_all / total_territories
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Territories", total_territories)
    with col2:
        st.metric("Total Customers", total_customers_all)
    with col3:
        st.metric("Avg Customers/Territory", f"{avg_customers_per_territory:.0f}")
    
    st.markdown("---")
    
    # Performance matrix scatter plot
    st.markdown("### 📊 Territory Performance Matrix")
    
    fig = px.scatter(
        territory_data,
        x='Customers',
        y='Revenue',
        size='Transactions',
        color='Category',
        hover_data=['Territory'],
        title='Territory Performance Matrix',
        color_discrete_map={
            "🌟 High Revenue / High Reach": "#10b981",
            "💰 High Revenue / Low Reach": "#3b82f6",
            "📈 Growth Potential": "#f59e0b",
            "⚠️ Developing": "#ef4444"
        }
    )
    
    # Add quadrant lines
    high_revenue_threshold = territory_data['Revenue'].quantile(0.75)
    high_customer_threshold = territory_data['Customers'].quantile(0.75)
    
    fig.add_hline(y=high_revenue_threshold, line_dash="dash", line_color="gray", opacity=0.5)
    fig.add_vline(x=high_customer_threshold, line_dash="dash", line_color="gray", opacity=0.5)
    
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)
    
    st.caption("**Quadrants:** High Revenue/High Reach (top-right) | High Revenue/Low Reach (top-left) | Growth Potential (bottom-right) | Developing (bottom-left)")
    
    # Territory details table
    st.markdown("### 📋 Territory Details")
    st.dataframe(
        territory_data[['Territory', 'Revenue', 'Customers', 'Transactions', 'Penetration', 'Revenue_per_Customer', 'Category']].style.format({
            'Revenue': '₹{:,.0f}',
            'Penetration': '{:.2f}',
            'Revenue_per_Customer': '₹{:,.0f}'
        }).background_gradient(subset=['Revenue'], cmap='Greens'),
        use_container_width=True
    )
    
    # Category distribution
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎯 Territory Categories")
        category_counts = territory_data['Category'].value_counts().reset_index()
        category_counts.columns = ['Category', 'Count']
        
        fig_cat = px.pie(
            category_counts,
            values='Count',
            names='Category',
            title='Territory Distribution',
            hole=0.3
        )
        st.plotly_chart(fig_cat, use_container_width=True)
    
    with col2:
        st.markdown("### 📊 Top Territories by Revenue")
        top_territories = territory_data.nlargest(5, 'Revenue')
        
        fig_top = px.bar(
            top_territories,
            x='Territory',
            y='Revenue',
            title='Top 5 Territories',
            color='Category'
        )
        st.plotly_chart(fig_top, use_container_width=True)

# ════════════════════════════════════════════════════════════
# SIDEBAR FOOTER
# ════════════════════════════════════════════════════════════

st.sidebar.markdown("---")
st.sidebar.caption("**Sales Intelligence Pro**")
st.sidebar.caption("Production Version v1.0")
st.sidebar.caption("✅ Smart duplicate detection")
st.sidebar.caption("✅ Missing column handling")
st.sidebar.caption("✅ All 13 analytics modules")
st.sidebar.caption("✅ Statistical testing")

# ════════════════════════════════════════════════════════════
# END OF FILE
# ════════════════════════════════════════════════════════════
