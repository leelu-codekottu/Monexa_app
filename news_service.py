import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

def get_financial_news(query="finance"):
    """
    Fetches top financial news articles from the News API.
    Falls back to cached news if API fails.

    Args:
        query (str): The search term for news articles.

    Returns:
        list: A list of dictionaries, where each dictionary is a news article.
    """
    # Fallback news data in case API fails
    fallback_news = [
        {
            "title": "Indian Stock Market Reaches New Heights",
            "description": "The Indian stock market continues its bullish trend with Sensex and Nifty touching new records. Strong domestic economic indicators and global market stability contributing to the growth.",
            "source": "Market Analysis",
            "published": datetime.now().strftime("%Y-%m-%d"),
            "url": "https://www.moneycontrol.com"
        },
        {
            "title": "Tech Stocks Lead Global Market Rally",
            "description": "Technology sector stocks show strong performance globally. AI and cloud computing companies leading the charge with substantial gains.",
            "source": "Financial Times",
            "published": datetime.now().strftime("%Y-%m-%d"),
            "url": "https://www.ft.com"
        },
        {
            "title": "RBI Maintains Policy Stance",
            "description": "Reserve Bank of India keeps key rates unchanged in its latest monetary policy meeting. Inflation control remains priority while supporting growth.",
            "source": "Economic Times",
            "published": datetime.now().strftime("%Y-%m-%d"),
            "url": "https://economictimes.indiatimes.com"
        },
        {
            "title": "Cryptocurrency Market Shows Recovery",
            "description": "Bitcoin and other major cryptocurrencies demonstrate strong recovery signals. Institutional adoption continues to grow despite regulatory challenges.",
            "source": "Crypto News",
            "published": datetime.now().strftime("%Y-%m-%d"),
            "url": "https://www.coindesk.com"
        },
        {
            "title": "Oil Prices Impact Global Markets",
            "description": "Fluctuations in global oil prices creating market volatility. Energy sector stocks showing mixed responses to the changing dynamics.",
            "source": "Reuters",
            "published": datetime.now().strftime("%Y-%m-%d"),
            "url": "https://www.reuters.com"
        }
    ]

    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        print("NEWSAPI_KEY not found in .env file, using fallback news.")
        return fallback_news

    # Use everything endpoint for broader search
    url = "https://newsapi.org/v2/everything"
    
    # Calculate date range (last 24 hours for fresh content)
    end_date = datetime.now()
    start_date = end_date - timedelta(hours=24)
    
    params = {
        'q': '(stock market OR financial markets OR investing OR finance) AND (analysis OR forecast OR outlook)',
        'language': 'en',
        'sortBy': 'publishedAt',  # Get most recent news first
        'from': start_date.strftime('%Y-%m-%d'),
        'to': end_date.strftime('%Y-%m-%d'),
        'apiKey': api_key,
        'pageSize': 10  # Request 10 articles to ensure we get enough good ones
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        
        if data.get('status') != 'ok':
            print(f"NewsAPI Error: {data.get('message', 'Unknown error')}")
            return {"error": data.get('message', 'Failed to fetch news')}
            
        articles = data.get("articles", [])
        
        # Filter and clean articles
        top_articles = []
        seen_titles = set()  # To avoid duplicates
        
        for article in articles:
            title = article.get("title", "").strip()
            desc = article.get("description", "").strip()
            
            # Skip articles without title or description
            if not title or not desc:
                continue
                
            # Skip duplicates
            if title in seen_titles:
                continue
                
            seen_titles.add(title)
            
            top_articles.append({
                "title": title,
                "description": desc,
                "url": article.get("url", ""),
                "source": article.get("source", {}).get("name", "Unknown"),
                "published": article.get("publishedAt", "")
            })
            
            # Stop after getting 5 good articles
            if len(top_articles) >= 5:
                break
                
        return top_articles

    except requests.exceptions.RequestException as e:
        print(f"Error fetching news: {e}")
        return {"error": f"Could not fetch news. Please check your connection and API key. Error: {e}"}
    except Exception as e:
        print(f"An unexpected error occurred in get_financial_news: {e}")
        return {"error": f"An unexpected error occurred: {e}"}

def extract_key_points(text):
    """Helper function to extract key financial points from text"""
    # Common financial terms to look for
    key_terms = [
        'market', 'stock', 'index', 'growth', 'decline', 'percent', 'rate',
        'economy', 'inflation', 'recession', 'investors', 'trading', 'price',
        'earnings', 'forecast', 'outlook', 'analysis'
    ]
    
    # Split into sentences and look for ones with key terms
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    key_sentences = []
    
    for sentence in sentences:
        if any(term in sentence.lower() for term in key_terms):
            key_sentences.append(sentence)
    
    return '. '.join(key_sentences)

def summarize_news_for_llm(articles):
    """
    Creates a detailed summary of news articles for the LLM, focusing on extracting
    actionable financial insights and market context.
    """
    if not articles or "error" in articles:
        return "No financial news could be retrieved at this time."

    summary = []
    summary.append("Current Market Context and News Analysis:\n")
    
    for i, article in enumerate(articles, 1):
        # Get all possible content
        title = article['title'].strip()
        desc = article.get('description', '').strip()
        source = article['source']
        date = article.get('published', '').split('T')[0]  # Just the date part
        
        # Extract key points from both title and description
        content = f"{title}. {desc}"
        key_points = extract_key_points(content)
        
        if key_points:
            summary.append(f"{i}. Key Market Insight ({source}, {date}):")
            summary.append(f"   {key_points}")
            
            # Add any numerical data or percentages if found
            numbers = [word for word in content.split() if any(c.isdigit() for c in word)]
            if numbers:
                relevant_numbers = [n for n in numbers if '%' in n or '$' in n or any(term in content.lower() for term in ['up', 'down', 'rose', 'fell', 'increased', 'decreased'])]
                if relevant_numbers:
                    summary.append(f"   Relevant Metrics: {', '.join(relevant_numbers)}")
            
            summary.append("")  # Empty line for readability
    
    if len(summary) <= 2:  # Only has the header
        return "No substantial financial insights could be extracted from the news at this time."
        
    return "\n".join(summary)