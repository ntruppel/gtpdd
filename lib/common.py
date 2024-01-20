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
    
    auth = tweepy.OAuthHandler(twitter_keys['consumer_key'], twitter_keys['consumer_secret'])
    auth.set_access_token(twitter_keys['access_token_key'], twitter_keys['access_token_secret'])
    api = tweepy.API(auth)
    
    media_ids = []
    for filename in filenames:
        res = api.media_upload(filename)
        media_ids.append(res.media_id)
        
    response = client.create_tweet(text=status,media_ids=media_ids)
    
    print(response)
