import streamlit as st
import sys
import os

# Set up the path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Import the main functionality
try:
    import main
except ImportError as e:
    st.error(f"Could not import main application: {str(e)}")
    st.error("Please ensure all files are in the correct locations:")
    st.code("""
    Required files:
    - streamlit_app.py (this file)
    - main.py
    - backend/
        - finance_service.py
        - news_service.py
        - llm_service.py
        - nova_client.py
    """)
    st.stop()
