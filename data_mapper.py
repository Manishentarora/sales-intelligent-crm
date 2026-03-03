"""
UNIVERSAL DATA MAPPER + OCR MODULE
Reads ANY Excel/CSV format + extracts data from scanned invoices (multilingual)
"""

import pandas as pd
import io
import re
from datetime import datetime
from pathlib import Path
import streamlit as st

try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except:
    OCR_AVAILABLE = False

try:
    from anthropic import Anthropic
    CLAUDE_AVAILABLE = True
except:
    CLAUDE_AVAILABLE = False

# ═══════════════════════════════════════════════════════════
#  INTELLIGENT COLUMN MAPPER
# ═══════════════════════════════════════════════════════════

class UniversalMapper:
    """Maps any Excel/CSV format to standard schema"""
    
    STANDARD_SCHEMA = {
        'Date': ['date', 'dt', 'invoice date', 'bill date', 'voucher date', 
                 'transaction date', 'तारीख', 'fecha', 'datum'],
        'Customer': ['customer', 'particulars', 'party', 'account', 'ledger',
                     'client', 'buyer', 'ग्राहक', 'cliente', 'kunde'],
        'Product': ['product', 'item', 'description', 'item details', 'goods',
                    'उत्पाद', 'producto', 'produkt'],
        'Amount': ['amount', 'amt', 'value', 'total', 'price', 'revenue',
                   'राशि', 'cantidad', 'betrag'],
        'Invoice': ['invoice', 'bill', 'vch no', 'voucher', 'receipt',
                    'बिल', 'factura', 'rechnung'],
        'Quantity': ['quantity', 'qty', 'units', 'pcs', 'मात्रा', 'cantidad'],
        'Salesperson': ['salesperson', 'rep', 'agent', 'sales rep', 'executive',
                        'विक्रेता', 'vendedor'],
        'Category': ['category', 'type', 'class', 'group', 'श्रेणी', 'categoría'],
        'Location': ['location', 'branch', 'city', 'region', 'स्थान'],
        'Tax': ['tax', 'gst', 'vat', 'igst', 'cgst', 'sgst', 'कर']
    }
    
    def __init__(self):
        self.mapping = {}
        self.confidence = {}
    
    def auto_detect(self, df: pd.DataFrame) -> dict:
        """Auto-detect column mapping with confidence scores"""
        
        detected = {}
        scores = {}
        
        # Clean column names
        cols_clean = {col: str(col).lower().strip() for col in df.columns}
        
        # Try exact/fuzzy match
        for std_name, patterns in self.STANDARD_SCHEMA.items():
            best_match = None
            best_score = 0
            
            for col_orig, col_clean in cols_clean.items():
                # Exact match
                if col_clean in patterns:
                    best_match = col_orig
                    best_score = 1.0
                    break
                
                # Partial match
                for pattern in patterns:
                    if pattern in col_clean or col_clean in pattern:
                        score = len(pattern) / max(len(pattern), len(col_clean))
                        if score > best_score:
                            best_match = col_orig
                            best_score = score
            
            if best_match and best_score > 0.5:
                detected[std_name] = best_match
                scores[std_name] = best_score
        
        # Content-based detection for missing fields
        if 'Date' not in detected:
            detected.update(self._detect_date_column(df))
        
        if 'Amount' not in detected:
            detected.update(self._detect_amount_column(df))
        
        if 'Customer' not in detected and 'Product' not in detected:
            detected.update(self._detect_text_columns(df))
        
        self.mapping = detected
        self.confidence = scores
        return detected
    
    def _detect_date_column(self, df: pd.DataFrame) -> dict:
        """Detect date column by content"""
        for col in df.columns:
            try:
                sample = df[col].dropna().head(10)
                parsed = pd.to_datetime(sample, errors='coerce')
                if parsed.notna().sum() >= 7:  # 70% success rate
                    return {'Date': col}
            except:
                continue
        return {}
    
    def _detect_amount_column(self, df: pd.DataFrame) -> dict:
        """Detect amount column by numeric content"""
        for col in df.columns:
            try:
                sample = df[col].dropna().head(20)
                # Try parsing as number (handle ₹, commas, etc)
                clean = sample.astype(str).str.replace(r'₹|,|Rs\.?', '', regex=True)
                numeric = pd.to_numeric(clean, errors='coerce')
                
                if numeric.notna().sum() >= 15:  # 75% numeric
                    # Check if values look like amounts (> 0, reasonable range)
                    if numeric.min() > 0 and numeric.max() < 1e10:
                        return {'Amount': col}
            except:
                continue
        return {}
    
    def _detect_text_columns(self, df: pd.DataFrame) -> dict:
        """Detect customer/product from text columns"""
        text_cols = df.select_dtypes(include=['object']).columns
        
        if len(text_cols) >= 1:
            # First text column = Customer
            result = {'Customer': text_cols[0]}
            
            # Second text column = Product (if exists)
            if len(text_cols) >= 2:
                result['Product'] = text_cols[1]
            
            return result
        return {}
    
    def apply_mapping(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply detected mapping and standardize data"""
        
        if not self.mapping:
            self.auto_detect(df)
        
        # Rename columns
        rename_dict = {v: k for k, v in self.mapping.items()}
        df_mapped = df.rename(columns=rename_dict)
        
        # Standardize Date
        if 'Date' in df_mapped.columns:
            df_mapped['Date'] = pd.to_datetime(df_mapped['Date'], errors='coerce')
        
        # Standardize Amount
        if 'Amount' in df_mapped.columns:
            df_mapped['Amount'] = (df_mapped['Amount']
                                   .astype(str)
                                   .str.replace(r'₹|,|Rs\.?|\$', '', regex=True)
                                   .str.strip())
            df_mapped['Amount'] = pd.to_numeric(df_mapped['Amount'], errors='coerce')
        
        # Standardize Quantity
        if 'Quantity' in df_mapped.columns:
            df_mapped['Quantity'] = pd.to_numeric(df_mapped['Quantity'], errors='coerce')
        
        # Clean text fields
        for col in ['Customer', 'Product', 'Salesperson', 'Category', 'Location']:
            if col in df_mapped.columns:
                df_mapped[col] = df_mapped[col].astype(str).str.strip()
        
        return df_mapped

# ═══════════════════════════════════════════════════════════
#  OCR INVOICE EXTRACTOR
# ═══════════════════════════════════════════════════════════

class InvoiceOCR:
    """Extract structured data from scanned invoices (multilingual)"""
    
    def __init__(self, anthropic_api_key: str = None):
        self.api_key = anthropic_api_key
        if anthropic_api_key and CLAUDE_AVAILABLE:
            self.client = Anthropic(api_key=anthropic_api_key)
        else:
            self.client = None
    
    def extract_from_image(self, image_path: str) -> pd.DataFrame:
        """Extract invoice data from image using OCR + Claude"""
        
        # Step 1: OCR to get text
        if OCR_AVAILABLE:
            text = self._ocr_extract(image_path)
        else:
            return pd.DataFrame()
        
        # Step 2: Use Claude to structure the data
        if self.client:
            structured = self._claude_structure(text)
            return self._to_dataframe(structured)
        else:
            # Fallback: regex-based extraction
            return self._regex_extract(text)
    
    def _ocr_extract(self, image_path: str) -> str:
        """Extract text using Tesseract OCR"""
        try:
            img = Image.open(image_path)
            # Try multiple languages
            text = pytesseract.image_to_string(img, lang='eng+hin+spa+fra+deu')
            return text
        except Exception as e:
            st.error(f"OCR failed: {e}")
            return ""
    
    def _claude_structure(self, text: str) -> dict:
        """Use Claude to extract structured data from OCR text"""
        
        prompt = f"""Extract invoice/bill data from this text and return ONLY a JSON object with this structure:

{{
  "invoice_no": "...",
  "date": "YYYY-MM-DD",
  "customer": "...",
  "items": [
    {{"product": "...", "quantity": 0, "price": 0, "amount": 0}}
  ],
  "total": 0,
  "tax": 0
}}

OCR Text:
{text}

Rules:
- Extract ALL line items
- Convert dates to YYYY-MM-DD format
- Extract numbers without currency symbols
- If a field is not found, use null
- Return ONLY the JSON, no explanation"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            json_str = response.content[0].text.strip()
            # Remove markdown code blocks if present
            json_str = re.sub(r'```json\s*|\s*```', '', json_str).strip()
            
            import json
            return json.loads(json_str)
            
        except Exception as e:
            st.error(f"Claude extraction failed: {e}")
            return {}
    
    def _regex_extract(self, text: str) -> pd.DataFrame:
        """Fallback: regex-based extraction"""
        
        lines = text.split('\n')
        data = []
        
        # Simple patterns
        date_pattern = r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})'
        amount_pattern = r'(?:₹|Rs\.?|INR)?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
        
        invoice_date = None
        for line in lines[:10]:  # Check first 10 lines for date
            match = re.search(date_pattern, line)
            if match:
                try:
                    invoice_date = pd.to_datetime(match.group(1), dayfirst=True)
                    break
                except:
                    continue
        
        # Extract line items (simple heuristic)
        for line in lines:
            amounts = re.findall(amount_pattern, line)
            if len(amounts) >= 1:
                # Assume last number is amount
                amount = float(amounts[-1].replace(',', ''))
                if amount > 10:  # Filter out small numbers
                    data.append({
                        'Date': invoice_date,
                        'Product': line[:50].strip(),  # First 50 chars
                        'Amount': amount
                    })
        
        return pd.DataFrame(data) if data else pd.DataFrame()
    
    def _to_dataframe(self, structured: dict) -> pd.DataFrame:
        """Convert Claude's structured output to DataFrame"""
        
        if not structured or 'items' not in structured:
            return pd.DataFrame()
        
        items = []
        for item in structured['items']:
            items.append({
                'Date': pd.to_datetime(structured.get('date'), errors='coerce'),
                'Invoice': structured.get('invoice_no', ''),
                'Customer': structured.get('customer', ''),
                'Product': item.get('product', ''),
                'Quantity': item.get('quantity', 1),
                'Amount': item.get('amount', 0)
            })
        
        return pd.DataFrame(items)

# ═══════════════════════════════════════════════════════════
#  STREAMLIT UI COMPONENT
# ═══════════════════════════════════════════════════════════

def render_data_mapper():
    """Render smart data mapper UI"""
    
    st.markdown("### 🎯 Smart Data Import")
    
    upload_type = st.radio("Data Source:", 
                           ["Excel/CSV Files", "Scanned Invoices (OCR)"],
                           horizontal=True)
    
    if upload_type == "Excel/CSV Files":
        files = st.file_uploader("Upload files", 
                                  type=['xlsx', 'xls', 'csv'],
                                  accept_multiple_files=True,
                                  help="Upload any Excel/CSV format — AI will auto-detect columns")
        
        if files:
            mapper = UniversalMapper()
            all_dfs = []
            
            for file in files:
                try:
                    # Read file
                    if file.name.endswith('.csv'):
                        df_raw = pd.read_csv(io.BytesIO(file.read()))
                    else:
                        df_raw = pd.read_excel(io.BytesIO(file.read()))
                    
                    # Auto-detect mapping
                    mapping = mapper.auto_detect(df_raw)
                    
                    with st.expander(f"📄 {file.name} — Detected Mapping"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.caption("**Standard Field**")
                            for std in mapping.keys():
                                st.text(std)
                        with col2:
                            st.caption("**Your Column**")
                            for orig in mapping.values():
                                conf = mapper.confidence.get(std, 0) * 100
                                st.text(f"{orig} ({conf:.0f}%)")
                    
                    # Apply mapping
                    df_mapped = mapper.apply_mapping(df_raw)
                    all_dfs.append(df_mapped)
                    
                except Exception as e:
                    st.error(f"❌ {file.name}: {e}")
            
            if all_dfs:
                combined = pd.concat(all_dfs, ignore_index=True)
                st.success(f"✅ Loaded {len(combined):,} rows from {len(files)} file(s)")
                
                # Preview
                with st.expander("👁️ Preview Data"):
                    st.dataframe(combined.head(20))
                
                return combined
    
    else:  # OCR Mode
        if not OCR_AVAILABLE:
            st.error("❌ OCR not available. Install: `pip install pytesseract pillow`")
            st.info("Also install Tesseract: https://github.com/tesseract-ocr/tesseract")
            return None
        
        api_key = st.text_input("Anthropic API Key (for best results):", 
                                 type="password",
                                 help="Optional but recommended for multilingual invoices")
        
        images = st.file_uploader("Upload invoice images",
                                   type=['png', 'jpg', 'jpeg', 'pdf'],
                                   accept_multiple_files=True,
                                   help="Supports: English, Hindi, Spanish, French, German")
        
        if images:
            ocr = InvoiceOCR(api_key if api_key else None)
            all_data = []
            
            for img_file in images:
                with st.spinner(f"Processing {img_file.name}..."):
                    # Save temp file
                    temp_path = f"/tmp/{img_file.name}"
                    with open(temp_path, 'wb') as f:
                        f.write(img_file.read())
                    
                    # Extract
                    df_invoice = ocr.extract_from_image(temp_path)
                    
                    if not df_invoice.empty:
                        all_data.append(df_invoice)
                        st.success(f"✅ {img_file.name}: {len(df_invoice)} items extracted")
                    else:
                        st.warning(f"⚠️ {img_file.name}: No data extracted")
            
            if all_data:
                combined = pd.concat(all_data, ignore_index=True)
                st.success(f"✅ Total: {len(combined):,} line items from {len(images)} invoice(s)")
                
                with st.expander("👁️ Preview Extracted Data"):
                    st.dataframe(combined)
                
                return combined
    
    return None

