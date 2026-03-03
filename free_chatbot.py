"""
FREE AI CHATBOT - No API Key Required
Uses local LLM via Ollama (runs on your computer)
Alternative: Google's Gemini API (free tier: 15 requests/min)
"""

import streamlit as st
import pandas as pd
import json
import os
import requests

# ═══════════════════════════════════════════════════════════
#  FREE CHATBOT OPTIONS
# ═══════════════════════════════════════════════════════════

class FreeChatbot:
    """Free chatbot using Ollama (local) or Gemini (free API)"""
    
    def __init__(self, mode="gemini"):
        """
        mode: 'ollama' (fully free, runs locally) or 'gemini' (free API, requires internet)
        """
        self.mode = mode
        
        if mode == "gemini":
            # Google Gemini - Free tier: 15 req/min, 1500 req/day
            self.api_key = os.getenv("GEMINI_API_KEY", "")
            self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
        
        elif mode == "ollama":
            # Ollama - Completely free, runs locally
            self.base_url = "http://localhost:11434/api/generate"
            self.model = "llama2"  # or mistral, phi, etc.
    
    def chat(self, message: str, data_summary: dict, history: list = None) -> tuple:
        """Send message and get response"""
        
        context = self._build_context(data_summary)
        
        system_prompt = f"""You are a Sales Intelligence Assistant. Help users analyze their data.

Data Context:
{context}

Be concise and actionable. Suggest specific analytics views to explore."""

        if self.mode == "gemini":
            return self._chat_gemini(message, system_prompt, history)
        else:
            return self._chat_ollama(message, system_prompt, history)
    
    def _chat_gemini(self, message: str, system: str, history: list) -> tuple:
        """Use Google Gemini (free API)"""
        
        if not self.api_key:
            return "⚙️ Set GEMINI_API_KEY environment variable. Get free key at: https://makersuite.google.com/app/apikey", history or []
        
        try:
            url = f"{self.base_url}?key={self.api_key}"
            
            payload = {
                "contents": [{
                    "parts": [{
                        "text": f"{system}\n\nUser: {message}"
                    }]
                }]
            }
            
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                text = result['candidates'][0]['content']['parts'][0]['text']
                
                if not history:
                    history = []
                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": text})
                
                return text, history
            else:
                return f"❌ Gemini API error: {response.status_code}", history or []
                
        except Exception as e:
            return f"❌ Error: {str(e)}", history or []
    
    def _chat_ollama(self, message: str, system: str, history: list) -> tuple:
        """Use Ollama (local LLM)"""
        
        try:
            payload = {
                "model": self.model,
                "prompt": f"{system}\n\nUser: {message}\n\nAssistant:",
                "stream": False
            }
            
            response = requests.post(self.base_url, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                text = result.get('response', '')
                
                if not history:
                    history = []
                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": text})
                
                return text, history
            else:
                return "❌ Ollama not running. Start with: `ollama serve`", history or []
                
        except requests.exceptions.ConnectionError:
            return "❌ Ollama not installed. Install: https://ollama.ai", history or []
        except Exception as e:
            return f"❌ Error: {str(e)}", history or []
    
    def _build_context(self, summary: dict) -> str:
        """Build data context from summary"""
        parts = []
        
        if 'total_revenue' in summary:
            parts.append(f"Revenue: ₹{summary['total_revenue']:,.0f}")
        if 'customers' in summary:
            parts.append(f"Customers: {summary['customers']:,}")
        if 'transactions' in summary:
            parts.append(f"Transactions: {summary['transactions']:,}")
        
        if 'top_customers' in summary:
            top5 = summary['top_customers'][:5]
            parts.append("\nTop Customers:\n" + 
                        "\n".join([f"- {c}: ₹{r:,.0f}" for c, r in top5]))
        
        if 'trends' in summary:
            parts.append(f"\nTrends: {summary['trends']}")
        
        if 'alerts' in summary and summary['alerts'] != "None":
            parts.append(f"\n⚠️ Alerts:\n{summary['alerts']}")
        
        return "\n".join(parts) if parts else "No data loaded."

# ═══════════════════════════════════════════════════════════
#  STREAMLIT INTEGRATION
# ═══════════════════════════════════════════════════════════

def render_free_chatbot(df: pd.DataFrame = None):
    """Render free chatbot in sidebar"""
    
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 💬 Free AI Assistant")
        
        # Choose mode
        mode = st.radio("Engine:", 
                       ["Gemini (Free API)", "Ollama (Local)"],
                       horizontal=True,
                       key="chatbot_mode")
        
        engine = "gemini" if "Gemini" in mode else "ollama"
        
        # Setup instructions
        with st.expander("⚙️ Setup"):
            if engine == "gemini":
                st.caption("**Google Gemini (Free)**")
                st.caption("1. Get key: https://makersuite.google.com/app/apikey")
                st.caption("2. Set environment variable:")
                st.code("export GEMINI_API_KEY='your-key'")
                st.caption("Free tier: 15 req/min, 1500/day")
                
                api_key = st.text_input("Or enter key:", type="password", key="gemini_key")
                if api_key:
                    os.environ["GEMINI_API_KEY"] = api_key
                    st.success("✅ Key set")
            
            else:
                st.caption("**Ollama (100% Free)**")
                st.caption("1. Install: https://ollama.ai")
                st.caption("2. Download model:")
                st.code("ollama pull llama2")
                st.caption("3. Start server:")
                st.code("ollama serve")
                st.caption("Runs on your computer, no API needed")
        
        # Initialize chatbot
        if 'free_chatbot' not in st.session_state:
            st.session_state['free_chatbot'] = FreeChatbot(engine)
        
        if 'chat_history' not in st.session_state:
            st.session_state['chat_history'] = []
        
        # Chat container
        chat_container = st.container(height=300)
        
        with chat_container:
            for msg in st.session_state['chat_history']:
                role = msg['role']
                content = msg['content']
                
                if role == "user":
                    st.markdown(f"**You:** {content}")
                else:
                    st.markdown(f"**AI:** {content}")
        
        # Input
        user_input = st.text_input("Ask about your data...", 
                                    placeholder="What are my top customers?",
                                    key="free_chatbot_input")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            send = st.button("Send", use_container_width=True, type="primary")
        with col2:
            clear = st.button("Clear", use_container_width=True)
        
        if clear:
            st.session_state['chat_history'] = []
            st.rerun()
        
        if send and user_input.strip():
            # Build summary
            summary = {}
            if df is not None and not df.empty:
                summary['total_revenue'] = df['Amount'].sum()
                summary['customers'] = df['Particulars'].nunique()
                summary['transactions'] = len(df)
                
                top = df.groupby('Particulars')['Amount'].sum().nlargest(5)
                summary['top_customers'] = list(zip(top.index, top.values))
                
                # Trends
                monthly = df.groupby(df['Date'].dt.to_period('M'))['Amount'].sum()
                if len(monthly) >= 2:
                    growth = ((monthly.iloc[-1] - monthly.iloc[-2]) / monthly.iloc[-2] * 100)
                    summary['trends'] = f"Last month: {growth:+.1f}% vs previous"
                
                # Alerts
                alerts = []
                hhi = df.groupby('Particulars')['Amount'].sum()
                top5 = (hhi.nlargest(5).sum() / hhi.sum() * 100)
                if top5 > 60:
                    alerts.append(f"High risk: Top 5 = {top5:.1f}%")
                
                last = df.groupby('Particulars')['Date'].max()
                inactive = ((pd.Timestamp.now() - last).dt.days > 90).sum()
                if inactive > 0:
                    alerts.append(f"{inactive} customers inactive 90+ days")
                
                summary['alerts'] = "\n".join(alerts) if alerts else "None"
            
            # Get response
            chatbot = st.session_state['free_chatbot']
            response, updated_history = chatbot.chat(
                user_input,
                summary,
                st.session_state['chat_history']
            )
            
            st.session_state['chat_history'] = updated_history
            st.rerun()
        
        # Quick prompts
        if not st.session_state['chat_history']:
            st.caption("**Quick prompts:**")
            for p in ["Summarize my data", "Top customers?", "Any risks?", "Growth opportunities?"]:
                if st.button(p, key=f"qp_{p}", use_container_width=True):
                    st.session_state['pending_prompt'] = p
                    st.rerun()

