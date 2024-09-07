# -*- coding: utf-8 -*-
"""
Created on Wed Sep  1 15:41:33 2021

@author: ntrup
"""
import requests
import datetime
import numpy as np
from datetime import datetime, timezone
import matplotlib.pyplot as plt
from PIL import Image
from lib.common import createTweet
from lib.fbCommon import getFBSchedule, getTeamInfo


def getPrediction(gameID, teamID):
    url = 'http://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event=' + gameID
    r = requests.get(url)
    x = r.json()
    
    if x['predictor']['homeTeam']['id'] == teamID:
        return x['predictor']['homeTeam']['gameProjection']
    else:
        return x['predictor']['awayTeam']['gameProjection']
    

def fbRecordPredictor(platform):
    if platform == 'Windows':
        figPath = r'out_files/fbRecordPredictor.png'
        backgroundPath = r'in_files\backgrounds\fbRecordPredictor.png'

    elif platform == 'AWS':
        figPath = 'out/fbRecordPredictor.png'
        
        import boto3
        s3 = boto3.client('s3')
        backgroundPath = '/tmp/fbRecordPredictorBackground.png'
        s3.download_file('gtpdd', 'fb_record_predictor_background.png', '/tmp/fbRecordPredictorBackground.png')
    
    
    present = datetime.now(timezone.utc)
    teamID = "2348"
    schedule_df, record = getFBSchedule(teamID)
    
    predictions = []
    wins = int(record.split('-')[0])
    loss = int(record.split('-')[1])
    for i in range(0,wins):
        predictions.append(100)
    for i in range(0,loss):
        predictions.append(0)
    
    ## When ESPN finally updates their API for 2023, this will work
    for index,row in schedule_df.iterrows():
        if present < row['date']:    
            predictions.append(getPrediction(row['gameID'], teamID))
    print(predictions)
    
    ## For now, stuck doing it manually. Remove this when ESPN API updates
    #gameIDs = ['401641007','401635546','401641008','401640981','401641009','401641010','401641011','401641012','401641004','401641013','401628427','401641014'] 
    #for gameID in gameIDs:
        #predictions.append(getPrediction(gameID, teamID))
        
    predictions = [round(float(x)/100,3) for x in predictions]
    print(predictions)
    
    
    
    wins12 = np.prod(predictions)
    
    wins11 = 0
    for i in range(0,12):
        predictions[i] = round(1 - predictions[i],3)
        wins11 = wins11 + np.prod(predictions)
        predictions[i] = round(1 - predictions[i],3)
            
    wins10 = 0
    for i in range(0,12):
        predictions[i] = round(1 - predictions[i],3)
        for j in range(i+1,12):
            predictions[j] = round(1 - predictions[j],3)
            wins10 = wins10 + np.prod(predictions)
            predictions[j] = round(1 - predictions[j],3)
        predictions[i] = round(1 - predictions[i],3)
    
    
    wins9 = 0
    for i in range(0,12):
        predictions[i] = round(1 - predictions[i],3)
        for j in range(i+1,12):
            predictions[j] = round(1 - predictions[j],3)
            for k in range(j+1,12):
                predictions[k] = round(1 - predictions[k],3)
                wins9 = wins9 + np.prod(predictions)
                predictions[k] = round(1 - predictions[k],3)
            predictions[j] = round(1 - predictions[j],3)
        predictions[i] = round(1 - predictions[i],3)
    
    wins8 = 0
    for i in range(0,12):
        predictions[i] = round(1 - predictions[i],3)
        for j in range(i+1,12):
            predictions[j] = round(1 - predictions[j],3)
            for k in range(j+1,12):
                predictions[k] = round(1 - predictions[k],3)
                for l in range(k+1,12):
                    predictions[l] = round(1 - predictions[l],3)
                    wins8 = wins8 + np.prod(predictions)
                    predictions[l] = round(1 - predictions[l],3)
                predictions[k] = round(1 - predictions[k],3)
            predictions[j] = round(1 - predictions[j],3)
        predictions[i] = round(1 - predictions[i],3)        
    
    wins7 = 0
    for i in range(0,12):
        predictions[i] = round(1 - predictions[i],3)
        for j in range(i+1,12):
            predictions[j] = round(1 - predictions[j],3)
            for k in range(j+1,12):
                predictions[k] = round(1 - predictions[k],3)
                for l in range(k+1,12):
                    predictions[l] = round(1 - predictions[l],3)
                    for m in range(l+1,12):
                        predictions[m] = round(1 - predictions[m],3)
                        wins7 = wins7 + np.prod(predictions)
                        predictions[m] = round(1 - predictions[m],3)
                    predictions[l] = round(1 - predictions[l],3)
                predictions[k] = round(1 - predictions[k],3)
            predictions[j] = round(1 - predictions[j],3)
        predictions[i] = round(1 - predictions[i],3)      
        
    wins6 = 0
    for i in range(0,12):
        predictions[i] = round(1 - predictions[i],3)
        for j in range(i+1,12):
            predictions[j] = round(1 - predictions[j],3)
            for k in range(j+1,12):
                predictions[k] = round(1 - predictions[k],3)
                for l in range(k+1,12):
                    predictions[l] = round(1 - predictions[l],3)
                    for m in range(l+1,12):
                        predictions[m] = round(1 - predictions[m],3)
                        for n in range(m+1,12):
                            predictions[n] = round(1 - predictions[n],3)
                            wins6 = wins6 + np.prod(predictions)
                            predictions[n] = round(1 - predictions[n],3)
                        predictions[m] = round(1 - predictions[m],3)
                    predictions[l] = round(1 - predictions[l],3)
                predictions[k] = round(1 - predictions[k],3)
            predictions[j] = round(1 - predictions[j],3)
        predictions[i] = round(1 - predictions[i],3)
    
    for i in range(0,12):
        predictions[i] = round(1 - predictions[i],3)
    
    wins5 = 0
    for i in range(0,12):
        predictions[i] = round(1 - predictions[i],3)
        for j in range(i+1,12):
            predictions[j] = round(1 - predictions[j],3)
            for k in range(j+1,12):
                predictions[k] = round(1 - predictions[k],3)
                for l in range(k+1,12):
                    predictions[l] = round(1 - predictions[l],3)
                    for m in range(l+1,12):
                        predictions[m] = round(1 - predictions[m],3)
                        wins5 = wins5 + np.prod(predictions)
                        predictions[m] = round(1 - predictions[m],3)
                    predictions[l] = round(1 - predictions[l],3)
                predictions[k] = round(1 - predictions[k],3)
            predictions[j] = round(1 - predictions[j],3)
        predictions[i] = round(1 - predictions[i],3)    
        
    wins4 = 0
    for i in range(0,12):
        predictions[i] = round(1 - predictions[i],3)
        for j in range(i+1,12):
            predictions[j] = round(1 - predictions[j],3)
            for k in range(j+1,12):
                predictions[k] = round(1 - predictions[k],3)
                for l in range(k+1,12):
                    predictions[l] = round(1 - predictions[l],3)
                    wins4 = wins4 + np.prod(predictions)
                    predictions[l] = round(1 - predictions[l],3)
                predictions[k] = round(1 - predictions[k],3)
            predictions[j] = round(1 - predictions[j],3)
        predictions[i] = round(1 - predictions[i],3)   
        
    wins3 = 0
    for i in range(0,12):
        predictions[i] = round(1 - predictions[i],3)
        for j in range(i+1,12):
            predictions[j] = round(1 - predictions[j],3)
            for k in range(j+1,12):
                predictions[k] = round(1 - predictions[k],3)
                wins3 = wins3 + np.prod(predictions)
                predictions[k] = round(1 - predictions[k],3)
            predictions[j] = round(1 - predictions[j],3)
        predictions[i] = round(1 - predictions[i],3)
        
    wins2 = 0  
    for i in range(0,12):
        predictions[i] = round(1 - predictions[i],3)
        for j in range(i+1,12):
            predictions[j] = round(1 - predictions[j],3)
            wins2 = wins2 + np.prod(predictions)
            predictions[j] = round(1 - predictions[j],3)
        predictions[i] = round(1 - predictions[i],3)
        
    wins1 = 0
    for i in range(0,12):
        predictions[i] = round(1 - predictions[i],3)
        wins1 = wins1 + np.prod(predictions)
        predictions[i] = round(1 - predictions[i],3)
       
    wins0 = np.prod(predictions)
    
    wins = [wins0, wins1, wins2, wins3, wins4, wins5, wins6, wins7, wins8, wins9, wins10, wins11, wins12]
    records = ['0-12','1-11','2-10','3-9','4-8','5-7','6-6','7-5','8-4','9-3','10-2','11-1','12-0']
    
    name, color1, color2 = getTeamInfo(teamID)
    fig,ax = plt.subplots()
    fig.set_size_inches(20, 10)
    for i in range(0,len(wins)):
        ax.bar(i,wins[i], color='#' + color1)
        ax.text(i,wins[i]+0.005,"{:.2%}".format(wins[i]), ha = 'center', fontsize=20, color = 'white')
        ax.text(i,-0.005,records[i], ha = 'center', va = 'top', fontsize = 20, color = 'white')
        
    ax.set_ylim([0,max(wins)+0.05])
    ax.axis('off')
    now = datetime.now()
    datestring = now.strftime("%B %-d, %Y")
    ax.set_title("Using ESPN's FPI | " +str(datestring), fontsize = 30, color = 'white')
    plt.suptitle('Tech Record Predictor', fontsize = 45, color = 'white', fontweight = 'bold')
    fig.savefig(figPath, bbox_inches='tight', pad_inches = 0, dpi=100, transparent = True)
    
    
    img = Image.open(figPath, 'r')
    img_w, img_h = img.size
    background = Image.open(backgroundPath, 'r')
    bg_w, bg_h = background.size
    offset = ((bg_w - img_w) // 2, (bg_h - img_h) // 2)
    background.paste(img, offset, img)
    background.save(figPath)
    
    pctBowling = wins6 + wins7 + wins8 + wins9 + wins10 + wins11 + wins12
    
    status = "Using ESPN's FPI, here are the odds on how Tech's record will look at the end of the regular season"
    if pctBowling != 0 or pctBowling != 1:
        status = status + ". Right now ESPN gives Tech a " + f"{pctBowling:.2%}" + " chance to make a bowl game:"
        
    print(status)
    
    
    #createTweet(status,[figPath])

fbRecordPredictor("AWS")