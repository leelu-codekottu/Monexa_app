import streamlit as st
import plotly.express as px
import pandas as pd
import sys
import os
import time

# Add the project's root directory to the Python path
# This allows for absolute imports from the 'backend' package
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

try:
    # Use absolute imports from the backend package
    from backend.finance_service import get_financial_data, calculate_expected_return, get_ticker_info
    from backend.news_service import get_financial_news, summarize_news_for_llm
    from backend.llm_service import get_llm_response
    from backend.nova_client import init_nova_client, get_nova_response
except ImportError as e:
    st.error(f"Error importing backend services: {e}. Please ensure the backend files exist in a 'backend' folder at the project root.")
    st.stop()

# Initialize nova_client here
# This is crucial so the client is available globally
try:
    nova_client = init_nova_client()
    if not nova_client:
        st.error("Failed to initialize Nova Pro client. Please check your AWS credentials.")
        st.stop()
except Exception as e:
    st.error(f"Error during Nova client initialization: {e}")
    st.stop()


# --- Page Configuration ---
st.set_page_config(
    page_title="Monexa - Your AI Financial Advisor",
    page_icon="🤖",
    layout="wide"
)

# --- Market Data Constants ---
INDIAN_STOCKS = {
    "Low Risk": ["HDFCBANK.NS", "TCS.NS", "HINDUNILVR.NS", "INFY.NS", "RELIANCE.NS"],
    "Medium Risk": ["ICICIBANK.NS", "AXISBANK.NS", "SBIN.NS", "LT.NS", "MARUTI.NS"],
    "High Risk": ["TATAMOTORS.NS", "ZOMATO.NS", "PAYTM.NS", "YESBANK.NS", "IDEA.NS"]
}

US_STOCKS = {
    "Low Risk": ["MSFT", "AAPL", "JNJ", "PG", "KO"],
    "Medium Risk": ["GOOGL", "AMZN", "META", "NVDA", "V"],
    "High Risk": ["TSLA", "PLTR", "RIVN", "COIN", "GME"]
}

CRYPTO_TICKERS = ["BTC-USD", "ETH-USD", "BNB-USD", "XRP-USD", "SOL-USD"]

MUTUAL_FUNDS = {
    "Large Cap": ["HDFC Top 100", "Axis Bluechip", "Mirae Asset Large Cap"],
    "Mid Cap": ["Kotak Emerging Equity", "HDFC Mid-Cap Opportunities", "DSP Midcap"],
    "Small Cap": ["Nippon Small Cap", "SBI Small Cap", "Axis Small Cap"]
}

# --- UI Rendering ---
# Main header with columns for better layout
col1, col2, col3 = st.columns([1, 4, 1]) # Add a third column for the button

with col1:
    st.image("https://em-content.zobj.net/source/microsoft-teams/363/robot_1f916.png", width=120)
with col2:
    st.title("Monexa AI Financial Advisor")
    st.markdown("Your personalized guide to smart investing. Let's build a plan for your financial future!")

# --- Place the Chatbot Toggle Button in the new column ---
with col3:
    # Initialize the show_chatbot state at the top level
    if "show_chatbot" not in st.session_state:
        st.session_state.show_chatbot = False

    st.markdown("<br><br>", unsafe_allow_html=True)  # Add some spacing to align with title
    # The button toggles the visibility state and triggers a rerun
    if st.button("💬 Open Chat", key="open_chat_button"):
        st.session_state.show_chatbot = not st.session_state.show_chatbot
        st.rerun()

# --- Sidebar for User Inputs ---
with st.sidebar:
    st.header("👤 Your Financial Profile")

    # Investment Type Selection
    investment_type = st.selectbox(
        "What would you like to invest in?",
        ("Stocks", "Mutual Funds", "Cryptocurrency"),
        help="Select the type of investment you're interested in"
    )

    user_inputs = {"investment_type": investment_type}

    # Market Selection for Stocks
    if investment_type == "Stocks":
        market = st.selectbox(
            "Which market would you like to invest in?",
            ("Indian Market", "US Market"),
            help="Select the stock market you want to invest in"
        )
        user_inputs["market"] = market

        # Stock search
        stock_search = st.text_input(
            "Search for specific stocks:",
            placeholder="e.g., RELIANCE.NS or AAPL",
            help="Enter stock symbol to search"
        )
        user_inputs["stock_search"] = stock_search

    # Common inputs for all investment types
    user_inputs["investment_amount"] = st.number_input(
        "How much can you invest monthly (₹)?",
        min_value=0, step=1000, value=5000,
        help="Enter the amount you can comfortably invest each month in INR",
        key="sidebar_investment_amount"
    )
    
    user_inputs["horizon"] = st.slider(
        "What is your investment horizon?",
        min_value=1, max_value=30, value=10, format="%d years",
        help="How many years are you planning to invest for?"
    )
    
    user_inputs["risk"] = st.select_slider(
        "What is your risk tolerance?",
        options=["Low Risk", "Medium Risk", "High Risk"], 
        value="Medium Risk",
        help="Low risk aims for stable returns. High risk has potential for higher growth but also higher volatility."
    )
    
    custom_tickers_input = st.text_area(
        "Track specific tickers (optional):",
        placeholder="e.g., GOOGL, BTC-USD, AMZN",
        help="Enter any stock or crypto tickers you want to include in the analysis, separated by commas."
    )
    if custom_tickers_input:
        user_inputs["tickers"] = [ticker.strip().upper() for ticker in custom_tickers_input.split(',') if ticker.strip()]
    
    analyze_button = st.button("✨ Get My Personalized Advice", use_container_width=True, type="primary")

# --- Initialize chat history in session state ---
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []


# --- Helper function to display results ---
def validate_inputs(user_inputs):
    """Validate all required user inputs are provided."""
    required_inputs = {
        'investment_type': "Please select an investment type",
        'investment_amount': "Please enter your monthly investment amount",
        'horizon': "Please select your investment horizon",
        'risk': "Please select your risk tolerance level"
    }
    
    missing = [msg for field, msg in required_inputs.items() 
              if not user_inputs.get(field)]
    
    if missing:
        for msg in missing:
            st.error(msg)
        st.info("👈 Please complete all required fields in the sidebar.")
        return False
    return True

def display_results(user_inputs):
    """Encapsulates the logic to fetch data, generate insights, and render UI elements."""
    try:
        # 1. Get Investment Type and Market Selection
        investment_type = user_inputs.get("investment_type")
        risk_level = user_inputs.get("risk", "Medium Risk")
        
        # 2. Fetch and Display Latest Market News
        # 2. Display Latest Market News
        st.subheader("📰 Latest Market News & Analysis")
        # Static news data to ensure consistent display
        news_data = [
                {
                    'title': 'Global Markets Show Strong Recovery',
                    'description': 'Major global indices demonstrate resilience as markets recover from recent volatility. Tech and financial sectors lead the gains.',
                    'source': 'Market Analysis Daily',
                    'published': 'Today',
                    'url': 'https://example.com/markets'
                },
                {
                    'title': 'Tech Stocks Continue Upward Trend',
                    'description': 'Technology sector maintains momentum as AI and cloud computing companies report strong quarterly earnings.',
                    'source': 'Tech Finance Weekly',
                    'published': 'Today',
                    'url': 'https://example.com/tech'
                },
                {
                    'title': 'Emerging Markets Present New Opportunities',
                    'description': 'Analysts identify promising investment opportunities in emerging markets as economic indicators show positive trends.',
                    'source': 'Global Investment Review',
                    'published': 'Today',
                    'url': 'https://example.com/emerging'
                },
                {
                    'title': 'Sustainable Investments Gain Traction',
                    'description': 'ESG-focused investments continue to attract capital as investors prioritize sustainable and responsible investing.',
                    'source': 'Sustainable Finance Today',
                    'published': 'Today',
                    'url': 'https://example.com/esg'
                }
            ]
        
        if isinstance(news_data, list) and news_data:
            news_context = summarize_news_for_llm(news_data)
            
            # Display news in a clean format
            for article in news_data:
                with st.container(border=True):
                    st.markdown(f"### 📌 {article['title']}")
                    st.markdown(f"{article['description']}")
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"*Source: {article['source']}*")
                    with col2:
                        st.markdown(f"*{article['published']}*")
                    if article.get('url'):
                        st.markdown(f"[🔗 Read full article]({article['url']})")
        else:
            st.warning("⚠️ Could not fetch latest news. Please try again later.")
            news_context = "No recent financial news available."

        # 3. Handle Different Investment Types
        if investment_type == "Stocks":
            market = user_inputs.get("market", "Indian Market")
            stock_list = INDIAN_STOCKS if market == "Indian Market" else US_STOCKS
            
            # Display top stocks based on risk level
            st.subheader(f"📈 Top {market.split()[0]} Stocks - {risk_level}")
            tickers_to_chart = stock_list.get(risk_level, [])[:]  # Make a copy
            # Handle custom stock search
            custom_stock = user_inputs.get("stock_search", "").strip().upper()
            if custom_stock:
                # Add .NS suffix for Indian stocks if not present
                if market == "Indian Market" and not custom_stock.endswith(".NS"):
                    custom_stock += ".NS"
                tickers_to_chart.insert(0, custom_stock)  # Add to beginning of list

            # Initialize validation lists
            invalid_tickers = []
            valid_custom = []
            
            # Handle custom tickers if provided
            custom_tickers = user_inputs.get("tickers", [])
            if custom_tickers:
                for ticker in custom_tickers:
                    if ticker:  # Skip empty strings
                        info = get_ticker_info(ticker)
                        if info:
                            valid_custom.append(ticker)
                        else:
                            invalid_tickers.append(ticker)
                
                if invalid_tickers:
                    st.warning(f"Could not find data for these tickers: {', '.join(invalid_tickers)}. They will be ignored.")
                if valid_custom:
                    tickers_to_chart.extend(valid_custom)
                    tickers_to_chart = list(dict.fromkeys(tickers_to_chart))  # Remove duplicates while preserving order
            
            # Fetch and display stock data
            with st.spinner(f"Fetching {market} stock data..."):
                stock_data = get_financial_data(tickers_to_chart, market=market.split()[0].upper())
                
                if stock_data:
                    # Create tabs for different visualizations
                    price_tab, volume_tab, compare_tab = st.tabs(["Price History", "Volume Analysis", "Comparison"])
                    
                    with price_tab:
                        for ticker, data in stock_data.items():
                            st.subheader(f"{data['name']} ({ticker})")
                            hist_df = data['historical_data']
                            
                            # Price history chart
                            fig = px.line(hist_df, x='Date', y='Close',
                                        title=f'Price History (₹)',
                                        labels={'Close': 'Price (₹)', 'Date': 'Date'})
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # Key metrics
                            col1, col2, col3, col4 = st.columns(4)
                            col1.metric("Current Price", f"₹{data['current_price']:,.2f}")
                            col2.metric("Change", f"{data['price_change']:,.2f}%")
                            col3.metric("52W High", f"₹{data['high_52week']:,.2f}")
                            col4.metric("52W Low", f"₹{data['low_52week']:,.2f}")
                    
                    with volume_tab:
                        for ticker, data in stock_data.items():
                            hist_df = data['historical_data']
                            fig = px.bar(hist_df, x='Date', y='Volume',
                                       title=f'Trading Volume - {ticker}',
                                       labels={'Volume': 'Volume', 'Date': 'Date'})
                            st.plotly_chart(fig, use_container_width=True)
                    
                    with compare_tab:
                        # Normalize prices for comparison
                        comparison_df = pd.DataFrame()
                        for ticker, data in stock_data.items():
                            hist_df = data['historical_data']
                            comparison_df[ticker] = hist_df['Close'] / hist_df['Close'].iloc[0] * 100
                        
                        comparison_df.index = next(iter(stock_data.values()))['historical_data']['Date']
                        fig = px.line(comparison_df, 
                                    title='Price Comparison (Normalized)',
                                    labels={'value': 'Normalized Price (%)', 'Date': 'Date'})
                        st.plotly_chart(fig, use_container_width=True)

            # 3. Fetch Financial Data
            if tickers_to_chart:
                with st.spinner("Fetching market data..."):
                    # Get current market data
                    market_data = get_financial_data(tickers_to_chart)
                    
                    if market_data:
                        # Display current market overview
                        st.subheader("📊 Market Overview")
                        cols = st.columns(len(market_data))
                        for idx, (ticker, data) in enumerate(market_data.items()):
                            with cols[idx]:
                                st.metric(
                                    label=f"{data.get('name', ticker)}",
                                    value=f"₹{data['current_price']:,.2f}",
                                    delta=f"{data['price_change']:.1f}%"
                                )
                        
                        # Create financial context for LLM
                        summaries = []
                        for ticker, data in market_data.items():
                            summary = (
                                f"{ticker}: Current=${data['current_price']:.2f}, "
                                f"Change={data['price_change']:.1f}%, "
                                f"52w-High=${data['high_52week']:.2f}"
                            )
                            summaries.append(summary)
                        financial_data_context = "Market Data:\n" + "\n".join(summaries)
                    else:
                        st.warning("Could not fetch current market data.")
                        financial_data_context = "No market data available."
            else:
                financial_data_context = "No specific tickers to analyze."

            # 4. Get and Display AI Analysis
            with st.spinner("Generating AI analysis..."):
                llm_response = get_llm_response(user_inputs, financial_data_context, news_context)
                
                st.subheader("💡 Your AI-Generated Plan")
                with st.container(border=True):
                    st.markdown(llm_response)

        # 6. Visualization and Investment Projections
        if tickers_to_chart:
            st.subheader("📊 Investment Analysis & Projections")
            with st.container(border=True):
                hist_data = get_financial_data(tickers_to_chart, period="5y")
                
                if not hist_data:  # Check if dictionary is empty
                    st.warning("Could not fetch historical data for visualization.")
                    return

                tab1, tab2, tab3 = st.tabs(["📈 Historical Performance", "📊 Expected Returns", "🔮 Future Projections"])

                with tab1:
                    st.markdown("##### Historical Growth Analysis")
                    st.markdown("This chart shows how your selected investments have performed historically.")

                    # Create historical performance visualization
                    performance_data = []
                    dates = None
                    initial_investment = 10000  # ₹10,000 base investment
                    
                    for ticker, data in hist_data.items():
                        if 'historical_data' in data and isinstance(data['historical_data'], pd.DataFrame):
                            hist_df = data['historical_data']
                            if not hist_df.empty and 'Close' in hist_df.columns:
                                # Store first date series we find
                                if dates is None:
                                    dates = hist_df['Date']
                                # Calculate normalized performance
                                normalized = (hist_df['Close'] / hist_df['Close'].iloc[0]) * initial_investment
                                performance_data.append({
                                    'ticker': ticker,
                                    'values': normalized
                                })
                    
                    if performance_data and dates is not None:
                        # Create DataFrame for visualization
                        df = pd.DataFrame({
                            data['ticker']: data['values'] for data in performance_data
                        }, index=dates)
                        
                        fig = px.line(
                            df,
                            title='Historical Performance of ₹10,000 Investment',
                            labels={'value': 'Portfolio Value (₹)', 'variable': 'Investment'},
                        )
                        fig.update_layout(
                            showlegend=True,
                            yaxis_title='Value (₹)',
                            xaxis_title='Date',
                            hovermode='x unified'
                        )
                        st.plotly_chart(fig, use_container_width=True)

                        # Add future projection controls
                        st.markdown("##### Investment Projection Calculator")
                        col1, col2 = st.columns(2)
                        with col1:
                            monthly_investment = st.number_input(
                                "Monthly Investment (₹)",
                                min_value=1000,
                                max_value=1000000,
                                value=user_inputs.get('investment_amount', 5000),
                                step=1000
                            )
                        with col2:
                            projection_years = st.selectbox(
                                "Projection Period",
                                options=[1, 3, 5, 10, 15, 20],
                                index=2  # Default to 5 years
                            )

                        # Calculate and show projections
                        conservative_rate = 0.08  # 8% annual return
                        moderate_rate = 0.12     # 12% annual return
                        aggressive_rate = 0.15    # 15% annual return

                        def calculate_future_value(monthly_amount, rate, years):
                            # Using future value of annuity formula
                            monthly_rate = rate / 12
                            n_months = years * 12
                            fv = monthly_amount * ((1 + monthly_rate) ** n_months - 1) / monthly_rate
                            return fv

                        conservative_fv = calculate_future_value(monthly_investment, conservative_rate, projection_years)
                        moderate_fv = calculate_future_value(monthly_investment, moderate_rate, projection_years)
                        aggressive_fv = calculate_future_value(monthly_investment, aggressive_rate, projection_years)

                        # Create projection visualization
                        months = range(0, projection_years * 12 + 1)
                        projections = pd.DataFrame({
                            'Month': months,
                            'Conservative': [monthly_investment * i * (1 + conservative_rate/12)**i for i in months],
                            'Moderate': [monthly_investment * i * (1 + moderate_rate/12)**i for i in months],
                            'Aggressive': [monthly_investment * i * (1 + aggressive_rate/12)**i for i in months]
                        })
                        
                        # Melt the dataframe for plotting
                        proj_melted = projections.melt(
                            id_vars=['Month'],
                            value_vars=['Conservative', 'Moderate', 'Aggressive'],
                            var_name='Scenario',
                            value_name='Value'
                        )
                        
                        # Create the projection plot
                        fig_proj = px.line(
                            proj_melted,
                            x='Month',
                            y='Value',
                            color='Scenario',
                            title=f'Investment Growth Projection Over {projection_years} Years',
                            labels={'Value': 'Portfolio Value (₹)', 'Month': 'Months'},
                            color_discrete_map={
                                'Conservative': '#2E86C1',  # Blue
                                'Moderate': '#28B463',      # Green
                                'Aggressive': '#E74C3C'     # Red
                            }
                        )
                        
                        # Update layout
                        fig_proj.update_layout(
                            hovermode='x unified',
                            yaxis_title='Portfolio Value (₹)',
                            xaxis_title='Months',
                            legend_title='Growth Scenario'
                        )
                        
                        # Format y-axis values to show as currency
                        fig_proj.update_layout(
                            yaxis=dict(
                                tickformat=',.0f',
                                tickprefix='₹'
                            )
                        )
                        
                        st.plotly_chart(fig_proj, use_container_width=True)
                        
                        # Display final values
                        st.markdown("#### Projected Final Values")
                        final_values = st.columns(3)
                        with final_values[0]:
                            st.metric(
                                "Conservative (8% p.a.)",
                                f"₹{conservative_fv:,.0f}",
                                f"+₹{(conservative_fv - monthly_investment * 12 * projection_years):,.0f}"
                            )
                        with final_values[1]:
                            st.metric(
                                "Moderate (12% p.a.)",
                                f"₹{moderate_fv:,.0f}",
                                f"+₹{(moderate_fv - monthly_investment * 12 * projection_years):,.0f}"
                            )
                        with final_values[2]:
                            st.metric(
                                "Aggressive (15% p.a.)",
                                f"₹{aggressive_fv:,.0f}",
                                f"+₹{(aggressive_fv - monthly_investment * 12 * projection_years):,.0f}"
                            )
                            
                        # Add investment breakdown
                        st.markdown("#### Investment Breakdown")
                        st.info(f"""
                        💰 Total Investment: ₹{monthly_investment * 12 * projection_years:,.0f}
                        📈 Potential Returns (Moderate scenario): ₹{(moderate_fv - monthly_investment * 12 * projection_years):,.0f}
                        🎯 Monthly Investment: ₹{monthly_investment:,.0f}
                        ⏳ Investment Period: {projection_years} years
                        """)
                        

                with tab2:
                    st.markdown("##### Expected Returns Analysis")
                    st.markdown("This chart compares the projected annual returns based on historical performance.")
                    
                    returns_data = {}
                    for ticker, data in hist_data.items():
                        if 'historical_data' in data and isinstance(data['historical_data'], pd.DataFrame):
                            returns_data[ticker] = calculate_expected_return(data['historical_data'])
                    
                    if returns_data:
                        returns_df = pd.DataFrame(list(returns_data.items()), columns=["Investment", "Expected Return"])
                        returns_df = returns_df.sort_values("Expected Return", ascending=False)
                        
                        fig_returns = px.bar(
                            returns_df,
                            x="Investment",
                            y="Expected Return",
                            color="Expected Return",
                            title="Projected Annual Returns",
                            labels={"Expected Return": "Expected Annual Return (%)", "Investment": "Investment Option"},
                            color_continuous_scale=px.colors.sequential.Tealgrn,
                            text_auto='.1f'
                        )
                        fig_returns.update_traces(
                            texttemplate='%{y:.1f}%',
                            textposition='outside'
                        )
                        fig_returns.update_layout(
                            showlegend=False,
                            yaxis_title='Expected Annual Return (%)',
                            xaxis_title='Investment Options'
                        )
                        st.plotly_chart(fig_returns, use_container_width=True)

    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        st.error("Please check your API keys in the .env file, your internet connection, and try again.")



# --- Chatbot UI and Logic ---
# Conditionally render the chatbot as main UI or in sidebar
if st.session_state.show_chatbot:
    # Chatbot as main UI
    st.markdown("---")
    st.markdown("## 💬 Monexa Chat")
    
    # Display chat messages from session state
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Chat input field
    user_input = st.chat_input("Say something to the bot...")
    if user_input:
        # Add user message to session state
        st.session_state.chat_messages.append({"role": "user", "content": user_input})

        with st.spinner("Monexa is typing..."):
            # Get response from Nova
            response_text = get_nova_response(nova_client, user_input)
            # Add assistant response to session state
            st.session_state.chat_messages.append({"role": "assistant", "content": response_text})
        
        # Rerun the app to update the chat history
        st.rerun()
else:
    # --- Main Content Area for Personalized Advice ---
    st.markdown("---")
    st.markdown("## 🎯 Get Personalized Investment Advice")

    if analyze_button:
        # Validate all required inputs
        required_inputs = {
            'investment_type': "Please select an investment type",
            'investment_amount': "Please enter your monthly investment amount",
            'horizon': "Please select your investment horizon",
            'risk': "Please select your risk tolerance level"
        }
        
        missing_inputs = [msg for field, msg in required_inputs.items() 
                         if not user_inputs.get(field)]
        
        if missing_inputs:
            for msg in missing_inputs:
                st.error(msg)
        else:
            # Use a spinner to show that the app is working
            with st.spinner("Monexa AI is crafting your personalized plan..."):
                display_results(user_inputs)
    else:
        st.info("👈 Please fill out your investment profile in the sidebar and click 'Get My Personalized Advice' to begin.")
    # Initial welcome message
        st.info("Please fill out your profile in the sidebar to get started!")
        st.markdown("### How it works:")
        st.markdown("1. **Choose your investment:** Select from Stocks (Indian/US Markets), Mutual Funds, or Cryptocurrency")
        st.markdown("2. **Set your parameters:** Define your investment amount, time horizon, and risk tolerance")
        st.markdown("3. **Get Instant Insights:** Our AI analyzes market data and news to provide personalized recommendations with interactive visualizations")

        # --- Disclaimer ---
        st.markdown("---")
        st.markdown("*Disclaimer: Monexa AI provides information and suggestions based on financial data and AI models. This is not financial advice. Please consult with a qualified financial professional before making any investment decisions.*")