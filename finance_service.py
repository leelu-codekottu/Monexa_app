import yfinance as yf
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime
import time
from typing import Dict, Optional, List, Union, Any
from forex_python.converter import CurrencyRates
import datetime

# Constants for market data
INDIAN_TOP_STOCKS = [
    'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
    'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'BAJFINANCE.NS'
]

US_TOP_STOCKS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 
    'META', 'BRK-B', 'JPM', 'V', 'TSLA'
]

cr = CurrencyRates()

def convert_to_inr(amount: float, from_currency: str = 'USD') -> float:
    """Convert any currency to INR"""
    try:
        if from_currency == 'INR':
            return amount
        rate = cr.get_rate(from_currency, 'INR')
        return amount * rate
    except Exception as e:
        print(f"Error converting currency: {str(e)}")
        return amount  # Return original amount if conversion fails

def calculate_expected_return(data: pd.DataFrame) -> float:
    """
    Calculates the expected annual return based on historical data.
    
    Args:
        data: DataFrame with historical price data containing 'Close' column
        
    Returns:
        float: The annualized expected return as a percentage
    """
    if data is None or data.empty:
        return 0.0
        
    try:
        # Calculate log returns
        prices = data['Close'].dropna()
        log_returns = np.log(prices / prices.shift(1)).dropna()
        
        if len(log_returns) < 30:  # Need enough data points
            return 0.0
            
        # Annualize the mean return (252 trading days)
        mu_daily = log_returns.mean()
        annual_return = (np.exp(mu_daily * 252) - 1) * 100
        
        # Ensure return is within reasonable bounds
        return max(min(annual_return, 100.0), -100.0)
        
    except Exception as e:
        print(f"Error calculating return: {str(e)}")
        return 0.0

def get_top_stocks(market: str = 'INDIA') -> List[str]:
    """Get list of top stocks for the specified market"""
    return INDIAN_TOP_STOCKS if market.upper() == 'INDIA' else US_TOP_STOCKS

def get_financial_data(tickers: Union[str, List[str]], period: str = "1y", market: str = 'INDIA') -> Dict:
    """
    Fetches historical market data for one or more tickers using parallel requests.
    
    Args:
        tickers: Single ticker string or list of stock/crypto tickers
        period: The period for which to fetch data (e.g., "1d", "5d", "1mo", "1y", "5y", "max")
        market: Market to fetch data from ('INDIA' or 'US')

    Returns:
        Dict with ticker data including current price, changes, and historical data in INR
    """
    # Convert single ticker to list
    if isinstance(tickers, str):
        tickers = [tickers]
    
    if not tickers:
        return {}
    
    def fetch_single_ticker(ticker: str) -> Optional[Dict]:
        """Fetches data for a single ticker with robust error handling"""
        try:
            print(f"Fetching data for {ticker}...")
            stock = yf.Ticker(ticker)
            info = stock.info
            hist = stock.history(period=period)
            
            if hist.empty:
                print(f"No data found for {ticker}")
                return None
                
            # Ensure we have the required columns
            required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            if not all(col in hist.columns for col in required_cols):
                print(f"Missing required columns for {ticker}")
                return None
                
            # Determine currency and convert if needed
            currency = info.get('currency', 'USD') if '.NS' not in ticker else 'INR'
            
            # Convert price data to INR if necessary
            if currency != 'INR':
                conversion_rate = cr.get_rate(currency, 'INR')
                for col in ['Open', 'High', 'Low', 'Close']:
                    hist[col] = hist[col] * conversion_rate
                    
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
                'name': info.get('longName', info.get('shortName', ticker)),
                'currency': 'INR',  # All values are converted to INR
                'current_price': float(current),
                'price_change': float(change),
                'high_52week': float(high_52w),
                'low_52week': float(low_52w),
                'avg_volume': float(avg_vol),
                'expected_return': exp_return,
                'historical_data': hist_clean.reset_index(),  # Reset index to make date a column
                'sector': info.get('sector', 'N/A'),
                'industry': info.get('industry', 'N/A')
            }
        except Exception as e:
            print(f"Error fetching {ticker}: {str(e)}")
            return None
    
    # Execute parallel requests
    results = {}
    with ThreadPoolExecutor(max_workers=min(len(tickers), 5)) as executor:
        future_to_ticker = {
            executor.submit(fetch_single_ticker, ticker): ticker 
            for ticker in tickers
        }
        
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
    Fetches detailed information for a single ticker.

    Args:
        ticker: The stock/crypto ticker symbol

    Returns:
        Clean dictionary of ticker info or None if invalid
    """
    try:
        print(f"Fetching info for {ticker}...")
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Clean up the info dictionary
        if not info:
            return None
            
        # Get currency and convert monetary values to INR
        currency = info.get('currency', 'USD') if '.NS' not in ticker else 'INR'
        conversion_rate = 1.0 if currency == 'INR' else cr.get_rate(currency, 'INR')
        
        # Return the most relevant fields with converted values
        relevant_fields = {
            'symbol': info.get('symbol'),
            'shortName': info.get('shortName'),
            'longName': info.get('longName'),
            'sector': info.get('sector'),
            'industry': info.get('industry'),
            'website': info.get('website'),
            'market': info.get('market'),
            'marketCap': info.get('marketCap', 0) * conversion_rate if info.get('marketCap') else None,
            'volume': info.get('volume'),
            'currency': 'INR',  # Always show INR as we convert all values
            'description': info.get('longBusinessSummary'),
            'pe_ratio': info.get('forwardPE', info.get('trailingPE', 'N/A')),
            'dividend_yield': info.get('dividendYield', 0),
            'beta': info.get('beta', 'N/A'),
            'regular_market_price': info.get('regularMarketPrice', 0) * conversion_rate if info.get('regularMarketPrice') else 0,
            'regular_market_change_percent': info.get('regularMarketChangePercent', 0)
        }
        
        return {k: v for k, v in relevant_fields.items() if v is not None}
        
    except Exception as e:
        print(f"Error fetching info for {ticker}: {str(e)}")
        return None

