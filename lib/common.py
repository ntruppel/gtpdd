# -*- coding: utf-8 -*-
"""
Created on Wed Jul 12 21:52:41 2023

@author: ntrup
"""


def parseRowStringTextTrue(row):
    return [str(x.string) for x in row.find_all(text=True)]

def parseRowStringTd(row):
    return [str(x.string) for x in row.find_all('td')]

def parseRowStringTextTrue0(row):
    return [str(x.string) for x in row.find_all(text=True)][0]

def parseRowStringTdA(row):
    return [str(x.string) for x in row.find_all(['td','a'])]

## TODO: Go through parse rows below and replace with better named ones above

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
