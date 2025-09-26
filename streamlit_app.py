import streamlit as st
import sys
import os

# Add the project's root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

try:
    from frontend.main import *
except ImportError as e:
    st.error(f"Error importing main application: {e}")
    st.stop()