"""
FREE OCR READER - No API Key Required
Uses Tesseract (100% free, open source)
Supports 100+ languages including Hindi, Spanish, French, German, Arabic
"""

import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    import pdf2image
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# ═══════════════════════════════════════════════════════════
#  FREE OCR ENGINE
# ═══════════════════════════════════════════════════════════

class FreeOCR:
    """Free OCR using Tesseract (open source)"""
    
    # Language codes for Tesseract
    LANGUAGES = {
        'English': 'eng',
        'Hindi (हिंदी)': 'hin',
        'Spanish (Español)': 'spa',
        'French (Français)': 'fra',
        'German (Deutsch)': 'deu',
        'Arabic (العربية)': 'ara',
        'Bengali (বাংলা)': 'ben',
        'Tamil (தமிழ்)': 'tam',
        'Telugu (తెలుగు)': 'tel',
        'Marathi (मराठी)': 'mar',
        'Gujarati (ગુજરાતી)': 'guj',
        'Kannada (ಕನ್ನಡ)': 'kan',
        'Malayalam (മലയാളം)': 'mal',
        'Punjabi (ਪੰਜਾਬੀ)': 'pan'
    }
    
    def __init__(self):
        self.available = OCR_AVAILABLE
    
    def extract_from_image(self, image_path: str, languages: list = None) -> str:
        """Extract text from image using Tesseract"""
        
        if not self.available:
            raise Exception("Tesseract not installed")
        
        # Default to English + Hindi
        if not languages:
            languages = ['eng', 'hin']
        
        lang_str = '+'.join(languages)
        
        try:
            img = Image.open(image_path)
            
            # Preprocess image for better OCR
            img = self._preprocess(img)
            
            # OCR with multiple languages
            text = pytesseract.image_to_string(img, lang=lang_str)
            
            return text
        
        except Exception as e:
            raise Exception(f"OCR failed: {str(e)}")
    
    def _preprocess(self, img):
        """Enhance image for better OCR accuracy"""
        from PIL import ImageEnhance, ImageFilter
        
        # Convert to grayscale
        img = img.convert('L')
        
        # Increase contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        
        # Sharpen
        img = img.filter(ImageFilter.SHARPEN)
        
        return img
    
    def extract_invoice_data(self, text: str) -> pd.DataFrame:
        """Parse OCR text into structured invoice data"""
        
        lines = text.split('\n')
        data = []
        
        # Patterns
        date_patterns = [
            r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})',
        ]
        
        amount_patterns = [
            r'(?:₹|Rs\.?|INR|USD|\$)?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:₹|Rs|INR)?'
        ]
        
        invoice_patterns = [
            r'(?:Invoice|Bill|Receipt)\s*#?\s*:?\s*([A-Z0-9-]+)',
            r'#\s*([A-Z0-9-]+)'
        ]
        
        # Extract invoice number
        invoice_no = None
        for line in lines[:15]:  # Check first 15 lines
            for pattern in invoice_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    invoice_no = match.group(1)
                    break
            if invoice_no:
                break
        
        # Extract date
        invoice_date = None
        for line in lines[:15]:
            for pattern in date_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    try:
                        date_str = match.group(1)
                        invoice_date = pd.to_datetime(date_str, dayfirst=True)
                        break
                    except:
                        continue
            if invoice_date:
                break
        
        # Extract line items
        for i, line in enumerate(lines):
            # Skip header lines
            if i < 5:
                continue
            
            # Look for lines with amounts
            amounts = []
            for pattern in amount_patterns:
                matches = re.findall(pattern, line)
                amounts.extend(matches)
            
            if amounts:
                # Get largest amount (likely the total for this line)
                amounts_clean = [float(a.replace(',', '')) for a in amounts]
                max_amount = max(amounts_clean)
                
                # Filter out small numbers (likely qty)
                if max_amount > 10:
                    # Product description is everything before the amount
                    product = re.split(r'\d+(?:,\d{3})*(?:\.\d{2})?', line)[0].strip()
                    
                    # Clean product name
                    product = re.sub(r'^\d+[\.\)]\s*', '', product)  # Remove numbering
                    product = product[:100]  # Limit length
                    
                    if len(product) > 3:  # Ignore very short lines
                        data.append({
                            'Date': invoice_date,
                            'Invoice': invoice_no or 'N/A',
                            'Product': product,
                            'Amount': max_amount
                        })
        
        # If no items found, try simpler extraction
        if not data:
            total_pattern = r'(?:Total|Grand Total|Amount|Net)\s*:?\s*(?:₹|Rs\.?)?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
            for line in lines:
                match = re.search(total_pattern, line, re.IGNORECASE)
                if match:
                    amount = float(match.group(1).replace(',', ''))
                    data.append({
                        'Date': invoice_date,
                        'Invoice': invoice_no or 'N/A',
                        'Product': 'Invoice Total',
                        'Amount': amount
                    })
                    break
        
        return pd.DataFrame(data) if data else pd.DataFrame()

# ═══════════════════════════════════════════════════════════
#  STREAMLIT INTEGRATION
# ═══════════════════════════════════════════════════════════

def render_free_ocr():
    """Render free OCR interface"""
    
    st.markdown("### 📄 Free Invoice OCR")
    
    if not OCR_AVAILABLE:
        st.error("❌ Tesseract not installed")
        
        with st.expander("📥 Installation Instructions"):
            st.markdown("""
**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
sudo apt-get install tesseract-ocr-hin tesseract-ocr-spa
```

**macOS:**
```bash
brew install tesseract
brew install tesseract-lang
```

**Windows:**
1. Download installer: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to `C:\\Program Files\\Tesseract-OCR`
3. Add to PATH

**Python packages:**
```bash
pip install pytesseract pillow pdf2image
```

**Language Packs:**
Tesseract supports 100+ languages. Install additional packs:
```bash
# Hindi
sudo apt-get install tesseract-ocr-hin

# Spanish
sudo apt-get install tesseract-ocr-spa

# All Indian languages
sudo apt-get install tesseract-ocr-{hin,ben,tam,tel,mar,guj,kan,mal}
```
""")
        return None
    
    # Language selection
    ocr = FreeOCR()
    
    st.caption("**Select languages in your invoices:**")
    selected_langs = st.multiselect(
        "Languages",
        options=list(ocr.LANGUAGES.keys()),
        default=['English', 'Hindi (हिंदी)'],
        help="Select all languages that appear in your invoices"
    )
    
    lang_codes = [ocr.LANGUAGES[lang] for lang in selected_langs]
    
    # File upload
    uploaded_files = st.file_uploader(
        "Upload invoice images",
        type=['png', 'jpg', 'jpeg', 'pdf'],
        accept_multiple_files=True,
        help="Supports: JPG, PNG, PDF"
    )
    
    if uploaded_files:
        all_data = []
        
        progress_bar = st.progress(0)
        status = st.empty()
        
        for i, file in enumerate(uploaded_files):
            status.text(f"Processing {file.name}... ({i+1}/{len(uploaded_files)})")
            
            try:
                # Save to temp
                temp_path = f"/tmp/{file.name}"
                with open(temp_path, 'wb') as f:
                    f.write(file.read())
                
                # Extract text
                text = ocr.extract_from_image(temp_path, lang_codes)
                
                # Parse into structured data
                df_invoice = ocr.extract_invoice_data(text)
                
                if not df_invoice.empty:
                    all_data.append(df_invoice)
                    st.success(f"✅ {file.name}: {len(df_invoice)} items extracted")
                    
                    # Show preview
                    with st.expander(f"👁️ {file.name} - Extracted Data"):
                        st.dataframe(df_invoice)
                        st.caption("**Raw Text:**")
                        st.text(text[:500] + "..." if len(text) > 500 else text)
                else:
                    st.warning(f"⚠️ {file.name}: No data extracted")
                    with st.expander(f"🔍 Debug: {file.name}"):
                        st.text(text)
            
            except Exception as e:
                st.error(f"❌ {file.name}: {str(e)}")
            
            progress_bar.progress((i + 1) / len(uploaded_files))
        
        status.empty()
        progress_bar.empty()
        
        if all_data:
            combined = pd.concat(all_data, ignore_index=True)
            st.success(f"✅ **Total: {len(combined):,} line items from {len(uploaded_files)} invoice(s)**")
            
            # Preview
            with st.expander("📊 All Extracted Data"):
                st.dataframe(combined)
            
            # Download options
            col1, col2 = st.columns(2)
            with col1:
                csv = combined.to_csv(index=False)
                st.download_button("📥 Download CSV", csv, "invoices.csv", "text/csv")
            
            with col2:
                try:
                    from io import BytesIO
                    import xlsxwriter
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        combined.to_excel(writer, index=False)
                    st.download_button("📥 Download Excel", output.getvalue(), 
                                      "invoices.xlsx",
                                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                except:
                    pass
            
            return combined
        
        else:
            st.warning("No data extracted from any invoice. Try:")
            st.caption("- Ensure image is clear and well-lit")
            st.caption("- Check if correct languages are selected")
            st.caption("- Verify invoice contains structured data (items, amounts)")
    
    return None

# ═══════════════════════════════════════════════════════════
#  TIPS FOR BETTER OCR ACCURACY
# ═══════════════════════════════════════════════════════════

def show_ocr_tips():
    """Display tips for better OCR results"""
    
    with st.expander("💡 Tips for Better OCR Accuracy"):
        st.markdown("""
**Image Quality:**
- ✅ Use high resolution (300 DPI or higher)
- ✅ Ensure good lighting and contrast
- ✅ Keep camera/scanner steady
- ❌ Avoid shadows or glare

**Invoice Format:**
- ✅ Flat, unfolded documents
- ✅ Clear, printed text (not handwritten)
- ✅ Standard invoice layout

**Language Setup:**
- ✅ Select all languages in your documents
- ✅ Install language packs for best results
- ✅ Use English + local language together

**Preprocessing:**
- The system automatically enhances images
- Converts to grayscale
- Increases contrast
- Sharpens text

**Supported:**
- ✅ Printed invoices
- ✅ Bills
- ✅ Receipts
- ✅ Purchase orders
- ✅ Multiple languages on same page

**Limitations:**
- ⚠️ Handwritten text (70-80% accuracy)
- ⚠️ Very small text (<8pt)
- ⚠️ Complex backgrounds
- ⚠️ Rotated or skewed images
""")

