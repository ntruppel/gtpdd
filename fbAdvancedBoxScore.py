# -*- coding: utf-8 -*-
import boto3
import cfbd
import pandas as pd
import matplotlib.pyplot as plt
import csv
import json
from lib.fbCommon import getTeamInfo
from PIL import Image
import os
from dotenv import load_dotenv
load_dotenv()

def find_win_expectancy(game_id):
    
    configuration = cfbd.Configuration()
    configuration.api_key['Authorization'] = os.environ["cfbdAuth"]
    configuration.api_key_prefix['Authorization'] = 'Bearer'
    
    api_instance = cfbd.GamesApi(cfbd.ApiClient(configuration))

    adv_box = api_instance.get_advanced_box_score(game_id=game_id)
    box = api_instance.get_team_game_stats(2024, game_id=game_id)
    print(adv_box.teams.keys())
    print(adv_box.teams['fieldPosition'])

    try: 
        if adv_box.teams.explosiveness[0].team == 'Louisiana Tech':
            tech = 0; oppo = 1
        else:
            tech = 1; oppo = 0
                
        tech_explosiveness = adv_box.teams.explosiveness[tech].overall.total
        tech_fp = adv_box.teams.field_position[tech].average_start

        tech_so = adv_box.teams.scoring_opportunities[tech].points_per_opportunity
        tech_eff = adv_box.teams.success_rates[tech].overall.total
        
        oppo_explosiveness = adv_box.teams.explosiveness[oppo].overall.total
        oppo_fp = adv_box.teams.field_position[oppo].average_start
        oppo_so = adv_box.teams.scoring_opportunities[oppo].points_per_opportunity
        oppo_eff = adv_box.teams.success_rates[oppo].overall.total
            
        if box[0].teams[0].school == 'Louisiana Tech':
            tech = 0; oppo = 1
        else:
            tech = 1; oppo = 0
        
        tech_pts = box[0].teams[tech].points
        oppo_pts = box[0].teams[oppo].points
    
        for pair in box[0].teams[tech].stats:
            if 'turnovers' in pair.category:
                tech_to = pair.stat
            
        for pair in box[0].teams[oppo].stats:
            if 'turnovers' in pair.category:
                oppo_to = pair.stat
    
    except:
        print('except')
        if adv_box.teams['explosiveness'][0]['team'] == 'Louisiana Tech':
            tech = 0; oppo = 1
        else:
            tech = 1; oppo = 0
                
        tech_explosiveness = adv_box.teams['explosiveness'][tech]['overall']['total']
        print(adv_box.teams)
        print(adv_box.teams.keys())
        tech_fp = adv_box.teams['fieldPosition'][tech]['averageStart']

        tech_so = adv_box.teams['scoringOpportunities'][tech]['pointsPerOpportunity']
        tech_eff = adv_box.teams['successRates'][tech]['overall']['total']
        
        oppo_explosiveness = adv_box.teams['explosiveness'][oppo]['overall']['total']
        oppo_fp = adv_box.teams['fieldPosition'][oppo]['averageStart']
        oppo_so = adv_box.teams['scoringOpportunities'][oppo]['pointsPerOpportunity']
        oppo_eff = adv_box.teams['successRates'][oppo]['overall']['total']
            
        if box[0].teams[0]['school'] == 'Louisiana Tech':
            tech = 0; oppo = 1
        else:
            tech = 1; oppo = 0
        
        tech_pts = box[0].teams[tech]['points']
        oppo_pts = box[0].teams[oppo]['points']
    
        for pair in box[0].teams[tech]['stats']:
            if 'turnovers' in pair['category']:
                tech_to = pair['stat']
            
        for pair in box[0].teams[oppo]['stats']:
            if 'turnovers' in pair['category']:
                oppo_to = pair['stat']
       
    
    print("")
    print("Explosiveness : 86% : " + str(tech_explosiveness) + " - " + str(oppo_explosiveness))
    print("Efficiency : 83% : " + str(tech_eff) + " - " + str(oppo_eff))
    print("Drive Finishing : 75% : " + str(tech_so) + " - " + str(oppo_so))
    print("Field Position : 72% : " + str(tech_fp) + " - " + str(oppo_fp))
    print("Turnovers : 73% : " + str(tech_to) + " - " + str(oppo_to))
    
    
    if tech_explosiveness > oppo_explosiveness:
        mult = tech_explosiveness / (tech_explosiveness + oppo_explosiveness)
        exp = mult+0.4
    elif tech_explosiveness == oppo_explosiveness:
        exp = 0.5
    else:
        mult = oppo_explosiveness / (tech_explosiveness + oppo_explosiveness)
        exp = 1-(mult+0.4)
        
    if tech_eff > oppo_eff:
        mult = tech_eff / (tech_eff + oppo_eff)
        eff = mult+0.4
    elif tech_eff == oppo_eff:
        eff = 0.5
    else:
        mult = oppo_eff / (tech_eff + oppo_eff)
        eff = 1-(mult+0.4)

        
    if tech_so > oppo_so:
        mult = tech_so / (tech_so + oppo_so)
        so = mult+0.4
    elif tech_so == oppo_so:
        so = 0.5
    else:
        mult = oppo_so / (tech_so + oppo_so)
        so = 1-(mult+0.4)
     
    tech_fp = float(tech_fp) 
    oppo_fp = float(oppo_fp)
    if tech_fp < oppo_fp:
        mult = oppo_fp / (tech_fp + oppo_fp)
        fp = mult+0.4
    elif tech_fp == oppo_fp:
        fp = 0.5
    else:
        mult = tech_fp / (tech_fp + oppo_fp)
        fp = 1-(mult+0.4)
        
    if tech_to < oppo_to:
        to = 1
    elif tech_to == oppo_to:
        to = 0.5
    else:
        to = 0
        
    if tech_pts > oppo_pts:
        result = "W"
    else:
        result = "L"
    
    win_prob = (0.86*exp + 0.83*eff + 0.75*so + 0.72*fp + 0.73*to)/3.89
    win_prob = 0
    api_response = api_instance.get_games(2024, team='Louisiana Tech')
    for game in api_response:
        temp = game.away_points
        if temp:
            if game.home_team == 'Louisiana Tech':
                win_prob = game.home_post_win_prob
            else:
                win_prob = game.away_post_win_prob

    print("Win Probability : " + "{:.1%}".format(win_prob))
    print("Actual Score : " + str(tech_pts) + " - " + str(oppo_pts))
    
    tech_list = [tech_explosiveness, tech_eff, tech_so, round(100-tech_fp,2), tech_to]
    oppo_list = [oppo_explosiveness, oppo_eff, oppo_so, round(100-oppo_fp,2), oppo_to]
    
    return oppo, result, win_prob, tech_list, oppo_list, tech_pts, oppo_pts 

def create_graphic(oppo, result, win_prob, tech_list, oppo_list, tech_pts, oppo_pts, code):

    colors = ["#002F8B",'#'+code]
    
    fig,ax = plt.subplots(4,2, figsize=(30,45))
    
    limitsList = [[1,2],[0.3,0.6],[0,7],[18,40],[0,5]]
    
    j=0
    for i in range(1,4):
        ax[i,0].barh(0,float(tech_list[j]),color=colors[0])
        ax[i,0].barh(1,float(oppo_list[j]),color=colors[1])
        
        placementLimit = limitsList[j][0]+((limitsList[j][1] - limitsList[j][0])/10)

        if float(tech_list[j]) > placementLimit:
            ax[i,0].text(float(tech_list[j]), -0.1, str(tech_list[j]), ha="right", color="white", fontsize=60)
        else:
           ax[i,0].text(float(tech_list[j]), -0.1, ' '+str(tech_list[j]), ha="left", color="black", fontsize=60)     
        
        if float(oppo_list[j]) > placementLimit:
            ax[i,0].text(float(oppo_list[j]), 0.9, str(oppo_list[j]), ha="right", color="white", fontsize=60)
        else:
            ax[i,0].text(float(oppo_list[j]), 0.9, ' '+str(oppo_list[j]), ha="left", color="black", fontsize=60)
    
        j = j+1
        if j < 4:
            placementLimit = limitsList[j][0]+((limitsList[j][1] - limitsList[j][0])/10)
            ax[i,1].barh(0,float(tech_list[j]),color=colors[0])
            ax[i,1].barh(1,float(oppo_list[j]),color=colors[1])
            
            if float(tech_list[j]) > placementLimit:
                ax[i,1].text(float(tech_list[j]), -0.1, str(tech_list[j]), ha="right", color="white", fontsize=60)
            else:
                ax[i,1].text(float(tech_list[j]), -0.1, ' '+str(tech_list[j]), ha="left", color="black", fontsize=60)
            
            if float(oppo_list[j]) > placementLimit:
                ax[i,1].text(float(oppo_list[j]), 0.9, str(oppo_list[j]), ha="right", color="white", fontsize=60)
            else:
                ax[i,1].text(float(oppo_list[j]), 0.9, ' '+str(oppo_list[j]), ha="left", color="black", fontsize=60)

        j = j+1
        
    for i in range(0,4):
        ax[i,0].axis('off')
        ax[i,1].axis('off')
    
    exp_limits = [1,2]
    eff_limits = [0.2,0.6]
    df_limits = [0,7]
    fp_limits = [18,45]
    to_limits = [0,5]
    
    
    ax[1,0].text(exp_limits[0],0.5,'Explosiveness',rotation=90,ha="right",va="center", fontsize=50)
    ax[1,1].text(eff_limits[0],0.5,'Efficiency',rotation=90,ha="right",va="center", fontsize=50)
    ax[2,0].text(df_limits[0],0.5,'Drive Finishing',rotation=90,ha="right",va="center", fontsize=50)
    ax[2,1].text(fp_limits[0],0.5,"Field Position",rotation=90,ha="right",va="center", fontsize=50)
    ax[3,0].text(to_limits[0],0.5,"Turnovers",rotation=90,ha="right",va="center", fontsize=50)
    ax[3,1].text(-1.75,0,"Win Expectancy",rotation=90,ha="right",va="center", fontsize=50)

    ax[1,0].text(exp_limits[0],0.5,'  Equivalent Points per Play', ha='left', va='center', fontsize=30)
    ax[1,1].text(eff_limits[0],0.5,'  Success Rate', ha='left', va='center', fontsize=30)
    ax[2,0].text(df_limits[0],0.5,'  Points per Trip Inside the 40 Yard Line', ha='left', va='center', fontsize=30)
    ax[2,1].text(fp_limits[0],0.5,'  Average Starting Field Position', ha='left', va='center', fontsize=30)

    ax[1,0].set_xlim(exp_limits)
    ax[1,1].set_xlim(eff_limits)
    ax[2,0].set_xlim(df_limits)
    ax[2,1].set_xlim(fp_limits)
    ax[3,0].set_xlim(to_limits)
    
    ax[0,0].text(0.5,0.5,"Louisiana Tech", fontsize=80, ha="center")
    ax[0,0].text(0.5,0.25, str(tech_pts), fontsize=100, fontweight='bold', ha="center", color=colors[0])    
    
    ax[0,1].text(0.5,0.5, str(oppo), fontsize=80, ha="center")
    ax[0,1].text(0.5,0.25, str(oppo_pts), fontsize=100, fontweight='bold', ha="center", color=colors[1])  
    
    slices = [win_prob, 1-win_prob]
    ax[3,1].pie(slices, colors=colors)
    
    ax[3,1].text(0,-0.1,"{:.2%}".format(win_prob), color="white", fontsize="80", ha="center", fontweight="bold")
    
    fig_path = 'out/fbAdvancedBoxScore.png'
        
    s3 = boto3.client('s3')
    backgroundPath = 'img/fbAdvancedBoxScoreBackground.png'
    s3.download_file('gtpdd-public-files', 'fbAdvancedBoxScoreBackground.png', 'img/fbAdvancedBoxScoreBackground.png')
    plt.savefig(fig_path, bbox_inches='tight', pad_inches = 0, dpi=120, transparent = True)
    
    img = Image.open(fig_path, 'r')
    img_w, img_h = img.size
    background = Image.open(backgroundPath, 'r')
    bg_w, bg_h = background.size
    offset = ((bg_w - img_w) // 2, (bg_h - img_h) // 2)
    background.paste(img, offset, img)
    background.save(fig_path)

    s3.upload_file('out/fbAdvancedBoxScore.png', 'gtpdd-public-files', 'fbAdvancedBoxScore.png')
    
    status = "Advanced box score from Tech's game against "+ oppo + ". Based on the stats from the game, Tech would have won this game "+"{:.2%}".format(win_prob)+ " of the time."
    print(status)
    return 0                                                                                                                                                             


def fbAdvancedBoxScore(gameId, teamId):
    oppo, result, win_prob, tech_list, oppo_list, tech_pts, oppo_pts = find_win_expectancy(gameId)
    name, color1, color2 = getTeamInfo(teamId)
    create_graphic(name, result, win_prob, tech_list, oppo_list, tech_pts, oppo_pts, color1)
    
fbAdvancedBoxScore('401640981', '2229')