from bs4 import BeautifulSoup as Soup
import requests
import numpy as np
import pandas as pd
from pandas import DataFrame
import matplotlib.pyplot as plt
import matplotlib.colors as mc
import colorsys
from PIL import Image
from lib.common import parse_th_row, parse_mod_th_row, parse_td_row, parse_mod_td_row, createTweet
from lib.hoopsCommon import getESPNAPI
    
def get_pbp_table(table):
    stat_rows = table.find_all('tr')
    list_of_parsed_stat_rows = [parse_td_row(row) for row in stat_rows[1:]]
    stat_df = DataFrame(list_of_parsed_stat_rows)
    stat_df = stat_df.drop(columns=[2,6,7,8])
    stat_df.columns = ['time','visitor_play','visitor_score','home_score','home_play']
    df = stat_df.replace('--', np.nan)
    df = df.replace(r'^\s*$', np.nan, regex=True)
    df = df.fillna(method='ffill')
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

def get_lineup(subs_df, lineups_df):
    # Create empty row with 20:00
    lineup = [['20:00',np.nan,np.nan,np.nan,np.nan,np.nan]]
    lineup_df = pd.DataFrame(lineup, columns = ['Time','P1','P2','P3','P4','P5'])
    lineup_df = lineup_df.set_index('Time')
    
    for index, row in subs_df.iterrows(): lineup_df.loc[row['time']] = [np.nan,np.nan,np.nan,np.nan,np.nan]
    subs_df = subs_df.sort_values(by=['time','action'], ascending=False)
        
    # Go line-by-line through vsubs
    for index, row in subs_df.iterrows():
        if row['action'] == 'SUB IN ':
            
            def fillLoop(pNum):
                lineup_df.loc[row['time'],pNum] = row['player']
                lineup_df[pNum].fillna(method='ffill', inplace=True)
            
            if pd.isnull(lineup_df.loc[row['time'],'P1']): fillLoop('P1')
            elif pd.isnull(lineup_df.loc[row['time'],'P2']): fillLoop('P2')
            elif pd.isnull(lineup_df.loc[row['time'],'P3']): fillLoop('P3')
            elif pd.isnull(lineup_df.loc[row['time'],'P4']): fillLoop('P4')
            elif pd.isnull(lineup_df.loc[row['time'],'P5']): fillLoop('P5')
        
        if row['action'] == 'SUB OUT ' and row['time'] != '20:00':
            
            def subOutLoop(pNum):
                lineup_df.loc[row['time']:,pNum] = np.nan
                
            def startPlayers(pNum):
                lineup_df.loc['20:00',pNum] = row['player']

            if lineup_df.loc[row['time'],'P1'] == row['player']: subOutLoop('P1')
            elif lineup_df.loc[row['time'],'P2'] == row['player']: subOutLoop('P2')
            elif lineup_df.loc[row['time'],'P3'] == row['player']: subOutLoop('P3')
            elif lineup_df.loc[row['time'],'P4'] == row['player']: subOutLoop('P4')
            elif lineup_df.loc[row['time'],'P5'] == row['player']: subOutLoop('P5')
                
            elif pd.isnull(lineup_df.loc['20:00','P1']): startPlayers('P1')
            elif pd.isnull(lineup_df.loc['20:00','P2']): startPlayers('P2')
            elif pd.isnull(lineup_df.loc['20:00','P3']): startPlayers('P3')
            elif pd.isnull(lineup_df.loc['20:00','P4']): startPlayers('P4')
            elif pd.isnull(lineup_df.loc['20:00','P5']): startPlayers('P5')
                
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
            if row['minutes'] > '30':
                nosubs.append(row['name'])
        
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
    
    lineup_df = lineup_df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
    lineup_df = lineup_df.transpose()
    lineup_df = lineup_df.apply(lambda x: x.sort_values().values)
    lineup_df = lineup_df.transpose()
    
    ##Makes sure duplicated names are in the same column
    real_cols = ['P1','P2','P3','P4','P5']
    lineup_df['temp'] = lineup_df['P1']==lineup_df['P2'].shift(1)
    lineup_df.loc[lineup_df['temp'] == True, 'temp'] = lineup_df['P2']
    lineup_df.loc[lineup_df['temp'] != False, 'P2'] = lineup_df['P1']
    lineup_df.loc[lineup_df['temp'] != False, 'P1'] = lineup_df['temp']
    lineup_df = lineup_df.drop(columns=['temp'])
 
    for i in range(0,len(lineup_df.index)):
        for check_col in real_cols:
            for col in real_cols:
                lineup_df['temp'] = lineup_df[check_col]==lineup_df[col].shift(1)
                lineup_df.loc[lineup_df['temp'] == True, 'temp'] = lineup_df[col]
                lineup_df.loc[lineup_df['temp'] != False, col] = lineup_df[check_col]
                lineup_df.loc[lineup_df['temp'] != False, check_col] = lineup_df['temp']
                lineup_df = lineup_df.drop(columns=['temp'])
                
    ## Change timestamp in Time column to seconds
    lineup_df = lineup_df.reset_index(level=0)
    lineup_df[['Minutes','Seconds']] = lineup_df['Time'].str.split(':', expand=True)# + int(lineup_df['Time'].str.split(':').str[1])
    lineup_df['Time'] = lineup_df['Minutes'].astype(int)*60 + lineup_df['Seconds'].astype(int)
    lineup_df = lineup_df.drop(columns=['Minutes','Seconds'])
    return lineup_df


def render_full_lineup_chart(lineup_df, shots_df, team, oppo, color_code, color2, filename, platform):
    lineup_df = lineup_df.set_index('Time')
    
    ## Get list of starters and add 'gaps' for STARTERS and BENCH text
    starters = lineup_df.loc[2400.0].tolist()
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
    diff_secs.append(2400-sum(diff_secs))
    
    ## (So, I'm dumb and did the master list backwards. So rather than fix that logic, I'm just transposing the list of lists because I'm lazy)
    t_master_list = list(map(list, zip(*master_list)))
    
    ## Setup chart
    #plt.rcParams["font.family"] = "Century Gothic"
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
                if 'GOOD FT' in row['action'] and ft_time == row['time']:
                    ft_num = ft_num + 1
                    ft_den = ft_den + 1
                elif 'MISS FT' in row['action'] and ft_time == row['time']:
                    ft_den = ft_den + 1
                else:
                    ## See if this was a shooting foul (Need to check the second before the FT since box scores are weird sometimes)
                    searchfor = ['GOOD', 'MISS']
                    player_shot_attempts = player_shots[player_shots['action'].str.contains('|'.join(searchfor),na = False)]
                    times_num = len(player_shot_attempts[player_shot_attempts['time'] == ft_time]) + len(player_shot_attempts[player_shot_attempts['time'] == ft_time + 1]) + len(player_shot_attempts[player_shot_attempts['time'] == ft_time + 2])
                                                                                                         
                    if times_num == ft_den:
                        ax.text(2400 - int(ft_time),i, str(ft_num) + "/" + str(ft_den), fontsize=6, color='white', weight='bold', va='center', ha='center')
                    else:
                        ax.text(2400 - int(ft_time),i, "\n\n+" + str(ft_num), fontsize=4, color='white', weight='bold', va='center', ha='center')
                        
                    
                    ft_flag = 0
                    
                ## Need to go ahead and print if this is the player's last shot
                if k == len(player_shots) - 1:
                    ax.text(2400 - int(ft_time),i, str(ft_num) + "/" + str(ft_den), fontsize=6, color='white', weight='bold', va='center', ha='center')
                    ft_flag = 0
                    
            if 'GOOD 3PTR' in row['action']:
                ax.text(2400 - int(row['time']),i,"3", fontsize=10, color='lime', weight='bold', va='center', ha='center')
            elif 'MISS 3PTR' in row['action']:
                ax.text(2400 - int(row['time']),i,"3", fontsize=10, color='lightpink', weight='bold', va='center', ha='center')
            elif 'GOOD JUMPER' in row['action']:
                ax.text(2400 - int(row['time']),i,"2", fontsize=10, color='lime', weight='bold', va='center', ha='center')
            elif 'GOOD LAYUP' in row['action']:
                ax.text(2400 - int(row['time']),i,"2", fontsize=10, color='lime', weight='bold', va='center', ha='center')
            elif 'GOOD DUNK' in row['action']:
                ax.text(2400 - int(row['time']),i,"2", fontsize=10, color='lime', weight='bold', va='center', ha='center')
            elif 'MISS JUMPER' in row['action']:
                ax.text(2400 - int(row['time']),i,"2", fontsize=10, color='lightpink', weight='bold', va='center', ha='center')
            elif 'MISS LAYUP' in row['action']:
                ax.text(2400 - int(row['time']),i,"2", fontsize=10, color='lightpink', weight='bold', va='center', ha='center')
            elif 'MISS DUNK' in row['action']:
                ax.text(2400 - int(row['time']),i,"2", fontsize=10, color='lightpink', weight='bold', va='center', ha='center')
            elif 'REBOUND' in row['action']:
                ax.text(2400 - int(row['time']),i,"R", fontsize=6, color='yellow', weight='heavy', va='center', ha='center')
            elif 'TURNOVER' in row['action']:
                ax.text(2400 - int(row['time']),i,"T", fontsize=6, color='orange', weight='heavy', va='center', ha='center')
            elif 'ASSIST' in row['action']:
                ax.text(2400 - int(row['time']),i,"A", fontsize=6, color='yellow', weight='heavy', va='center', ha='center')
            elif 'FOUL' in row['action']:
                foul_count[i] = foul_count[i] + 1
                ax.text(2400 - int(row['time']),i,"|", fontsize=14, color='#FF3131', weight='bold', va='center', ha='center')
                ax.text(2400 - int(row['time']),i+0.4,"  " + str(foul_count[i]), fontsize=4, color='#FF3131', weight='bold', va='top', ha='center')
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
    ax.set_xlim(0,2400)
    ax.set_xticks([0,600,1200,1800,2400])
    ax.set_xticklabels(['Start','10:00 1H','Halftime','10:00 2H','End of Regulation'])
    ax.grid(axis="x", color="white", alpha=.5, linewidth=.5)
    plt.gca().invert_yaxis()
    ax.text(0,-5," ")
    ax.set_title('at\n\n ')
    ax.tick_params(axis=u'y', which=u'both',length=0)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    fig.patch.set_facecolor(color2) 
    ax.set_facecolor(color2)
 

    if platform == "Windows":
        fig_path = 'C:\\Users\\ntrup\\Google Drive\\GTPDD\\\\Coding\\out_files\\out.png'
        team_logo_path = 'C:\\Users\\ntrup\\Google Drive\\GTPDD\\\\Coding\\in_files\\team_logos\\'+team+'.png'
        oppo_logo_path = 'C:\\Users\\ntrup\\Google Drive\\GTPDD\\\\Coding\\in_files\\team_logos\\'+oppo+'.png'
        out_path = 'C:\\Users\\ntrup\\Google Drive\\GTPDD\\\\Coding\\out_files\\' + filename + '.png'
        
    
    elif platform == 'Chrome':
        fig_path = 'out_files/out.png'
        team_logo_path = 'in_files/'+team+'.png'
        oppo_logo_path = 'in_files/'+oppo+'.png'
        out_path = 'out_files/' + filename + '.png'
         
    elif platform == 'AWS':
        fig_path = '/tmp/out.png'
        team_logo_path = '/tmp/'+team+'.png'
        oppo_logo_path = '/tmp/'+oppo+'.png'
        out_path = '/tmp/' + filename + '.png'
        
        
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
    scores_df = scores_df.fillna(method="ffill")
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
            filename='visitor'
        else:
            score_dif = (int(h_score[k+1]) -int(h_score[k])) - (int(v_score[k+1]) - int(v_score[k]))
            filename='home'
                
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
    
    if platform == "Windows":
        fig_path = 'C:\\Users\\ntrup\\Google Drive\\GTPDD\\Coding\\out_files\\out.png'
        team_logo_path = 'C:\\Users\\ntrup\\Google Drive\\GTPDD\\\\Coding\\in_files\\team_logos\\'+team+'.png'
        oppo_logo_path = 'C:\\Users\\ntrup\\Google Drive\\GTPDD\\\\Coding\\in_files\\team_logos\\'+oppo+'.png'
        at_path = 'C:\\Users\\ntrup\\Google Drive\\GTPDD\\\\Coding\\in_files\\plusminus.png'
        out_path = 'C:\\Users\\ntrup\\Google Drive\\GTPDD\\Coding\\out_files\\' + filename + '_plusminus.png'
        
    
    elif platform == 'Chrome':
        fig_path = 'out_files/out.png'
        team_logo_path = 'in_files/'+team+'.png'
        oppo_logo_path = 'in_files//'+oppo+'.png'
        at_path = 'in_files/plusminus.png'
        out_path = 'out_files/' + filename + '_plusminus.png'
         
    elif platform == 'AWS':
        fig_path = '/tmp/out.png'
        team_logo_path = '/tmp/'+team+'.png'
        oppo_logo_path = '/tmp/'+oppo+'.png'
        at_path = '/tmp/plusminus.png'
        out_path = '/tmp/' + filename + '_plusminus.png'
        
        import boto3
        s3 = boto3.client('s3')
        s3.download_file('gtpdd', 'plusminus.png', '/tmp/plusminus.png')
        
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
    
    def getBackgroundColors(color,color2):
        if color > color2:
            temp = color
            color = color2
            color2 = temp  
        try:
            c = mc.cnames[color2]
        except:
            c = color2
            c = colorsys.rgb_to_hls(*mc.to_rgb(c))
            color2 = colorsys.hls_to_rgb(c[0], 1 - 0.3 * (1 - c[1]), c[2])
        return color,color2
    v_color, v_color2 = getBackgroundColors(v_color,v_color2)
    h_color, h_color2 = getBackgroundColors(h_color,h_color2)
    
    print(visitor,home,h_color,v_color)
    
    home_soup = Soup((requests.get('https://latechsports.com/sports/mens-basketball/schedule')).text)
    box_scores = []
    lis = home_soup.find_all('li', {"class":"sidearm-schedule-game-links-boxscore"})
    for li in lis:
        box_scores.append(li.a.get("href"))
    box_scores = list(dict.fromkeys(box_scores))
    
    
    box_url = 'https://latechsports.com' + str(box_scores[gameNum])
    box_soup = Soup((requests.get(box_url)).text)
    tables = box_soup.find_all('table')
    
    first_half_visitor_table = tables[1]
    first_half_home_table = tables[4]
    second_half_visitor_table = tables[1]
    second_half_home_table = tables[4]
    
    first_half_pbp = tables[7]
    second_half_pbp = tables[8]

    h1_df = get_pbp_table(first_half_pbp)
    h2_df = get_pbp_table(second_half_pbp)

    v1shots_df = get_shots(h1_df,'visitor')
    v1shots_df.to_csv('temp3.csv')
    v2shots_df = get_shots(h2_df,'visitor')
    v1shots_df['time'] = v1shots_df['time'].astype(int) + 1200
    vshots_df = pd.concat([v1shots_df,v2shots_df])
    vshots_df.to_csv('temp4.csv')
    h1shots_df = get_shots(h1_df,'home')
    h2shots_df = get_shots(h2_df,'home')
    h1shots_df['time'] = h1shots_df['time'].astype(int) + 1200
    hshots_df = pd.concat([h1shots_df,h2shots_df])

    v1subs_df = get_subs(h1_df,'visitor')
    v2subs_df = get_subs(h2_df,'visitor')
    h1subs_df = get_subs(h1_df,'home')
    h2subs_df = get_subs(h2_df,'home')

    v1lineup_df = get_lineup(v1subs_df, first_half_visitor_table)
    v2lineup_df = get_lineup(v2subs_df, second_half_visitor_table)
    v1lineup_df['Time'] = v1lineup_df['Time'].astype(int) + 1200
    vlineup_df= pd.concat([v1lineup_df,v2lineup_df])
                
    h1lineup_df = get_lineup(h1subs_df, first_half_home_table)
    h2lineup_df = get_lineup(h2subs_df, second_half_home_table)
    h1lineup_df['Time'] = h1lineup_df['Time'].astype(int) + 1200
    hlineup_df= pd.concat([h1lineup_df,h2lineup_df])

    
    vpm_df = get_plus_minus(vlineup_df,scores_df,visitor,home,0, v_color, v_color2, platform)
    hpm_df = get_plus_minus(hlineup_df,scores_df,home,visitor,1, h_color, h_color2, platform)    
    
    render_full_lineup_chart(vlineup_df,vshots_df,visitor,home,v_color, v_color2,'vlineup',platform)
    render_full_lineup_chart(hlineup_df,hshots_df,home,visitor,h_color, h_color2,'hlineup',platform)
    
    df = pd.read_csv('plusminus.csv')
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
    df_master.to_csv('plusminus.csv')
    
    
    #tweetGraphic(visitor,home,platform)
    #tweetPlusMinus(platform,visitor,home,vpm_df,hpm_df)

hoopsLineups('Chrome', '401573591', -1)      
