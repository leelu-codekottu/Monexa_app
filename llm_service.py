import os
import traceback
from dotenv import load_dotenv

# Attempt to robustly load .env from the project root
try:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(project_root, '.env')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)
    else:
        load_dotenv()
except Exception as e:
    print(f"Warning: Could not load .env file. Ensure it is in the project root. Error: {e}")

# Try to import and configure the Google generative AI client, but fail gracefully
genai = None
GENAI_CONFIGURED = False
try:
    import google.generativeai as genai_module
    genai = genai_module
    API_KEY = os.getenv("GOOGLE_API_KEY")
    if API_KEY:
        try:
            genai.configure(api_key=API_KEY)
            GENAI_CONFIGURED = True
        except Exception as e:
            print(f"Warning: genai.configure failed: {e}")
    else:
        print("Warning: GOOGLE_API_KEY not found in environment variables. LLM will operate in fallback mode.")
except Exception as e:
    print(f"Warning: google.generativeai import failed: {e}")


def _local_fallback_response(user_inputs, financial_data_context, news_context):
    """Generate a detailed response without using external LLM service"""
    try:
        # Extract user inputs
        investment_type = user_inputs.get('investment_type', 'Stocks')
        risk_level = user_inputs.get('risk', 'Medium Risk')
        investment_amount = user_inputs.get('investment_amount', 5000)
        horizon = user_inputs.get('horizon', 10)
        market = user_inputs.get('market', 'Indian Market')

        # Parse financial context
        market_data = {}
        if 'Market Data:' in financial_data_context:
            lines = financial_data_context.split('\n')[1:]  # Skip header
            for line in lines:
                if ':' in line:
                    ticker, data = line.split(':', 1)
                    market_data[ticker.strip()] = data.strip()

        # Generate personalized response
        response = f"""### Investment Analysis Summary

#### Your Investment Profile
- **Investment Type**: {investment_type}
- **Risk Level**: {risk_level}
- **Monthly Investment**: ₹{investment_amount:,}
- **Time Horizon**: {horizon} years
- **Preferred Market**: {market}

#### Market Analysis
Based on current market conditions and your risk profile, here's our analysis:

"""
        # Add risk-based recommendations
        if risk_level == "Low Risk":
            response += """
🔹 **Conservative Strategy Recommended**
- Focus on blue-chip companies with stable dividends
- Consider large-cap mutual funds
- Maintain 70-30 split between equity and debt
- Look for companies with strong fundamentals and consistent performance
"""
        elif risk_level == "Medium Risk":
            response += """
🔸 **Balanced Strategy Recommended**
- Mix of growth stocks and value stocks
- Consider mid-cap mutual funds for growth potential
- Maintain 60-40 split between equity and growth stocks
- Look for companies showing steady growth and innovation
"""
        else:  # High Risk
            response += """
🔺 **Growth Strategy Recommended**
- Focus on high-growth potential stocks
- Consider small-cap and sector-specific funds
- Higher allocation to emerging sectors
- Look for companies with disruptive potential
"""

        # Add market-specific recommendations
        if market_data:
            response += "\n#### Current Market Opportunities\n"
            for ticker, data in list(market_data.items())[:3]:
                response += f"- **{ticker}**: {data}\n"

        # Add news-based insights
        if "error" not in news_context:
            response += "\n#### Recent Market Developments\n" + news_context[:500] + "..."

        # Add future projections
        monthly_investment = float(investment_amount)
        years = int(horizon)
        conservative_return = 0.08  # 8% annual return
        moderate_return = 0.12      # 12% annual return
        aggressive_return = 0.15    # 15% annual return

        future_conservative = monthly_investment * 12 * ((1 + conservative_return) ** years)
        future_moderate = monthly_investment * 12 * ((1 + moderate_return) ** years)
        future_aggressive = monthly_investment * 12 * ((1 + aggressive_return) ** years)

        response += f"""
#### Potential Future Outcomes
Based on your monthly investment of ₹{investment_amount:,} over {horizon} years:

- Conservative Estimate (8% p.a.): ₹{future_conservative:,.0f}
- Moderate Estimate (12% p.a.): ₹{future_moderate:,.0f}
- Aggressive Estimate (15% p.a.): ₹{future_aggressive:,.0f}

#### Next Steps:
1. 📈 Start with a diversified portfolio based on your risk profile
2. 🔄 Set up automatic monthly investments of ₹{investment_amount:,}
3. 📊 Review and rebalance your portfolio quarterly

*Note: These are algorithmic recommendations based on historical data and market analysis. Please consult with a qualified financial advisor before making investment decisions.*
"""
        return response
    except Exception:
        return "Fallback: Unable to generate LLM response due to internal error."


def get_llm_response(user_inputs, financial_data_context, news_context):
    """
    Generates a personalized financial plan using the Gemini API when available.
    Falls back to a safe local response if the API key or client is missing.
    """
    if not GENAI_CONFIGURED or genai is None:
        return _local_fallback_response(user_inputs, financial_data_context, news_context)

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')

        # Constructing a detailed prompt for the LLM
        prompt = f"""
        **Role**: You are Monexa, an expert AI Financial Advisor. Your tone is encouraging, clear, and professional. Avoid overly technical jargon.

        **User Profile**:
        - **Primary Goal**: {user_inputs.get('goal', 'Not specified')}
        - **Monthly Savings**: ${user_inputs.get('savings', 'Not specified')}
        - **Time Horizon**: {user_inputs.get('horizon', 'Not specified')} years
        - **Risk Tolerance**: {user_inputs.get('risk', 'Not specified')}
        - **Specific Tickers of Interest**: {', '.join(user_inputs.get('tickers', [])) if user_inputs.get('tickers') else 'None'}

        **Market Context**:
        - **Recent Financial News Summary**: {news_context}
        - **Relevant Data Points**: {financial_data_context}

        **Your Task**:
        Based on the user's profile and the current market context, provide a personalized financial plan. Structure your response in Markdown with the following sections:

        1.  **Summary of Your Situation**: Briefly summarize the user's goals and profile in a friendly, easy-to-understand paragraph.
        2.  **Personalized Recommendations**: Provide actionable advice based on their goal.
            - If **Investing**: Suggest a diversified portfolio strategy. Mention specific types of assets (like ETFs, stocks, crypto) that align with their risk tolerance. Explain *why* these are good choices. For example, for a 'Low' risk user, you might suggest broad-market ETFs like VOO and bonds. For a 'High' risk user, you could mention growth stocks or a small allocation to crypto.
            - If **Saving**: Suggest high-yield savings accounts, CDs, or other low-risk vehicles. Provide tips on budgeting and reaching their savings goal.
            - If **Getting a Loan**: Briefly explain key factors to consider, like credit scores, debt-to-income ratio, and comparing interest rates from different lenders. Suggest types of loans that might be appropriate (e.g., personal loan, mortgage).
        3.  **Next Steps**: Conclude with 2-3 clear, bulleted next steps the user can take.
        4. According to the present market condition and the trends using the news context of finanacial news , suggest recommendated stocks with reasons

        **IMPORTANT**: Do not give definitive financial advice. Use phrases like "You might consider...", "A common strategy is...", or "It could be beneficial to look into...". Always remind the user to consult a human financial advisor.
        """

        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        print(f"An error occurred in get_llm_response: {e}\n{traceback.format_exc()}")
        return _local_fallback_response(user_inputs, financial_data_context, news_context)