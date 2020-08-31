"""
file - stockprice.py
Get stock price from yahoo finance and add to Elasticsearch
"""

import argparse
import json
import logging
import random
import re
import requests
import sys
import time

from elasticsearch import Elasticsearch

from config import elasticsearch_host, elasticsearch_port, yahoo_stock_url

# create es instance
es = Elasticsearch(hosts=[{'host': elasticsearch_host, 'port': elasticsearch_port}])

class Stock:
    
    def __init__(self):
        pass
    
    def get_stock_price(self, url, symbol):
        
        import re
        
        while True:
            logger.info('grabbing stock data for symbol %s...' % symbol)
            
            try:
                url = re.sub('SYMBOL', symbol, url)
                # get json stock data from url
                try:
                    r = requests.get(url)
                    data = r.json()
                except (requests.HTTPError, requests.ConnectionError, requests.ConnectTimeout) as re:
                    logger.error('exception occurred when  getting stock data from url caused by %s' % re)
                    raise
                logger.debug(data)
                try:
                    dict = {}
                    dict['symbol'] = symbol
                    dict['last'] = data['chart']['result'][0]['indicators']['quote'][0]['close'][-1]
                    if dict['last'] is None:
                        dict['last'] =  data['chart']['result'][0]['indicators']['quote'][0]['close'][-2]
                    dict['date'] = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())
                    try:
                        dict['change'] = (data['chart']['result'][0]['indicators']['quote'][0]['close'][-1] - 
                                          data['chart']['result'][0]['indicators']['quote'][0]['close'][-2]) / \
                                              data['chart']['result'][0]['indicators']['quote'][0]['close'][-2] * 100
                    except TypeError:
                        dict['change'] = (data['chart']['result'][0]['indicators']['quote'][0]['close'][-2] - 
                                          data['chart']['result'][0]['indicators']['quote'][0]['close'][-3]) / \
                                              data['chart']['result'][0]['indicators']['quote'][0]['close'][-3] * 100
                        pass
                    dict['high'] = data['chart']['result'][0]['indicators']['quote'][0]['high'][-1]
                    if dict['high'] is None:
                        dict['high'] = data['chart']['result'][0]['indicators']['quote'][0]['high'][-2]
                    
                    dict['low'] = data['chart']['result'][0]['indicators']['quote'][0]['low'][-1]
                    if dict['low'] is None:
                        dict['low'] = data['chart']['result'][0]['indicators']['quote'][0]['low'][-2]
                    
                    dict['vol'] = data['chart']['result'][0]['indicators']['quote'][0]['volume'][-1]
                    if dict['vol'] is None:
                        dict['vol'] = data['chart']['result'][0]['indicators']['quote'][0]['volume'][-2]
                    
                    logger.debug(dict)
                except KeyError as e:
                    logger.error('exception occurred when getting stock data caused by %s' % e)
                    raise
                
                # sanity before sending to es
                if dict['last'] is not None and dict['high'] is not None and dict['low'] is not None:
                    logger.info('adding stock data to Elasticsearch')
                    es.index(index=args.index, doc_type='stock', 
                             body={
                                 'symbol': dict['symbol'], 
                                 'price_last': dict['last'], 
                                 'date': dict['date'], 
                                 'change': dict['change'], 
                                 'price_high': dict['high'], 
                                 'price_low': dict['low'], 
                                 'vol': dict['vol']
                             })
                else:
                    logger.warning('some stock data had null values, skipping')
            
            except Exception as e:
                logger.error('exception can\'t get stock data caused by %s, trying again later' % e)
                pass
            
if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--index', default='stock-price', 
                        help='Index name for es')
    parser.add_argument('-s', '--symbol', type=str, help='Stock symbol, e.g. TSLA')
    parser.add_argument('-v', '--verbose', action='store_true', help='Increase output verbosity')
    parser.add_argument('--debug', action='store_true', help='Debug message output')
    parser.add_argument('-q', '--quiet', action='store_true', help='Run quiet with no msg output')
    
    args = parser.parse_args()
    
    # set up logging
    logger = logging.getLogger('stock-price')
    logger.setLevel(logging.INFO)
    
    logging.addLevelName(
        logging.INFO, "\033[1;32m%s\033[1;0m"
                      % logging.getLevelName(logging.INFO))
    logging.addLevelName(
        logging.WARNING, "\033[1;31m%s\033[1;0m"
                         % logging.getLevelName(logging.WARNING))
    logging.addLevelName(
        logging.ERROR, "\033[1;41m%s\033[1;0m"
                       % logging.getLevelName(logging.ERROR))
    logging.addLevelName(
        logging.DEBUG, "\033[1;33m%s\033[1;0m"
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
        
    if args.symbol is None:
        print('No stock symbol, see --help for help')
        sys.exit(1)
    
    # create instance of Stock
    stockprice = Stock()
    
    try:
        stockprice.get_stock_price(symbol=args.symbol, url=yahoo_stock_url)
    except Exception as e:
        logger.warning('Exception occurred when getting stock data caused by %s' % e)
    except KeyboardInterrupt:
        print('Ctrl-c keyboard interrupt, exiting...')
        sys.exit(0)
    