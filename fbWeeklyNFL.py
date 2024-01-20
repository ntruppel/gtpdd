# -*- coding: utf-8 -*-
"""
Created on Sun Jul 23 16:51:12 2023

@author: ntrup
"""
import requests
from PIL import Image, ImageFont, ImageDraw
from lib.common import createTweet
from datetime import date
import os


def checkIfPlayed(platform, week, playerID):
    url = 'https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/'+ playerID + '/gamelog?year=2023'
    r = requests.get(url)
    x = r.json()
    
    for gameID in list(x['events'].keys()):
        if x['events'][gameID]['week'] == int(week):
            getPlayerStats(platform, week,x, gameID, playerID)
            return 1
    return 0

def getPlayerStats(platform,week,x,gameID, playerID):
    statLabels = x['labels']
    statNames = x['displayNames']
    
    statLengths = []
    for category in x['categories']:
        statLengths.append(category['count'])
        
    for seasonType in x['seasonTypes']:
        for game in x['seasonTypes'][0]['categories'][0]['events']:
            if game['eventId'] == gameID:
                stats = game['stats']
                indices = [i for i in range(len(stats)) if stats[i] == '0' or stats[i] == '0.0']
                indices.reverse()
                for index in indices:
                    del stats[index]
                    del statLabels[index]
                createPlayerCard(platform,week,playerID,stats,statLabels,statNames, statLengths)
                
def createPlayerCard(platform,week,playerID,stats,statLabels,statNames, statLengths):
    if platform == 'Windows':
        img = Image.open('in_files/nfl_cards/' + playerID + '.png')
        
    for name in statNames:
        if name in ['Yards Per Pass Attempt', 'Adjusted QBR', 'Total Sacks', 'Longest Pass']:
            index = statNames.index(name)
            del stats[index]
            del statLabels[index]
            del statNames[index]
            statLengths[0] = int(statLengths[0]) - 1
    
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("in_files/font/Oswald-Regular.ttf", 18)
    draw.text((890,330),"Week "+ str(week) + " Stats:",(1,1,151),font=font)
    
    j=0
    for i in range(0,len(stats)):
        if j < statLengths[0]:
            draw.text((730,350+i*30),statNames[i] + ": " + stats[i],(1,1,151),font=font)
        elif j < statLengths[0] + statLengths[1]:
            draw.text((950,350+(i-5)*30),statNames[i] + ": " + stats[i],(1,1,151),font=font)
        j = j+1
        

    img.save('out_files/nfl_cards/' + playerID + '_' + str(week) + '.png')


def fbWeeklyNFL(platform):
    week = str(date.today().isocalendar()[1] - 36)
    if int(week) < 0:
        week = int(week) + 52
        week = str(week)
    print(week)
    
    playerIDs = [ '4040432',    ## L'Jarius Sneed
                  '3040572',    ## Xavier Woods
                  '3040569',    ## Trent Taylor     NEED TO CREATE CARD
                  '4239694',    ## Amik Robertson   
                  '3051439',    ## Boston Scott
                  '4239699',    ## Milton Williams
                  '2574630'     ## Jeff Driskel
                  ]
    goodIDs = []
    for playerID in playerIDs:
        try:
            if checkIfPlayed(platform, week, playerID):
                print(playerID)
                week_file = 'out_files/nfl_cards/' + playerID+'_'+str(week)+'.png'
                if os.path.isfile(week_file):
                    goodIDs.append(playerID+'_'+str(week)+'.png')
            
        except:
            print(playerID + ' no game')
    
    filenames = [[],[],[],[]]
    i = 0
    for goodID in goodIDs:
        if len(filenames[i]) < 4:
            filenames[i].append('out_files/nfl_cards/' + goodID)
        else:
            i = i + 1
            filenames[i].append('out_files/nfl_cards/' + goodID)
    
    filenames = [x for x in filenames if x]
    print(filenames)
    numTweets = len(filenames)
    
    if numTweets == 1:
        status="Here's how some former Tech Bulldogs performed in the NFL this week:"
        createTweet(status, filenames[0])
        print(status)
        
    elif numTweets != 1:
        i = 1
        for filename in filenames:
            status="Here's how some former Tech Bulldogs performed in the NFL this week (" +str(i)+"/"+str(numTweets) + "):"
            createTweet(status, filename)
            i = i+1
            print(status)
            
    
    
fbWeeklyNFL('Windows')



