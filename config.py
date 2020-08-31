"""
file - config.py
Place to store needed configurations
"""

# nltk tokens reqs
nltk_tokens_ignored = ("win", 'giveaway')
nltk_tokens_required = ("jeff", "bezos", "jeff bezos", "#amazon", "@amazon", "amazon", "amzn", "#amzn", "alexa", "blue origin", "space")
nltk_min_tokens = 1

# elasticsearch
elasticsearch_host = "localhost"
elasticsearch_port = 9200

# twitter access tokens
consumer_key = "DAWNpchJ1N7D16QShvBQ6vQ1E"
consumer_key_secret = "RKD3FZ2kTw8b7vXjg6U2GNdZ7LMjZgPMENFOKdXjNDhwtjvNFA"
access_token = "1216093106-j2WqgiLWcjEzHLHt4q88PFHUVOfl1Ge1prhUJAj"
access_token_secret = "YN47wTGnnDnXdU1HF2Tgok6nyZLBBs7jN5l4gKZWdpwcw"

# sentiment url
sentiment_url = 'http://text-processing.com/api/sentiment/'
# yahoo stock url
yahoo_stock_url = "https://query1.finance.yahoo.com/v8/finance/chart/SYMBOL?region=US&lang=en-US&includePrePost=false&interval=2m&range=5d&corsDomain=finance.yahoo.com&.tsrc=finance"
# yahoo news url
yahoo_news_url = 'https://finance.yahoo.com/quote/SYMBOL/?p=SYMBOL'
