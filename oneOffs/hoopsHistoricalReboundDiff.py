import requests
import json
import pandas as pd

def getData():
    gameString = ''
    for i in range(2012,2026):
        url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/latech/schedule?season=' + str(i)
        r = requests.get(url)
        x = r.json()['events']
        for game in x:
            try:
                techRebounds = ''
                oppoRebounds = ''
                url = 'http://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event=' + game['id']
                r = requests.get(url)
                x = r.json()
                if x['boxscore']['teams'][0]['team']['displayName'] == 'Louisiana Tech Bulldogs':
                    for stat in x['boxscore']['teams'][0]['statistics']:
                        if stat['name'] == 'totalRebounds':
                            techRebounds=stat['displayValue']
                    for stat in x['boxscore']['teams'][1]['statistics']:
                        if stat['name'] == 'totalRebounds':
                            oppoRebounds=stat['displayValue']

                elif x['boxscore']['teams'][1]['team']['displayName'] == 'Louisiana Tech Bulldogs':
                    for stat in x['boxscore']['teams'][1]['statistics']:
                        if stat['name'] == 'totalRebounds':
                            techRebounds=stat['displayValue']
                    for stat in x['boxscore']['teams'][0]['statistics']:
                        if stat['name'] == 'totalRebounds':
                            oppoRebounds=stat['displayValue']

                if x['header']['competitions'][0]['competitors'][0]['team']['displayName'] == 'Louisiana Tech Bulldogs':
                    isWin = x['header']['competitions'][0]['competitors'][0]['winner']
                elif x['header']['competitions'][0]['competitors'][1]['team']['displayName'] == 'Louisiana Tech Bulldogs':
                    isWin = x['header']['competitions'][0]['competitors'][1]['winner']

                print(game['id'],isWin,techRebounds,oppoRebounds)
                gameString = gameString + game['id'] + ',' + str(isWin) + ',' + techRebounds + ',' + oppoRebounds + '\n'
            except:
                gameString = gameString + game['id'] + '\n'
            
        with open('csv/hoopsHisoricalRebDiff.csv','w') as f:
                f.write(gameString)


#getData()
df = pd.read_csv('csv/hoopsHisoricalRebDiff.csv')
df['rebDiff'] = df['TechReb'] - df['OppoReb']
print(df)