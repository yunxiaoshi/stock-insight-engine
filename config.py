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

# put your twitter access credentials here
consumer_key = ""
consumer_key_secret = ""
access_token = ""
access_token_secret = ""

# sentiment url
sentiment_url = 'http://text-processing.com/api/sentiment/'
# yahoo stock url
yahoo_stock_url = "https://query1.finance.yahoo.com/v8/finance/chart/SYMBOL?region=US&lang=en-US&includePrePost=false&interval=2m&range=5d&corsDomain=finance.yahoo.com&.tsrc=finance"
# yahoo news url
yahoo_news_url = 'https://finance.yahoo.com/quote/SYMBOL/?p=SYMBOL'
