# -*- coding: utf-8 -*-
"""
Created on Wed Jul 12 21:52:41 2023

@author: ntrup
"""
import os
import shutil


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


####
# STATIC SITE FILES
####

def copyMissingFiles(src_dir, dest_dir):
    # Copies every file under src_dir into dest_dir unless it's already there; returns the copied paths
    copied = []
    for root, _, files in os.walk(src_dir):
        for name in files:
            if name == '.DS_Store':
                continue
            src = os.path.join(root, name)
            # Same relative path under dest_dir, so subfolders mirror the source
            dest = os.path.join(dest_dir, os.path.relpath(src, src_dir))
            # Never overwrite, so local edits to a published copy survive
            if os.path.exists(dest):
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)
            print(f"Copied {src} -> {dest}")
            copied.append(dest)
    return copied
