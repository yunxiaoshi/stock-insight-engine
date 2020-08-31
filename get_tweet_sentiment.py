"""
file - sentiment.py
Analyze tweets with sentiment analysis and add to Elasticsearch
"""

import argparse
import datetime
import json
import logging
import nltk
import re
import requests
import random
import string
import time
import sys
import urllib.parse as urlparse

from bs4 import BeautifulSoup
from elasticsearch import Elasticsearch
from newspaper import Article, ArticleException
from tweepy import API, Stream, OAuthHandler, TweepError
from tweepy.streaming import StreamListener
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from parsing import ParsingUtils

from config import nltk_min_tokens, nltk_tokens_required, nltk_tokens_ignored
from config import consumer_key, consumer_key_secret, access_token, access_token_secret
from config import elasticsearch_host, elasticsearch_port
from config import sentiment_url, yahoo_news_url
                    
class TweetStreamListener(StreamListener):

    def __init__(self, parsing_utils, verbose=False):
        self.count = 0
        self.filtered_count = 0
        self.filtered_ratio = 0.
        self.tweet_ids = []
        self.parsing_utils = parsing_utils
        self.verbose = verbose

    # on success
    def on_data(self, data):
        try:
            self.count += 1
            # decode json
            dict_data = json.loads(data)

            if self.verbose:
                print('################ tweets: %d | filtered: %d | filtered-ratio: %.2f' % (
                    self.count, self.filtered_count, self.filtered_count / self.count))
            logger.debug('tweet data: %s' % str(dict_data))

            text = dict_data['text']
            if not text:
                logger.info('Tweet has no text, skipping')
                self.filtered_count += 1
                return True

            # extract html links from tweet
            tweet_urls = []
            if args.link_sentiment:
                tweet_urls = re.findall(r'https?://[^\s]+', text)

            # clean up tweet text
            text_cleaned = self.parsing_utils.clean_text(text)

            if not text_cleaned:
                logger.info('Tweet does not contain any valid text, skipping')
                self.filtered_count += 1
                return True

            # get date when tweet was created
            created_date = time.strftime('%Y-%m-%dT%H:%M:%S', time.strptime(dict_data['created_at'], 
            '%a %b %d %H:%M:%S +0000 %Y'))

            # unpack dict_data into separate vars
            screen_name = str(dict_data.get('user', {}).get('screen_name'))
            location = str(dict_data.get('user', {}).get('location'))
            language = str(dict_data.get('user', {}).get('lang'))
            friends = int(dict_data.get('user', {}).get('friends_count'))
            followers = int(dict_data.get('user', {}).get('followers_count'))
            statuses = int(dict_data.get('user', {}).get('statuses_count'))
            hashtags = str(dict_data.get('entities', {})['hashtags'][0]['text'].title()
                           ) if len(dict_data.get('entities', {})['hashtags']) > 0 else ""
            filtered_text = str(text_cleaned)
            tweet_id = int(dict_data.get('id'))
            
            tokens = self.parsing_utils.create_tokens_from_text(filtered_text)
            
            # check for min token length
            if not tokens:
                logger.info('Empty tokens from tweet, skipping')
                self.filtered_count += 1
                return True
            # check ignored tokens from config
            for t in nltk_tokens_ignored:
                if t in tokens:
                    logger.info('Tweet contains tokens from ignored list, skipping')
                    self.filtered_count += 1
                    return True
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
                logger.info('Tweet does not contain tokens from required tokens list or min tokens required, skipping')
                self.filtered_count += 1
                return True

            # clean up text for sentiment analysis
            text_cleaned_for_sentiment = self.parsing_utils.clean_text_sentiment(filtered_text)
            if not text_cleaned_for_sentiment:
                logger.info('Tweet does not contain any valid text after cleaning, skipping')
                self.filtered_count += 1

            if self.verbose:
                print('Tweet cleaned for sentiment analysis: %s' % text_cleaned_for_sentiment)

            # get sentiment values
            polarity, subjectivity, sentiment = self.parsing_utils.sentiment_analysis(text_cleaned_for_sentiment)

            # add tweet_id to tweet_ids
            self.tweet_ids.append(dict_data['id'])

            # get sentiment for tweet
            if tweet_urls:
                tweet_urls_polarity = 0
                tweet_urls_subjectivity = 0
                for url in tweet_urls:
                    res = self.parsing_utils.tweet_link_sentiment_analysis(url)
                    if not res:
                        continue
                    pol, sub, sen = res
                    tweet_urls_polarity = (tweet_urls_polarity + pol) / 2
                    tweet_urls_subjectivity = (tweet_urls_subjectivity + sub) / 2
                    if sentiment == 'positive' or sen == 'positive':
                        sentiment == 'postive'
                    elif sentiment == 'negative' or sen == 'negative':
                        sentiment == 'negative'
                    else:
                        sentiment == 'neutral'
                # calculate average polarity and subjectivity from tweet and tweet links
                if tweet_urls_polarity > 0:
                    polarity = (polarity + tweet_urls_polarity) / 2
                if tweet_urls_subjectivity > 0:
                    subjectivity = (subjectivity + tweet_urls_subjectivity) / 2

            logger.info('Adding tweet to elasticsearch')
            # add twitter data and sentiment info into elasticsearch
            es.index(index=args.index, 
            doc_type='tweet', 
            body={
                'author': screen_name, 
                'location': location, 
                'language': language, 
                'friends': friends, 
                'followers': followers, 
                'statuses': statuses, 
                'date': created_date, 
                'message': filtered_text, 
                'tweet_id': tweet_id, 
                'polarity': polarity, 
                'subjectivity': subjectivity, 
                'sentiment': sentiment, 
                'hashtags': hashtags
            })
            return True

        except Exception as e:
            logger.warning('Exception: exception caused by: %s' % e)
            raise
    
    # on failure
    def on_error(self, status_code):
        logger.error('Got an error with status code: %s (will try again later)' % status_code)

    # on timeout
    def on_timeout(self):
        logger.warning('timeout... (will try again later)')
        
    # on exception
    def on_exception(self, exception):
        print(exception)
        return         

if __name__ == '__main__':

    parser = argparse.ArgumentParser()

    parser.add_argument('-i', '--index', default='stock-tweet', help='index name for elasticsearch')
    parser.add_argument('-s', '--symbol', required=True, help='Stock symbol to search for, e.g. TSLA')
    parser.add_argument('-k', '--keywords', required=True, 
                        help='Use keywords to search in tweets instead of feeds. '
                        'Separated by commas, case senstitive, space are ANDs and commas are ORs. '
                        'Example: TSLA,\'Elon Musk\',Musk,Tesla,SpaceX')
    parser.add_argument('-a', '--add_tokens', action='store_true',  
                        help='Add nltk tokens required from config to keywords')
    parser.add_argument('-u', '--url', help='Use twitter users from any links in web page at url')
    parser.add_argument('-l', '--link_sentiment', action='store_true', 
                        help='Follow any link url in tweets and analyze sentiments on web page')
    parser.add_argument('-w', '--web_sentiment', action='store_true', 
                        help='Get sentiment results from text processing website')
    parser.add_argument('--override_tokens_required', nargs='+', 
                        help='Override nltk required tokens from config, separate with space')
    parser.add_argument('--override_tokens_ignored', nargs='+', 
                        help='Override nltk ignored token from config, separate with space')
    parser.add_argument('-v', '--verbose', action='store_true', help='Increase output verbosity')
    parser.add_argument('-q', '--quiet', action='store_true', help='Run quiet without message output')
    parser.add_argument('--debug', action='store_true', help='debug message output')
    
    args = parser.parse_args()
    
    # set up logging
    logger = logging.getLogger('stock-tweets')
    logger.setLevel(logging.INFO)
    
    logging.addLevelName(logging.INFO, '\033[1;32m%s\033[1;0m' 
                         % logging.getLevelName(logging.INFO))
    logging.addLevelName(logging.WARNING, '\033[1;31m%s\033[1;0m' 
                         % logging.getLevelName(logging.WARNING))
    logging.addLevelName(logging.ERROR, '\033[1;41m%s\033[1;0m' 
                         % logging.getLevelName(logging.WARNING))
    logging.addLevelName(logging.DEBUG, '\033[1;33m%s\033[1;0m' 
                         % logging.getLevelName(logging.DEBUG))
    
    log_format = '%(asctime)s [%(levelname)s][%(name)s] %(message)s'
    log_level = logging.INFO
    logging.basicConfig(format=log_format, level=log_level)
    
    if args.verbose:
        logger.setLevel(logging.INFO)
    if args.debug:
        logger.setLevel(logging.DEBUG)
    if args.quiet:
        logger.disabled = True
        
    parsing_utils = ParsingUtils(sentiment_url=sentiment_url, logger=logger, 
                                 web_sentiment=args.web_sentiment, verbose=args.verbose)
    
    # create instance of elasticsearch
    es = Elasticsearch(hosts=[{'host': elasticsearch_host, 'port': elasticsearch_port}])
    
    # check if need to override any tokens
    if args.override_tokens_required:
        nltk_tokens_required = tuple(args.override_tokens_required)
    if args.override_tokens_ignored:
        nltk_tokens_ignored = tuple(args.override_tokens_ignored)

    # create instance of tweet listener
    tweet_listener = TweetStreamListener(parsing_utils=parsing_utils, verbose=args.verbose)
    
    # set twitter access keys/tokens
    auth = OAuthHandler(consumer_key, consumer_key_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = API(auth)
    
    # create instance of the tweepy stream
    stream = Stream(auth, tweet_listener)
    
    # grab twitter users from links at url
    if args.url:
        twitter_users = parsing_utils.get_twitter_users_from_url(args.url)
        if len(twitter_users) > 0:
            twitter_feeds = twitter_users
        else:
            logger.info('No twitter user found in links at %s, exiting' % args.url)
            sys.exit(1)
        
    try:
        # search twitter for keywords
        logger.info('Stock symbol: %s' % args.symbol)
        logger.info('NLTK tokens required : %s' % str(nltk_tokens_required))
        logger.info('NLTK tokens ignored: %s' % str(nltk_tokens_ignored))
        logger.info('Listening for tweets (ctrl-c to exit)')
        keywords = args.keywords.split(',')
        if args.add_tokens:
            for f in nltk_tokens_required:
                keywords.append(f)
        logger.info('Searching twitter for keywords...')
        logger.info('Twitter keywords: %s' % keywords)
        stream.filter(track=keywords, languages=['en'])
    except TweepError as te:
        logger.debug('Tweepy exception: failed to get tweets caused by: %s' % te)
    except KeyboardInterrupt:
        print('ctrl-c keyboard interrupt, exiting...')
        stream.disconnect()
        sys.exit(0)
            