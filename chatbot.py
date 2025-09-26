import streamlit as st
import os
from dotenv import load_dotenv
from backend.nova_client import init_nova_client, get_nova_response
import re
import requests
import yfinance as yf
import pandas as pd
import time # NEW: Import time for sleep

# Load environment variables
load_dotenv()
news_api_key = os.getenv("NEWSAPI_KEY")

# Initialize Nova client
nova_client = init_nova_client()

st.set_page_config(page_title="Fintech Assistant", page_icon="💸", layout="centered")

# --- 1. ARCHITECT THE PROMPT WITH A SYSTEM PERSONA ---
# This persona will guide the tone and style of all AI responses.
SYSTEM_PERSONA = """
You are a smart, empathetic, and professional Fintech Assistant. Your primary goal is to guide users through their financial questions with clarity and patience.
- Your tone should be conversational and encouraging, never robotic or abrupt.
- You must strictly stay within the domain of personal finance (saving, investing, budgeting, loans, retirement, expense management).
- When asking questions, first acknowledge the user's goal in a positive way.
- When providing information, especially about financial products, always be clear and avoid jargon where possible.
- If you cannot access live data, state it clearly and provide representative examples instead.
"""

# --- Initialization and API Key Check ---
if not news_api_key:
    st.error("NEWSAPI_KEY is missing. Add it to your .env and restart the app.")
    st.stop()

# --- Session State Initialization ---
def initialize_session_state():
    defaults = {
        "messages": [],
        "questions": [],
        "answers": [],
        "suggestions": [],
        "goal": None,
        "broad_intent": None,
        "risk_tolerance": None,
        "awaiting_confirmation": False,
        "current_question_index": 0,  # NEW: Track question progress
        "conversation_complete": False  # NEW: Track conversation state
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
initialize_session_state()

# --- Helper Functions ---
def ask_nova(prompt_text: str, is_json_output: bool = False):
    """Generic helper to call Nova Pro, replacing Gemini"""
    if not nova_client:
        st.error("Nova Pro client initialization failed")
        return ""
        
    # Always prepend the persona to the user's specific prompt
    full_prompt = f"{SYSTEM_PERSONA}\n\n--- TASK ---\n\n{prompt_text}"
    try:
        with st.spinner("Thinking..."):
            response = get_nova_response(nova_client, full_prompt)
        return response
    except Exception as e:
        st.error(f"An API error occurred: {e}")
        return ""

# NEW: Show a loading state
def show_loading_state():
    with st.spinner("Processing your response..."):
        time.sleep(0.5)  # Minimal delay for UX

# NEW: Safe Nova call with error handling
def safe_nova_call(prompt, fallback_message="I'm sorry, I couldn't process that. Could you try again?"):
    try:
        return ask_nova(prompt)
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return fallback_message

# --- 2. OVERHAUL THE INTENT DETECTION ENGINE ---
def get_broad_intent_from_nova(goal_text: str):
    """Uses Nova Pro for robust, high-level intent classification."""
    prompt = f"""
    Analyze the user's financial goal below and classify it into ONE of the following categories:
    - Saving/Investing (e.g., 'save for a house', 'invest 10k', 'buy stocks')
    - Debt Management (e.g., 'get a home loan', 'pay off my credit card', 'loan options')
    - Budgeting/Expense Control (e.g., 'reduce my expenses', 'create a budget', 'track my spending')
    - Retirement Planning (e.g., 'plan for retirement', 'retire at 50')
    - General Inquiry (if it's a simple greeting or doesn't fit elsewhere)
    - Out of Domain (if it's clearly not about personal finance, like 'how to cook pasta')

    User's Goal: "{goal_text}"

    Return only the category name and nothing else.
    """
    return ask_nova(prompt)

# --- 3. SOLVE THE "NO LIVE BANK DATA" PROBLEM WITH STATIC HELPERS ---
def get_static_bank_info(intent: str):
    """
    Provides representative static data for bank-related products.
    This simulates an API call and manages user expectations.
    """
    if intent == "Debt Management":
        return {
            "title": "Indicative Loan Options",
            "disclaimer": "Note: These are estimated interest rates and terms. Please verify directly with banks for current, personalized offers.",
            "options": [
                {"title": "Personal Loan", "explanation": "Typically 10.5% - 16% p.a. Flexible use, shorter tenure (1-5 years)."},
                {"title": "Home Loan", "explanation": "Typically 8.5% - 9.5% p.a. For property purchase, long tenure (15-30 years)."},
                {"title": "Car Loan", "explanation": "Typically 9% - 11% p.a. For new or used cars, tenure up to 7 years."},
            ]
        }
    if intent == "Saving/Investing": # For low-risk FD type queries
         return {
            "title": "Indicative Fixed Deposit Rates",
            "disclaimer": "Note: These are sample rates for general citizens. Senior citizen rates are often higher. Please verify with the bank.",
            "options": [
                {"title": "Major Private Bank FD (e.g., HDFC/ICICI)", "explanation": "Approx. 7.0% - 7.25% p.a. for 1-2 year tenures."},
                {"title": "Major Public Bank FD (e.g., SBI)", "explanation": "Approx. 6.8% - 7.10% p.a. for 1-2 year tenures."},
            ]
        }
    return None


# --- (Other helper functions like yfinance, newsapi can remain as they are good) ---
def fetch_news(query: str, page_size: int = 3):
    if not news_api_key: return []
    try:
        url = "https://newsapi.org/v2/everything"
        params = {"q": query, "language": "en", "sortBy": "relevancy", "pageSize": page_size, "apiKey": news_api_key}
        response = requests.get(url, params=params, timeout=5)
        articles = response.json().get("articles", [])
        return [{"title": a['title'], "url": a['url']} for a in articles]
    except Exception:
        return []

def fetch_stock_performance(tickers, period="6mo"):
    try:
        data = yf.download(tickers, period=period, progress=False)['Close']
        if data.empty: return []
        perf = ((data.iloc[-1] - data.iloc[0]) / data.iloc[0]) * 100
        return [{"ticker": ticker, "change_pct": round(pct, 2)} for ticker, pct in perf.items()]
    except Exception:
        return []

def parse_unique_suggestions(text):
    suggestions = []
    existing_titles_lower = set()
    for line in text.split("\n"):
        if ":" not in line: continue
        title_part, explanation = line.split(":", 1)
        clean_title = re.sub(r"^\s*\d+[\.\)]?\s*", "", title_part).strip()
        key = clean_title.lower()
        if key and key not in existing_titles_lower:
            existing_titles_lower.add(key)
            suggestions.append({"title": clean_title, "explanation": explanation.strip()})
    return suggestions

# --- UI and Main Logic ---
st.title("💸 Smart Fintech Assistant")
st.markdown("Ask me anything about your financial goals: saving, investing, budgeting, loans, retirement, and more!")

# Display chat history
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).markdown(msg["content"])

# --- Add progress indicator below the title ---
if st.session_state.questions:
    progress = st.session_state.current_question_index / len(st.session_state.questions)
    st.progress(progress)
    st.caption(f"Question {st.session_state.current_question_index + 1} of {len(st.session_state.questions)}")

# --- Main Chat Input and Simplified Control Flow ---
user_input = st.chat_input("Tell me your financial goal...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    # STAGE 1: Initial goal setting
    if not st.session_state.goal:
        st.session_state.goal = user_input
        
        # Use Nova Pro for intent detection
        intent = get_broad_intent_from_nova(user_input)
        st.session_state.broad_intent = intent

        if "Out of Domain" in intent:
            response_text = "I'm sorry, but I can only assist with personal finance topics like saving, loans, and budgeting. How can I help you with your finances?"
            st.session_state.goal = None # Reset goal
        elif "General Inquiry" in intent:
            response_text = "Hello! I'm here to help you with your financial goals. What would you like to achieve? For example, you can tell me 'I want to save for a vacation' or 'I need to understand my loan options.'"
            st.session_state.goal = None # Reset goal
        else:
            # --- 5. ENHANCED, CONVERSATIONAL QUESTION GENERATION ---
            question_prompt = f"""
            The user's goal is '{st.session_state.goal}', which falls under the category of '{intent}'.
            Acknowledge their goal in a friendly and encouraging tone.
            Then, generate 3-4 essential, non-redundant questions to understand their situation better.
            - For 'Saving/Investing' or 'Retirement', ALWAYS ask about their risk tolerance (Low, Medium, High).
            - For 'Debt Management', ask about the type of loan and their existing financial commitments.
            - For 'Budgeting/Expense Control', ask about their main challenge (e.g., overspending, not knowing where money goes).
            Return ONLY the friendly acknowledgment followed by the questions, each on a new line.
            Example: "That's a great goal! To help you with that, I have a few questions..."
            """
            questions_text = ask_nova(question_prompt)
            if questions_text:
                st.session_state.questions = [q.strip() for q in questions_text.split("\n") if q.strip()]
                response_text = st.session_state.questions[0] # Ask the first question (which includes the acknowledgment)
                st.session_state.questions.pop(0) # Remove the acknowledgment part for later processing
            else:
                response_text = "I'm having a little trouble thinking of questions right now. Could you please rephrase your goal?"

        st.session_state.messages.append({"role": "assistant", "content": response_text})
        st.session_state.current_question_index = 0
        st.rerun()

    # STAGE 2: Gathering answers
    elif not st.session_state.conversation_complete and st.session_state.questions:
        st.session_state.answers.append(user_input)
        st.session_state.current_question_index += 1

        # Check if there are more questions
        if st.session_state.current_question_index < len(st.session_state.questions):
            next_question = st.session_state.questions[st.session_state.current_question_index]
            st.session_state.messages.append({"role": "assistant", "content": next_question})
            st.rerun()
        else:
            # Mark conversation as complete when all questions are answered
            st.session_state.conversation_complete = True

    # STAGE 3: Providing suggestions
    if st.session_state.conversation_complete and not st.session_state.suggestions:
        context_summary = f"Goal: {st.session_state.goal}\n"
        for q, a in zip(st.session_state.questions, st.session_state.answers):
            context_summary += f"Q: {q}\nA: {a}\n"

        # The suggestions prompt is now dynamically tailored to the broad intent
        suggestion_prompt = f"""
        Based on the user's situation summarized below, provide a diverse list of 4-5 actionable suggestions.
        The user's intent is '{st.session_state.broad_intent}'. Your suggestions must be highly relevant to this intent.

        - If 'Budgeting/Expense Control', suggest concrete strategies like the '50/30/20 rule', 'envelope system', or recommend types of budgeting apps.
        - If 'Debt Management', use the static bank info provided below to suggest loan types, and also mention strategies like 'debt snowball' or 'debt avalanche'.
        - If 'Saving/Investing' or 'Retirement', provide a mix of options that match the user's stated risk tolerance. Use real-world examples like 'Nifty 50 Index Fund' or 'Public Provident Fund'.

        User Context:
        {context_summary}
        """

        # Inject static bank data if relevant
        static_data = get_static_bank_info(st.session_state.broad_intent)
        if static_data:
            suggestion_prompt += f"\nStatic Reference Data (Use this for examples):\n{static_data}"

        suggestions_text = ask_nova(suggestion_prompt)
        
        final_suggestions = parse_unique_suggestions(suggestions_text)
        st.session_state.suggestions = final_suggestions

        response_text = "Based on our conversation, here are a few tailored suggestions for you:\n\n"
        for i, sug in enumerate(final_suggestions):
            response_text += f"{i+1}. *{sug['title']}*: {sug['explanation']}\n"
        
        # Add relevant news or market data
        news = fetch_news(st.session_state.goal)
        if news:
            response_text += "\n\n*Relevant News:*\n"
            for n in news:
                response_text += f"- [{n['title']}]({n['url']})\n"
        
        if static_data and static_data.get('disclaimer'):
            response_text += f"\n\n*{static_data['disclaimer']}*"

        st.session_state.messages.append({"role": "assistant", "content": response_text})
        
        # Clear questions and answers to prevent re-triggering this block
        st.session_state.questions = []
        st.session_state.answers = []
        st.rerun()

    # STAGE 4: Handle follow-up questions about suggestions
    elif st.session_state.conversation_complete and st.session_state.suggestions:
        follow_up_prompt = f"""
        The user says: "{user_input}"
        Based on our previous suggestions:
        {[s['title'] for s in st.session_state.suggestions]}
        
        Provide a detailed, helpful response addressing their question.
        If they ask about something new, acknowledge it and provide relevant information.
        """
        response = ask_nova(follow_up_prompt)
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

# Add a reset button
if st.sidebar.button("Start New Conversation"):
    for key in st.session_state.keys():
        if key != "nova_client":  # Preserve the Nova client
            del st.session_state[key]
    st.rerun()