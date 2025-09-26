import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, List, Union, Any
import numpy as np

def calculate_expected_return(historical_prices: pd.DataFrame) -> float:
    """Calculate expected return based on historical price data"""
    if historical_prices.empty:
        return 0.0
    try:
        returns = historical_prices['Close'].pct_change().dropna()
        return float(returns.mean() * 252)  # Annualized return
    except Exception:
        return 0.0

def get_financial_data(tickers: Union[str, List[str]], period: str = "1y") -> Dict:
    """
    Fetches historical market data for one or more tickers using parallel requests.
    
    Args:
        tickers: Single ticker string or list of stock/crypto tickers
        period: The period for which to fetch data (e.g., "1d", "5d", "1mo", "1y", "5y", "max")

    Returns:
        Dict with ticker data including current price, changes, and historical data
    """
    if isinstance(tickers, str):
        tickers = [tickers]
    
    if not tickers:
        return {}
        
    def fetch_single_ticker(ticker: str) -> Optional[Dict]:
        try:
            print(f"Fetching data for {ticker}...")  # Debug log
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period)
            
            if hist.empty:
                print(f"No data found for {ticker}")
                return None
                
            # Ensure we have the required columns
            required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            if not all(col in hist.columns for col in required_cols):
                print(f"Missing required columns for {ticker}")
                return None
                
            current = hist['Close'][-1]
            start = hist['Close'][0]
            change = ((current - start) / start) * 100
            
            # Calculate additional metrics
            high_52w = hist['High'].max()
            low_52w = hist['Low'].min()
            avg_vol = hist['Volume'].mean()
            exp_return = calculate_expected_return(hist)
            
            # For visualization data, make sure all NaN values are handled
            hist_clean = hist.copy()
            hist_clean.fillna(method='ffill', inplace=True)  # Forward fill
            hist_clean.fillna(method='bfill', inplace=True)  # Back fill any remaining
            
            return {
                'ticker': ticker,
                'current_price': float(current),
                'price_change': float(change),
                'high_52week': float(high_52w),
                'low_52week': float(low_52w),
                'avg_volume': float(avg_vol),
                'expected_return': exp_return,
                'historical_data': hist_clean.reset_index()  # Reset index to make date a column
            }
            
        except Exception as e:
            print(f"Error fetching {ticker}: {str(e)}")
            return None
    
    # Execute parallel requests
    with ThreadPoolExecutor(max_workers=min(len(tickers), 5)) as executor:
        future_to_ticker = {executor.submit(fetch_single_ticker, ticker): ticker for ticker in tickers}
        
        results = {}
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                data = future.result()
                if data:
                    results[ticker] = data
            except Exception as e:
                print(f"Error processing {ticker}: {str(e)}")
    
    return results

def get_ticker_info(ticker: str) -> Optional[Dict]:
    """
    Fetches detailed information for a single ticker with better error handling
    and cleaned response data.

    Args:
        ticker: The stock/crypto ticker symbol

    Returns:
        Optional[Dict]: Clean dictionary of ticker info or None if invalid
    """
    try:
        print(f"Fetching info for {ticker}...")
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Clean up the info dictionary
        if not info:
            return None
            
        # Return only the most relevant fields
        relevant_fields = {
            'symbol': info.get('symbol'),
            'shortName': info.get('shortName'),
            'longName': info.get('longName'),
            'sector': info.get('sector'),
            'industry': info.get('industry'),
            'website': info.get('website'),
            'market': info.get('market'),
            'marketCap': info.get('marketCap'),
            'volume': info.get('volume'),
            'currency': info.get('currency'),
            'description': info.get('longBusinessSummary')
        }
        
        return {k: v for k, v in relevant_fields.items() if v is not None}
        
    except Exception as e:
        print(f"Error fetching info for {ticker}: {str(e)}")
        return None