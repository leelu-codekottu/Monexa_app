import streamlit as st
import sys
import os

# Add the project root directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Configure Streamlit page
st.set_page_config(
    page_title="Monexa - Your AI Financial Advisor",
    page_icon="🤖",
    layout="wide"
)

# Import all required modules
try:
    from backend.finance_service import get_financial_data, calculate_expected_return, get_ticker_info
    from backend.news_service import get_financial_news, summarize_news_for_llm
    from backend.llm_service import get_llm_response
    from backend.nova_client import init_nova_client, get_nova_response
    
    # Initialize Nova client
    nova_client = init_nova_client()
    if not nova_client:
        st.error("Failed to initialize Nova Pro client. Please check your configuration.")
        st.stop()
        
    # Import main app functionality
    from main import *
    
except ImportError as e:
    st.error(f"Error importing required modules: {str(e)}")
    st.error("Please ensure all required files are in the correct locations:")
    st.code("""
    Project Directory Structure:
    - streamlit_app.py (this file)
    - main.py
    - backend/
        - __init__.py
        - finance_service.py
        - news_service.py
        - llm_service.py
        - nova_client.py
    """)
    st.stop()
