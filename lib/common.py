# -*- coding: utf-8 -*-
"""
Created on Wed Jul 12 21:52:41 2023

@author: ntrup
"""

import tweepy


def parse_th_row(row):
    return [str(x.string) for x in row.find_all('th')]

def parse_mod_th_row(row):
    return [str(x) for x in row.find_all('th')]

def parse_td_row(row):
    return [str(x.string) for x in row.find_all('td')]

def parse_td_text_row(row):
    return [str(x.string) for x in row.find_all(text=True)]

def parse_a_row(row):
    return [str(x.string) for x in row.find_all(text=True)]

def parse_span_row(row):
    return [str(x.string) for x in row.find_all(text=True)]

def parse_mod_td_row(row):
    return [str(x) for x in row.find_all('td')]

def parse_th_row(row):
    return [str(x.string) for x in row.find_all(text=True)]

def createTweet(status,filenames):
    client = tweepy.Client(
        consumer_key='UQFEflfOzx4lDj6kaZrlB135G',
        consumer_secret='Ir5ok2lyHijQuhinrFOBw48wvwK88OepUIo6gJYgHEda0OgAAQ',
        access_token='1350197647018176513-KomgwjYEEPIIJl1pvE2o4hG9oJEd3K',
        access_token_secret='QrkmTSjDA2MNBpElTlpcdZRQljD0wU4PfkSGC2QpeY7Qq')
    
    
    twitter_keys = {
            'consumer_key':        'UQFEflfOzx4lDj6kaZrlB135G',
            'consumer_secret':     'Ir5ok2lyHijQuhinrFOBw48wvwK88OepUIo6gJYgHEda0OgAAQ',
            'access_token_key':    '1350197647018176513-KomgwjYEEPIIJl1pvE2o4hG9oJEd3K',
            'access_token_secret': 'QrkmTSjDA2MNBpElTlpcdZRQljD0wU4PfkSGC2QpeY7Qq'
        }
    
    auth = tweepy.OAuthHandler(twitter_keys['consumer_key'], twitter_keys['consumer_secret'])
    auth.set_access_token(twitter_keys['access_token_key'], twitter_keys['access_token_secret'])
    api = tweepy.API(auth)
    
    media_ids = []
    for filename in filenames:
        res = api.media_upload(filename)
        media_ids.append(res.media_id)
        
    response = client.create_tweet(text=status,media_ids=media_ids)
    
    print(response)