from bs4 import BeautifulSoup as Soup
import requests
import numpy as np
import pandas as pd
from pandas import DataFrame
import matplotlib.pyplot as plt
import matplotlib.colors as mc
import colorsys
from PIL import Image
from lib.common import parse_th_row, parse_mod_th_row, parse_td_row, parse_mod_td_row
from lib.hoopsCommon import getESPNAPI
    
def get_pbp_table(table):
    with pd.option_context('future.no_silent_downcasting', True):
        stat_rows = table.find_all('tr')
        list_of_parsed_stat_rows = [parse_td_row(row) for row in stat_rows[1:]]
        stat_df = DataFrame(list_of_parsed_stat_rows)
        stat_df = stat_df.drop(columns=[2,6,7,8])
        stat_df.columns = ['time','visitor_play','visitor_score','home_score','home_play']
        df = stat_df.replace('--', np.nan)
        df = df.replace(r'^\s*$', np.nan, regex=True)
        df = df.ffill()
        df = df.replace('None', np.nan)
    return df

def get_subs(df,team):
    if team == 'visitor': play,score,n_play,n_score = 'visitor_play','visitor_score','home_play','home_score'
    else: n_play,n_score,play,score = 'visitor_play','visitor_score','home_play','home_score'
    subs_df = df[df[play].str.contains('SUB',na = False)]
    subs_df = subs_df.drop(columns=[score,n_score,n_play])
    subs_df['action'] = np.nan
    subs_df[['action','player']] = subs_df[play].str.split("b", n=2, expand=True)
    subs_df['player'] = subs_df['player'].str[2:]
    subs_df = subs_df.drop(columns=play)
    subs_df['player'] = subs_df['player'].str.split(',').str[::-1].str.join(' ')
    return subs_df


def get_shots(df,team):
    searchfor = ['GOOD', 'MISS', 'REBOUND', 'FOUL', 'TURNOVER', 'ASSIST']    
    if team == 'visitor': play,score,n_play,n_score = 'visitor_play','visitor_score','home_play','home_score'
    else: n_play,n_score,play,score = 'visitor_play','visitor_score','home_play','home_score'
    
    ## Seperate out the made shots
    shots_df = df[df[play].str.contains('|'.join(searchfor),na = False)]
    shots_df = shots_df.drop(columns=[score,n_score, n_play])
    shots_df['action'] = np.nan
    shots_df[['action','player']] = shots_df[play].str.split("by", n=2, expand=True)
    shots_df['player'] = shots_df['player'].str[1:]
    shots_df = shots_df.drop(columns=play)
    shots_df['player'] = shots_df['player'].str.split(',').str[::-1].str.join(' ')
    shots_df['player'] = shots_df['player'].str.replace('\(.*\)','',regex=True)

    ## Convert Timestamp to seconds count
    time_secs = []
    for time in shots_df['time']: time_secs.append(int(time.split(':')[0])*60 + int(time.split(':')[1]))
    shots_df['time'] = time_secs
    shots_df = shots_df.sort_values(by=['time'], ascending=False)
    shots_df['player'] = shots_df['player'].str.title()
        
    return shots_df

def get_lineup(subs_df, lineups_df, startTime):
    # Create empty row with 20:00
    lineup = [[startTime,np.nan,np.nan,np.nan,np.nan,np.nan]]
    lineup_df = pd.DataFrame(lineup, columns = ['Time','P1','P2','P3','P4','P5'])
    lineup_df = lineup_df.set_index('Time')
    lineup_df['P1'] = lineup_df['P1'].astype('object')
    lineup_df['P2'] = lineup_df['P2'].astype('object')
    lineup_df['P3'] = lineup_df['P3'].astype('object')
    lineup_df['P4'] = lineup_df['P4'].astype('object')
    lineup_df['P5'] = lineup_df['P5'].astype('object')


    
    for index, row in subs_df.iterrows(): lineup_df.loc[row['time']] = [np.nan,np.nan,np.nan,np.nan,np.nan]

    subs_df = subs_df.sort_values(by=['time','action'], ascending=False)
        
    # Go line-by-line through vsubs
    for index, row in subs_df.iterrows():
        if row['action'] == 'SUB IN ':
            
            def fillLoop(pNum):
                lineup_df.loc[row['time'],pNum] = row['player']
                lineup_df[pNum] = lineup_df[pNum].ffill()
            
            if pd.isnull(lineup_df.loc[row['time'],'P1']): fillLoop('P1')
            elif pd.isnull(lineup_df.loc[row['time'],'P2']): fillLoop('P2')
            elif pd.isnull(lineup_df.loc[row['time'],'P3']): fillLoop('P3')
            elif pd.isnull(lineup_df.loc[row['time'],'P4']): fillLoop('P4')
            elif pd.isnull(lineup_df.loc[row['time'],'P5']): fillLoop('P5')

        if row['action'] == 'SUB OUT ' and row['time'] != startTime:
            
            def subOutLoop(pNum):
                lineup_df.loc[row['time']:,pNum] = np.nan
                
            def startPlayers(pNum):
                lineup_df.loc[startTime,pNum] = row['player']

            if lineup_df.loc[row['time'],'P1'] == row['player']: subOutLoop('P1')
            elif lineup_df.loc[row['time'],'P2'] == row['player']: subOutLoop('P2')
            elif lineup_df.loc[row['time'],'P3'] == row['player']: subOutLoop('P3')
            elif lineup_df.loc[row['time'],'P4'] == row['player']: subOutLoop('P4')
            elif lineup_df.loc[row['time'],'P5'] == row['player']: subOutLoop('P5')
                
            elif pd.isnull(lineup_df.loc[startTime,'P1']): startPlayers('P1')
            elif pd.isnull(lineup_df.loc[startTime,'P2']): startPlayers('P2')
            elif pd.isnull(lineup_df.loc[startTime,'P3']): startPlayers('P3')
            elif pd.isnull(lineup_df.loc[startTime,'P4']): startPlayers('P4')
            elif pd.isnull(lineup_df.loc[startTime,'P5']): startPlayers('P5')
                
    if(lineup_df['P5'].isnull().all()):
        nosubs = []
        name_rows = lineups_df.find_all('tr')
        list_of_parsed_name_rows = [parse_mod_td_row(row) for row in name_rows[1:]]
        name_df = DataFrame(list_of_parsed_name_rows)
        name_df[1] = name_df[1].str.split('</span>').str[1]
        name_df[1] = name_df[1].str.split('</td>').str[0]
        name_df = name_df.drop(columns=[0,2,3,4,5,6,7,8,9,10,11,12,13,14])
        
        box_rows = lineups_df.find_all('tr')
        list_of_parsed_box_rows = [parse_td_row(row) for row in box_rows[1:]]
        box_df = DataFrame(list_of_parsed_box_rows)        
        box_df = box_df.drop(columns=[0,1,2,4,5,6,7,8,9,10,11,12,13,14])
        box_df.columns = ['minutes']
        name_df.columns = ['name']
                
        minutes = box_df['minutes']
        df = name_df.join(minutes)
    
        ## Get list of players who played 20 minutes
        ## FUTURE: I think starters have a * in column 2
        for index, row in df.iterrows():
            if row['minutes'] > '21':
                nosubs.append(row['name'])
        nosubs = [x for x in nosubs if str(x) != 'nan']
        ## Sometimes the names are hyperlinks, so we have to extract the actual name
        try:
            i=0
            for nosub in nosubs:
                nosubs[i] = nosub.split('>')[1].split('</a')[0]
                i = i+1
        except: 0
            
        ## Change from LAST,FIRST to FIRST LAST
        i = 0
        for nosub in nosubs:
            nosubs[i] = nosub.split(',')[1].strip() + ' ' + nosub.split(',')[0].strip()
            i = i + 1
        
        ## Get the names already in the lineup
        lineup_list = lineup_df.values.tolist()[0]
        
        ## Convert the names from allcaps
        i=0
        for lineup in lineup_list:
            lineup_list[i] = str(lineup).title()
            i=i+1
        
        ## Remove names from nosubs if they are already on the lineup
        nosubs2 = []
        for nosub in nosubs:
            if nosub.strip() not in lineup_list:
                nosubs2.append(nosub)
        if nosubs2:
            nosubs = nosubs2

        lineup_df['P5'] = nosubs[0]
    
    i=1
    for pNum in ['P4','P3','P2','P1']:
        if(lineup_df[pNum].isnull().all()):
            lineup_df[pNum] = nosubs[i]
        i = i+1
    
    for pNum in ['P1','P2','P3','P4','P5']:
        lineup_df[pNum] = lineup_df[pNum].str.title()
    
    lineup_df = lineup_df.map(lambda x: x.strip() if isinstance(x, str) else x)
    lineup_df = lineup_df.transpose()
    lineup_df = lineup_df.apply(lambda x: x.sort_values().values)
    lineup_df = lineup_df.transpose()
                
    ## Change timestamp in Time column to seconds
    lineup_df = lineup_df.reset_index(level=0)
    lineup_df[['Minutes','Seconds']] = lineup_df['Time'].str.split(':', expand=True)# + int(lineup_df['Time'].str.split(':').str[1])
    lineup_df['Time'] = lineup_df['Minutes'].astype(int)*60 + lineup_df['Seconds'].astype(int)
    lineup_df = lineup_df.drop(columns=['Minutes','Seconds'])
    return lineup_df


def render_full_lineup_chart(lineup_df, shots_df, team, oppo, color_code, color2, filename, maxTime, platform):
    lineup_df = lineup_df.set_index('Time')
    
    ## Get list of starters and add 'gaps' for STARTERS and BENCH text
    starters = lineup_df.loc[maxTime].tolist()
    starters.insert(0,"")
    starters.append(" ")
    
    ## Get list of all players who played in the game (without duplicates)
    player_list = lineup_df.values.tolist()
    player_list = list(np.concatenate(player_list).flat)
    player_list = list(set(player_list))
    player_list.sort()
    
    ## Seperate out the starters at the top of the chart
    player_list_temp = starters + player_list
    player_list = []
    [player_list.append(x) for x in player_list_temp if x not in player_list]
    
    ## Remove Empty items from list
    if 'nan' in player_list: player_list.remove('nan')
    
    ## Get a list of whether each player was on the court at what intervals
    master_list = []
    temp_list = []
    for name in player_list:
        for index, row in lineup_df.iterrows():
            if row['P1'] == name or row['P2'] == name or row['P3'] == name or row['P4'] == name or row['P5'] == name:
                temp_list.append(color_code)
            else:
                temp_list.append('#B2BEB5')
        master_list.append(temp_list)
        temp_list = []
                    
    ## Get length of time periods
    times = list(lineup_df.index.values)
    
    diff_secs = [i-j for i, j in zip(times[:-1], times[1:])]
    diff_secs.append(int(maxTime)-sum(diff_secs))
    
    ## (So, I'm dumb and did the master list backwards. So rather than fix that logic, I'm just transposing the list of lists because I'm lazy)
    t_master_list = list(map(list, zip(*master_list)))
    
    ## Setup chart
    plt.rcParams["font.family"] = "Century Gothic"
    fig, ax = plt.subplots(figsize=(10, 4), dpi=200)
    
    ## Create bars
    x = 0
    for i in range(0,len(diff_secs)):
        ax.barh(player_list,diff_secs[i],left=x,color=t_master_list[i])
        x = x + diff_secs[i]
    
    ## Put shots on chart
    foul_count = []
    i = 0
    for player in player_list:
        foul_count.append(0)
        ft_flag = 0
        ft_num = 0
        ft_den = 0
        ft_time = ""
        player_shots = shots_df.loc[shots_df['player'] == player]
        for k, (index,row) in enumerate(player_shots.iterrows()):
            if ft_flag == 1:
                if 'GOOD FT' in row['action'] and ft_time <= row['time']+2 and ft_time >= row['time']-2:
                    ft_num = ft_num + 1
                    ft_den = ft_den + 1
                elif 'MISS FT' in row['action'] and ft_time <= row['time']+2 and ft_time >= row['time']-2:
                    ft_den = ft_den + 1
                else:
                    ## See if this was a shooting foul (Need to check the second before the FT since box scores are weird sometimes)
                    searchfor = ['GOOD', 'MISS']
                    player_shot_attempts = player_shots[player_shots['action'].str.contains('|'.join(searchfor),na = False)]
                    times_num = len(player_shot_attempts[player_shot_attempts['time'] == ft_time]) + len(player_shot_attempts[player_shot_attempts['time'] == ft_time + 1]) + len(player_shot_attempts[player_shot_attempts['time'] == ft_time + 2]) + len(player_shot_attempts[player_shot_attempts['time'] == ft_time - 1]) + len(player_shot_attempts[player_shot_attempts['time'] == ft_time - 2])
                                                                                                         
                    if times_num == ft_den:
                        ax.text(int(maxTime) - int(ft_time),i, str(ft_num) + "\n" + "—" + "\n" + str(ft_den), fontsize=6, color='white', weight='bold', va='center', ha='center', linespacing=0.5)
                    else:
                        ax.text(int(maxTime) - int(ft_time),i, "\n\n+" + str(ft_num), fontsize=4, color='white', weight='bold', va='center', ha='center')
                    
                    ft_flag = 0
                    
                ## Need to go ahead and print if this is the player's last shot
                if k == len(player_shots) - 1:
                    ax.text(int(maxTime) - int(ft_time),i, str(ft_num) + "\n" + "—" + "\n" + str(ft_den), fontsize=6, color='white', weight='bold', va='center', ha='center', linespacing=0.5)
                    ft_flag = 0
                    
            if 'GOOD 3PTR' in row['action']:
                ax.text(int(maxTime) - int(row['time']),i,"3", fontsize=10, color='lime', weight='bold', va='center', ha='center')
            elif 'MISS 3PTR' in row['action']:
                ax.text(int(maxTime) - int(row['time']),i,"3", fontsize=10, color='lightpink', weight='bold', va='center', ha='center')
            elif 'GOOD JUMPER' in row['action']:
                ax.text(int(maxTime) - int(row['time']),i,"2", fontsize=10, color='lime', weight='bold', va='center', ha='center')
            elif 'GOOD LAYUP' in row['action']:
                ax.text(int(maxTime) - int(row['time']),i,"2", fontsize=10, color='lime', weight='bold', va='center', ha='center')
            elif 'GOOD DUNK' in row['action']:
                ax.text(int(maxTime) - int(row['time']),i,"2", fontsize=10, color='lime', weight='bold', va='center', ha='center')
            elif 'MISS JUMPER' in row['action']:
                ax.text(int(maxTime) - int(row['time']),i,"2", fontsize=10, color='lightpink', weight='bold', va='center', ha='center')
            elif 'MISS LAYUP' in row['action']:
                ax.text(int(maxTime) - int(row['time']),i,"2", fontsize=10, color='lightpink', weight='bold', va='center', ha='center')
            elif 'MISS DUNK' in row['action']:
                ax.text(int(maxTime) - int(row['time']),i,"2", fontsize=10, color='lightpink', weight='bold', va='center', ha='center')
            elif 'REBOUND' in row['action']:
                ax.text(int(maxTime) - int(row['time']),i,"|", fontsize=14, color='darkorange', weight='heavy', va='center', ha='center')
            elif 'TURNOVER' in row['action']:
                ax.text(int(maxTime) - int(row['time']),i,"|", fontsize=14, color='lightpink', weight='heavy', va='center', ha='center')
            elif 'ASSIST' in row['action']:
                ax.text(int(maxTime) - int(row['time']),i,"|", fontsize=14, color='green', weight='heavy', va='center', ha='center')
            elif 'FOUL' in row['action']:
                foul_count[i] = foul_count[i] + 1
                ax.text(int(maxTime) - int(row['time']),i,"|", fontsize=14, color='#FF3131', weight='bold', va='center', ha='center')
                ax.text(int(maxTime) - int(row['time']),i+0.4,"  " + str(foul_count[i]), fontsize=4, color='#FF3131', weight='bold', va='top', ha='center')
            elif 'FT' in row['action'] and ft_flag == 0:
                ft_flag = 1
                ft_num = 0
                ft_den = 1
                ft_time = row['time']
                if 'GOOD FT' in row['action']:
                    ft_num = 1
                else:
                    ft_num = 0
        i = i+1
    
    ## Add text to chart
    ax.text(1200,0,"STARTERS", fontsize=10, color=color_code, weight='bold', va='center', ha='center')
    ax.text(1200,6,"BENCH", fontsize=10, color=color_code, weight='bold', va='center', ha='center')

    ## Finalize Chart
    ax.set_xlim(0,int(maxTime))
    xticks = [0,240,480,720,960,1200,1440,1680,1920,2160,2400]
    xticklabels = ['Start','16:00\n1H','12:00\n1H','8:00\n1H','4:00\n1H','Halftime','16:00\n2H','12:00\n2H','8:00\n2H','4:00\n2H','End of\nRegulation']

    if maxTime == 2700:
        xticks.append(2700)
        xticklabels.append('End of\nOT')
        plt.axvline(x=2400, color='white', linewidth=1.5)

    ax.set_xticks(xticks)
    ax.set_xticklabels(xticklabels)

    plt.axvline(x=1200, color='white', linewidth=1.5)
    ax.grid(axis="x", color="white", alpha=.5, linewidth=.5)
    plt.gca().invert_yaxis()
    ax.text(0,-5," ")
    ax.set_title('at\n\n ')
    ax.tick_params(axis=u'y', which=u'both',length=0)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    fig.patch.set_facecolor(color2) 
    ax.set_facecolor(color2)
 

    if platform == "AWS":
        fig_path = '/tmp/out.png'
        team_logo_path = '/tmp/'+team+'.png'
        oppo_logo_path = '/tmp/'+oppo+'.png'
        out_path = '/tmp/' + filename + '.png'     
    
    else:
        fig_path = 'tmp/hoopsLineupsTemp.png'
        team_logo_path = 'logo/'+team+'.png'
        oppo_logo_path = 'logo/'+oppo+'.png'
        out_path = 'out/' + filename + '.png'        
        
    plt.savefig(fig_path, bbox_inches='tight', pad_inches = 0, dpi=300)
    
    img = Image.open(fig_path)
    team_logo = Image.open(team_logo_path)
    oppo_logo = Image.open(oppo_logo_path)
    logo_size = 250
    
    team_logo = team_logo.resize((logo_size,logo_size))
    oppo_logo = oppo_logo.resize((logo_size,logo_size))
    
    img_w, img_h = img.size
    v_offset = ((img_w - logo_size) -1390 , 10)
    h_offset = ((img_w) -1290 , 10)
    

    if filename == 'vlineup':
        img.paste(team_logo, v_offset, team_logo)
        img.paste(oppo_logo.convert('L'), h_offset, oppo_logo)
        
    else:
        img.paste(team_logo, h_offset, team_logo)
        img.paste(oppo_logo.convert('L'), v_offset, oppo_logo)
    
    img.save(out_path)
    
    
    if platform == 'AWS':
        import boto3
        s3 = boto3.resource("s3")
        s3.meta.client.upload_file('/tmp/' + filename + '.png', 'gtpdd', filename + '.png')
        
    return 0


def get_plus_minus(lineup_df,scores_df,team,oppo, hFlag, color, color2, platform): 
    ## Get list of all players who played in the game (without duplicates)
    lineup_df2 = lineup_df.drop(columns=['Time'])
    player_list = lineup_df2.values.tolist()
    player_list = list(np.concatenate(player_list).flat)
    player_list = list(set(player_list))
    player_list.sort()
        
    pm_list = [0]*len(player_list)
    
    ## Get timestamps for subs
    sub_times = lineup_df['Time'].tolist()
    sub_times.append(0)
    v_score = [0]
    h_score = [0]
    
    ## Add substitution times to the scores_df from ESPN
    for sub_time in sub_times:
        temp_df = pd.DataFrame({'Away': np.nan, 'Home': np.nan, 'Time': sub_time }, index=[0])
        #temp_df = pd.DataFrame.from_dict(temp_df)
        #scores_df = scores_df.append(temp_df, ignore_index = True)
        scores_df= pd.concat([scores_df,temp_df])

    scores_df = scores_df.sort_values(by = ['Time'], ascending = False)
    scores_df = scores_df.reset_index(drop=True)
    scores_df = scores_df.ffill()
    scores_df = scores_df.fillna(value=0)
        
    
    k = 0
    for i in range(0,len(sub_times)-1):
        ## Get score at those timestamps
        scores_df2 = scores_df.loc[scores_df['Time'] == sub_times[i+1]]
        v_score.append(scores_df2['Away'].max())
        h_score.append(scores_df2['Home'].max())
                
        ## Get point diff for each sub period
        if hFlag == 0:
            score_dif = (int(v_score[k+1]) -int(v_score[k])) - (int(h_score[k+1]) - int(h_score[k]))
            filename='hoopsPlusMinusVisitor'
        else:
            score_dif = (int(h_score[k+1]) -int(h_score[k])) - (int(v_score[k+1]) - int(v_score[k]))
            filename='hoopsPlusMinusHome'
                
        ## For each timestamp, go player by player and add the pointdiff to their total
        lineup_df_list = lineup_df.values.tolist()
        j = 0
        for player in player_list:
            if player in lineup_df_list[i]:
                pm_list[j] = pm_list[j] + score_dif
            j = j + 1
        k = k + 1

    df = pd.DataFrame({'Player': player_list, '+/-': pm_list})
    df = df.sort_values(by=['+/-'], ascending=False)
    df = df.reset_index(drop=True)
    print(df)
    
    fig, ax = plt.subplots(dpi=200)
    ax.barh(df['Player'], df['+/-'], align='center', color=color)
    plt.gca().invert_yaxis()
    
    for i in range(0,len(df['Player'])):
        if len(df['Player'][i])/2 < df['+/-'][i] or len(df['Player'][i])/-2 > df['+/-'][i]:
            ax.text(df['+/-'][i]/2,i,df['Player'][i], ha='center', va='center', fontweight = 'bold',color=color2)
        elif df['+/-'][i] >= 0:
            ax.text(0,i,df['Player'][i] + ' ', ha='right', va='center',fontweight = 'bold', color=color)
        else:
            ax.text(0,i,' ' + df['Player'][i], ha='left', va='center',fontweight = 'bold', color=color)
            
        if df['+/-'][i] >= 0:
            ax.text(df['+/-'][i],i,' +' + str(df['+/-'][i]), ha='left', va='center', color=color)
        else:
            ax.text(df['+/-'][i],i,str(df['+/-'][i]) + ' ', ha='right', va='center', color=color)

    
    ## Finalize Chart
    plt.axis('off')
    fig.patch.set_facecolor(color2) 
    ax.set_facecolor(color2)
    plt.axvline(x=0, color=color)
    ax.text(0,-4,' ')
    
    if platform == "AWS":
        fig_path = '/tmp/out.png'
        team_logo_path = '/tmp/'+team+'.png'
        oppo_logo_path = '/tmp/'+oppo+'.png'
        at_path = '/tmp/plusminus.png'
        out_path = '/tmp/' + filename + '_plusminus.png'

        import boto3
        s3 = boto3.client('s3')
        s3.download_file('gtpdd', 'plusminus.png', '/tmp/plusminus.png')
    
    else:
        fig_path = 'tmp/hoopsLineupsTemp.png'
        team_logo_path = 'logo/'+team+'.png'
        oppo_logo_path = 'logo/'+oppo+'.png'
        at_path = 'img/plusminus.png'
        out_path = 'out/' + filename + '.png'
        
    plt.savefig(fig_path, bbox_inches='tight', pad_inches = 0, dpi=300)
    
    img = Image.open(fig_path)
    team_logo = Image.open(team_logo_path)
    oppo_logo = Image.open(oppo_logo_path)
    at = Image.open(at_path)
    logo_size = 250
    
    team_logo = team_logo.resize((logo_size,logo_size))
    oppo_logo = oppo_logo.resize((logo_size,logo_size))
    
    img_w, img_h = img.size
    v_offset = (int(img_w/2 - logo_size - 40) , -2)
    h_offset = (int(img_w/2) + 40 , -2)
    at_offset = (int(img_w/2)-40, 95)
    

    if filename == 'visitor':        
        img.paste(team_logo, v_offset, team_logo)
        img.paste(at, at_offset, at)
        img.paste(oppo_logo.convert('L'), h_offset, oppo_logo)
        
    else:
        img.paste(team_logo, h_offset, team_logo)
        img.paste(at, at_offset, at)
        img.paste(oppo_logo.convert('L'), v_offset, oppo_logo)
        
    img.save(out_path)
    
    if platform == 'AWS':
        import boto3
        s3 = boto3.resource("s3")
        s3.meta.client.upload_file('/tmp/' + filename + '_plusminus.png', 'gtpdd', filename + '_plusminus.png')

    return df
 
def hoopsLineups(platform, gameId, gameNum):
    x,visitorId,homeId,visitor,home,v_color,v_color2,h_color,h_color2,scores_df = getESPNAPI(platform, gameId)
    otFlag = 1
    
    def getBackgroundColors(color,color2):
        if color == "#002d65":
            color2 = "lightgray"
        else:
            color = "black"
            color2 = "lightgray"
        return color,color2
    v_color, v_color2 = getBackgroundColors(v_color,v_color2)
    h_color, h_color2 = getBackgroundColors(h_color,h_color2)
    
    print(visitor,home,h_color,v_color)
    
    home_soup = Soup((requests.get('https://latechsports.com/sports/mens-basketball/schedule')).text, features="lxml")
    box_scores = []
    lis = home_soup.find_all('li', {"class":"sidearm-schedule-game-links-boxscore"})
    for li in lis:
        box_scores.append(li.a.get("href"))
    box_scores = list(dict.fromkeys(box_scores))
    
    
    box_url = 'https://latechsports.com' + str(box_scores[gameNum])
    box_soup = Soup((requests.get(box_url)).text, features="lxml")
    tables = box_soup.find_all('table')
    
    visitorStatTable = tables[1]
    homeStatTable = tables[4]
    half1PBP = tables[7]
    half2PBP = tables[8]

    half1_df = get_pbp_table(half1PBP)
    half2_df = get_pbp_table(half2PBP)

    if otFlag:
        half3PBP = tables[9]
        half3_df = get_pbp_table(half3PBP)



    def generateDataframes(half1_df,half2_df,statTable,label):
        shots1_df = get_shots(half1_df,label)
        shots2_df = get_shots(half2_df,label)
        shots1_df['time'] = shots1_df['time'].astype(int) + 1200
        shots_df = pd.concat([shots1_df,shots2_df])
        
        subs1_df = get_subs(half1_df,label)
        subs2_df = get_subs(half2_df,label)

        lineup1_df = get_lineup(subs1_df, statTable)
        lineup2_df = get_lineup(subs2_df, statTable)
        lineup1_df['Time'] = lineup1_df['Time'].astype(int) + 1200
        lineup_df= pd.concat([lineup1_df,lineup2_df])
        return lineup_df, shots_df
    
    def generateDataframesOT(half1_df,half2_df,half3_df,statTable,label):
        shots1_df = get_shots(half1_df,label)
        shots2_df = get_shots(half2_df,label)
        shots3_df = get_shots(half3_df,label)
        shots1_df['time'] = shots1_df['time'].astype(int) + 1500
        shots2_df['time'] = shots2_df['time'].astype(int) + 300
        shots_df = pd.concat([shots1_df,shots2_df,shots3_df])
        
        subs1_df = get_subs(half1_df,label)
        subs2_df = get_subs(half2_df,label)
        subs3_df = get_subs(half3_df,label)

        lineup1_df = get_lineup(subs1_df, statTable, '20:00')
        lineup2_df = get_lineup(subs2_df, statTable, '20:00')
        lineup3_df = get_lineup(subs3_df, statTable, '05:00')
        lineup1_df['Time'] = lineup1_df['Time'].astype(int) + 1500
        lineup2_df['Time'] = lineup2_df['Time'].astype(int) + 300
        lineup_df= pd.concat([lineup1_df,lineup2_df,lineup3_df])
        return lineup_df, shots_df

    if otFlag:
        vlineup_df,vshots_df = generateDataframesOT(half1_df,half2_df,half3_df,visitorStatTable,'visitor')
        hlineup_df,hshots_df = generateDataframesOT(half1_df,half2_df,half3_df,homeStatTable,'home')
        maxTime=2700
    else:
        vlineup_df,vshots_df = generateDataframes(half1_df,half2_df,visitorStatTable,'visitor')
        hlineup_df,hshots_df = generateDataframes(half1_df,half2_df,homeStatTable,'home')
        maxTime=2400




    
    #vpm_df = get_plus_minus(vlineup_df,scores_df,visitor,home,0, v_color, v_color2, platform)
    #hpm_df = get_plus_minus(hlineup_df,scores_df,home,visitor,1, h_color, h_color2, platform)    
    
    render_full_lineup_chart(vlineup_df,vshots_df,visitor,home,v_color, v_color2,'hoopsLineupsVisitor',maxTime,platform)
    render_full_lineup_chart(hlineup_df,hshots_df,home,visitor,h_color, h_color2,'hoopsLineupsHome',maxTime,platform)
    
    '''
    if otFlag:
        ot_pbp = tables[9]
        ot_df = get_pbp_table(ot_pbp)
        v3shots_df = get_shots(ot_df,'visitor')
        h3shots_df = get_shots(ot_df,'home')
        v3subs_df = get_subs(ot_df,'visitor')
        h3subs_df = get_subs(ot_df,'home')
        print(v3subs_df)
        v3lineup_df = get_lineup(v3subs_df, first_half_visitor_table)
        h3lineup_df = get_lineup(h3subs_df, first_half_visitor_table)

        render_full_lineup_chart(v3lineup_df,v3shots_df,visitor,home,v_color, v_color2,'hoopsLineupsVisitorOT',platform)
    '''






    
    '''
    df = pd.read_csv('tmp/plusminus.csv')
    df = df.set_index('Player')
    if visitorId == '2348':
        pm_df = vpm_df
    else:
        pm_df = hpm_df
    pm_df = pm_df.set_index('Player')
    pm_df = pm_df.rename(columns={"+/-": gameId})

        
    print(df)
    print(pm_df)
    
    try: df_master = df.join(pm_df)
    except: df_master = df
    
    print(df_master)
    df_master.to_csv('tmp/plusminus.csv')
    '''

hoopsLineups('Chrome', '401700216', -1)      
