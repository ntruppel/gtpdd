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


####
# SIDEARM PAGES
####

def nuxtPayload(text):
    # Sidearm nextgen pages embed their data as a Nuxt payload; rebuilds it as plain dicts and lists
    import json
    import re
    m = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', text, re.S)
    if not m:
        raise ValueError("Page has no __NUXT_DATA__ payload; did the site change?")

    # Flat array: [{"game": 1}, {"opponent": 2}, "ULM"] unflattens to {"game": {"opponent": "ULM"}}
    flat = json.loads(m.group(1))
    # Vue state is wrapped as ["Reactive", <slot>]; these tags mean "use the value in that slot"
    wrappers = {'Reactive', 'ShallowReactive', 'Ref', 'ShallowRef', 'EmptyRef'}
    # Slots already rebuilt, so shared values are built once and self-references can't loop
    memo = {}

    def resolve(i):
        # Anything that isn't a slot number is a plain value
        if not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(flat):
            return i
        if i in memo:
            return memo[i]
        v = flat[i]
        if isinstance(v, list):
            # A wrapper tag: skip to the slot it wraps (EmptyRef has none)
            if v and isinstance(v[0], str) and v[0] in wrappers:
                memo[i] = resolve(v[1]) if len(v) > 1 else None
                return memo[i]
            out = memo[i] = []
            out.extend(resolve(x) for x in v)
            return out
        if isinstance(v, dict):
            out = memo[i] = {}
            for k, x in v.items():
                out[k] = resolve(x)
            return out
        return v

    # Start at the root in slot 0 and rebuild everything reachable from it
    return resolve(0)


####
# PAGE SCREENSHOTS
####

# Chrome or Chromium, wherever this machine keeps it
BROWSERS = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Chromium.app/Contents/MacOS/Chromium',
            'google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome']


def findBrowser():
    # Returns the path to a Chrome or Chromium binary, or None
    for name in BROWSERS:
        path = name if os.path.isfile(name) else shutil.which(name)
        if path:
            return path
    return None


def screenshotPage(page_path, dest, size=(1200, 630), scale=2, query='?preview'):
    # Screenshots a local page with headless Chrome at size, saved as a JPEG; returns dest or None
    import subprocess
    import tempfile
    from pathlib import Path
    from PIL import Image
    browser = findBrowser()
    if browser is None:
        print("No Chrome or Chromium found; skipping the screenshot.")
        return None
    W, H = size
    url = Path(page_path).resolve().as_uri() + query
    # A throwaway profile, so a Chrome that's already open doesn't get in the way
    with tempfile.TemporaryDirectory() as profile:
        shot = os.path.join(profile, 'shot.png')
        cmd = [browser, '--headless=new', '--disable-gpu', '--hide-scrollbars',
               '--allow-file-access-from-files', f'--user-data-dir={profile}',
               f'--window-size={W},{H}', f'--force-device-scale-factor={scale}',
               f'--screenshot={shot}', url]
        try:
            subprocess.run(cmd, check=True, timeout=60, capture_output=True)
            img = Image.open(shot).convert('RGB')
        except Exception as e:
            print(f"Could not screenshot {page_path} ({type(e).__name__}: {e}).")
            return None
    # Back down to the requested size from the scaled shot
    img = img.resize(size, Image.LANCZOS)
    os.makedirs(os.path.dirname(dest) or '.', exist_ok=True)
    img.save(dest, quality=88, optimize=True)
    return dest
