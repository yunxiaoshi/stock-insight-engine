"""
file - parsing.py
Implements a utility class that cleans up text and performs sentiment analysis
"""

import re
import requests
import string
import urllib.parse as urlparse

from bs4 import BeautifulSoup
import nltk
from newspaper import Article, ArticleException
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from config import nltk_min_tokens, nltk_tokens_required, nltk_tokens_ignored

class ParsingUtils:
    """
    A utility class that computes sentiment for text
    """
    def __init__(self, sentiment_url, logger, web_sentiment=False, 
                 verbose=False):
        """
        sentiment_url: 'http://text-processing.com/api/sentiment/' for online sentiment parsing
        """
        self.sentiment_url = sentiment_url
        self.logger = logger
        self.web_sentiment = web_sentiment
        self.verbose = verbose
        
    def clean_text(self, text):
        # clean up text
        text = text.replace('\n', ' ')
        text = re.sub(r'https?\S+', '', text)
        text = re.sub(r'&.*?;', '', text)
        text = re.sub(r'<.*?>', '', text)
        text = text.replace('RT', '')
        text = text.replace(u'...', '')
        text = text.strip()
        return text

    def clean_text_sentiment(self, text):
        # clean up text for sentiment analysis
        text = re.sub(r'[#|@]\S+', '', text)
        text = text.strip()
        return text
    
    def create_tokens_from_text(self, text):    
        text_tokens = re.sub(r"[\%|\$|\.|\,|\!|\:|\@|\(|\)|\#|\+|(``)|('')|\?|\-]", "", text)
        tokens = nltk.word_tokenize(text_tokens)
        tokens = [w.lower() for w in tokens]
        table = str.maketrans('', '', string.punctuation)
        stripped = [w.translate(table) for w in tokens]
        tokens = [w for w in stripped if w.isalpha()]
        stop_words = set(nltk.corpus.stopwords.words('english'))
        tokens = [w for w in tokens if not w in stop_words]
        # remove words less than 3 characters
        tokens = [w for w in tokens if not len(w) < 3]
        return tokens

    def get_sentiment_from_url(self, text):
        # get sentiment from text processing website
        payload = {'text': text}

        try:
            self.logger.debug(text)
            post = requests.post(self.sentiment_url, data=payload)
            self.logger.debug(post.status_code)
            self.logger.debug(post.text)

        except requests.exceptions.RequestException as re:
            self.logger.error('Exception occurred when getting sentiment from %s caused by %s' % (self.sentiment_url, re))
            raise

        # return None if getting throttled or other connection problem
        if post.status_code != 200:
            self.logger.warning('Can\'t get sentiment from %s caused by %s %s' % (self.sentiment_url, post.status_code, post.text))
            return None

        response = post.json()

        neg = response['probability']['neg']
        pos = response['probability']['pos']
        neu = response['probability']['neutral']
        label = response['label']

        # determine if sentiment is positive, negative or neutral
        if label == 'neg':
            sentiment = 'negative'
        elif label == 'neutral':
            sentiment = 'neutral'
        else:
            sentiment = 'positive'

        return sentiment, neg, pos, neu

    def sentiment_analysis(self, text):
        """
        utility leveraging TextBlob, VADERSentiment and sentiment from text-processing.com
        """
        # pass text into sentiment url
        if self.web_sentiment:
            ret = self.get_sentiment_from_url(text)
            if not ret:
                sentiment_web = None
            else:
                sentiment_web, _, _, _ = ret
        else:
            sentiment_web = None

        # pass text into TextBlob
        if not isinstance(text, str):
            text = str(text)
        text_tb = TextBlob(text)

        # pass text into VADER sentiment
        analyzer = SentimentIntensityAnalyzer()
        text_vs = analyzer.polarity_scores(text)

        # determine sentiment
        if not sentiment_web:
            if text_tb.sentiment.polarity < 0 and text_vs['compound'] <= -0.05:
                sentiment = 'negative'
            elif text_tb.sentiment.polarity > 0  and text_vs['compound'] >= 0.05:
                sentiment = 'positive'
            else:
                sentiment = 'neutral'
        else:
            if text_tb.sentiment.polarity < 0 and text_vs['compound'] <= -0.05 and sentiment_web == 'negative':
                sentiment = 'negative'
            elif text_tb.sentiment.polarity > 0 and text_vs['compound'] >=0.05 and sentiment_web == 'positive':
                sentiment = 'positive'
            else:
                sentiment = 'neutral'

        # calculate average polarity from TextBlob and VADER
        polarity = (text_tb.sentiment.polarity + text_vs['compound']) / 2

        return polarity, text_tb.sentiment.subjectivity, sentiment

    def tweet_link_sentiment_analysis(self, url):
        # run sentiment analysis on tweet link text summary page
        try:
            self.logger.info('Following tweet link %s to get sentiment...' % url)
            article = Article(url)
            article.download()
            article.parse()
            if 'Tweet with a location' in article.text:
                self.logger.info('Link to a twitter web page, skipping')
                return None
            article.nlp()
            tokens = article.keywords

            if len(tokens) < 1:
                self.logger.info('Text does not have min number of tokens, skipping')
                return None
            # check ignored tokens from config
            for t in nltk_tokens_ignored:
                if t in tokens:
                    self.logger.info('Text contains token from ignored list, skipping')
                    return None
            # check required tokens from config
            tokens_passed = False
            tokens_found = 0
            for t in nltk_tokens_required:
                if t in tokens:
                    tokens_found += 1
                    if tokens_found == nltk_min_tokens:
                        tokens_passed = True
                        break
            if not tokens_passed:
                self.logger.info('Text does not contain any required token, skipping')
                return None

            summary = article.summary
            if not summary:
                self.logger.info('No text found in tweet link url page')
                return None

            summary_cleaned = self.clean_text(summary)
            summary_cleaned = self.clean_text_sentiment(summary_cleaned)
            polarity, subjectivity, sentiment = self.sentiment_analysis(summary_cleaned)

            return polarity, subjectivity, sentiment

        except ArticleException as e:
            self.logger.warning('Exception: error getting text on twitter link caused by %s' % e)
            return None

    def get_twitter_users_from_url(self, url):
        twitter_users = []
        self.logger.info('grabbing twitter users from url %s' % url)
        try:
            twitter_urls = ('http://twitter.com/', 'http://www.twitter.com/', 
            'https://www.twitter.com', 'https://www.twitter.com')
            req = requests.get(url)
            html = req.text
            soup = BeautifulSoup(html, 'html.parser')
            html_links = []
            for link in soup.findAll('a'):
                html_links.append(link.get('href'))
            if html_links:
                for link in html_links:
                    # check if there is twitter url in link
                    parsed_uri = urlparse.urljoin(link, '/')
                    # get twitter user-name from link and add to list
                    if parsed_uri in twitter_urls and '=' not in link and '?' not in link:
                        user = link.split('/')[3]
                        twitter_users.append(u'@' + user)
                    self.logger.debug(twitter_users)
        except requests.exceptions.RequestException as re:
            self.logger.warning('Can\'t crawl web site caused by %s' % re)
            pass

        return twitter_users
    