## 2025 LSU
FILE=csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk2_LSU.csv
sed -i '' 's/401752687102886801,0,14/401752687102886801,0,7/g' $FILE

sed -i '' 's/Q2 0:32,4,16,Punt,63,46/Q2 0:32,4,16,Punt,63,56/g' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk2_LSU.csv
sed -i '' 's/Q2 0:32,4,16,Punt Return,17,3/Q2 0:32,4,16,Punt Return,7,3/g' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk2_LSU.csv

## 2025 NMSU
FILE=csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk3_New_Mexico_State.csv
if ! grep -q "36,New Mexico State,Q1 5:36,1,10,Penalty"  csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk3_New_Mexico_State.csv; then
sed -i '' '36a\
36,New Mexico State,Q1 5:36,1,10,Penalty,79,29,"John Hoyet Chance kickoff for 78 yds , Dijon Stanley return for 19 yds to the NMSU 39 Louisiana Tech Penalty, Fighting (John Hoyet Chance) to the 50 yard line",401757257101946303,3,0
' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk3_New_Mexico_State.csv
fi

sed -i '' 's/Q3 9:5,4,6,Punt,44,40/Q3 9:5,4,6,Punt,54,32/g' $FILE

sed -i '' 's/Q3 7:2,4,3,Punt,77,46/Q3 7:2,4,3,Punt,77,63/g' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk3_New_Mexico_State.csv
sed -i '' 's/Q3 7:2,4,3,Punt Return,31,12/Q3 7:2,4,3,Punt Return,14,12/g' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk3_New_Mexico_State.csv

## 2025 USM
if ! grep -q "42,Louisiana Tech,Q1 3:29,1,10,Kickoff Return (Offense)"  csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk4_Southern_Miss.csv; then
sed -i '' '43a\
42,Louisiana Tech,Q1 3:29,1,10,Kickoff Return (Offense),1,35,"Exact play missing from box score",401757257101946303,10,10
' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk4_Southern_Miss.csv
fi

## 2025 UTEP
sed -i '' '/401757272101947501/d' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk5_UTEP.csv
sed -i '' 's/35,UTEP,Q1 5:24,4,8,Punt,73,39,/35,UTEP,Q1 5:24,4,8,Punt,73,62,/g' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk5_UTEP.csv
sed -i '' 's/36,Louisiana Tech,Q1 5:24,4,8,Punt Return,34,12/36,Louisiana Tech,Q1 5:24,4,8,Punt Return,11,12/g' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk5_UTEP.csv

sed -i '' '/401757272102905603/d' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk5_UTEP.csv

if ! grep -q "70,Louisiana Tech,Q2 9:42,1,10,Penalty"  csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk5_UTEP.csv; then
sed -i '' '69a\
70,Louisiana Tech,Q2 9:42,1,10,Penalty,38,-29,"Exact play missing from box score",401757257101946303,10,10
' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk5_UTEP.csv
fi

sed -i '' 's/Q2 0:3,3,6,Fumble Recovery (Own),77,-13/Q2 0:3,3,6,Fumble Recovery (Opponent),77,-47/g' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk5_UTEP.csv

sed -i '' 's/UTEP,Q3 12:32,1,10,Pass Reception,37,2/UTEP,Q3 12:32,1,10,Pass Reception,37,17/g' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk5_UTEP.csv

sed -i '' 's/Q4 10:30,2,8,Fumble Recovery (Own),31,7/Q4 10:30,2,8,Fumble Recovery (Opponent),31,7/g' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk5_UTEP.csv

sed -i '' 's/Q4 5:21,1,10,Penalty,85,5/Q4 5:21,1,10,Penalty,85,11/g' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk5_UTEP.csv

## 2025 Kennesaw
if ! grep -q "24,Kennesaw State,Q1 7:11,0,8,Penalty"  csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk7_Kennesaw_State.csv; then
sed -i '' '25a\
24,Kennesaw State,Q1 7:11,0,8,Penalty,88,-6,"Kennesaw State Penalty, Offensive Holding (6 Yards) to the KENN 6",401757257101946303,10,10
' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk7_Kennesaw_State.csv
fi

if ! grep -q "105,Louisiana Tech,Q3 15:0,0,10,Penalty"  csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk7_Kennesaw_State.csv; then
sed -i '' '109a\
105,Louisiana Tech,Q3 15:0,0,10,Penalty,26,-10,"Louisiana Tech Penalty, Offensive Holding (10 Yards) to the LT 16",401757257101946303,10,10
' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk7_Kennesaw_State.csv
fi

## 2025 WKU
FILE='csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk9_Western_Kentucky.csv'
sed -i '' 's/Q1 6:46,3,6,Pass Reception,94,6/Q1 6:46,3,6,Passing Touchdown,94,6/g' $FILE

sed -i '' 's/Q1 1:9,3,5,Pass Reception,15,15/Q1 1:9,3,5,Passing Touchdown,15,15/g' $FILE

sed -i '' 's/Q2 10:41,1,1,Rush,1,1/Q2 10:41,1,1,Rushing Touchdown,1,1/g' $FILE

sed -i '' 's/Q2 10:32,1,10,Kickoff,65,-37/Q2 10:32,1,10,Kickoff,65,-65/g' $FILE
sed -i '' 's/Q2 10:32,1,10,Kickoff,65,28/Q2 10:32,1,10,Kickoff,65,-65/g' $FILE

if ! grep -q "57,Louisiana Tech,Q2 10:32,1,10,Kickoff Return (Offense)"  $FILE; then
sed -i '' '58a\
57,Louisiana Tech,Q2 10:32,1,10,Kickoff Return (Offense),0,28,"#1 D.Gandy return 28 yards to the LAT28 (#25 X.Griffin)",401757257101946303,10,10
' $FILE
fi

sed -i '' 's/Q2 2:28,1,10,Kickoff,65,-45/Q2 2:28,1,10,Kickoff,65,-30/g' $FILE

if ! grep -q "79,Louisiana Tech,Q2 2:28,0,10,Penalty,35,-15"  $FILE; then
sed -i '' '81a\
79,Louisiana Tech,Q2 2:28,0,10,Penalty,35,-15,"PENALTY LAT Personal Foul (#4 C.Thevenin) 15 yards from LAT35 to LAT20",401757257101946303,10,10
' $FILE
fi

sed -i '' 's/Q2 1:5,2,6,Penalty,76,10/Q2 1:5,2,6,Penalty,76,-10/g' $FILE

sed -i '' '94 c\
92,Louisiana Tech,Q2 0:46,2,16,Rush,66,1,Shotgun #5 B.Baker rush middle for 1 yard gain to the WKU33,401757286397,7,20
' $FILE 

sed -i '' '95 c\
91,Louisiana Tech,Q2 0:47,3,15,Pass Reception,67,20,"Shotgun #5 B.Baker pass complete short left to #4 C.Thevenin caught at WKU34, for 20 yards to the WKU13, out of bounds at WKU13, 1ST DOWN",401757286401,7,20
' $FILE

sed -i '' '/401757286406/d' $FILE

sed -i '' 's/Louisiana Tech,Q2 0:0,4,2,End Period,95,-3/Louisiana Tech,Q2 0:0,4,2,End of Half,95,-3/g' $FILE

sed -i '' 's/Q3 14:45,1,10,Kickoff,65,-30/Q3 14:45,1,10,Kickoff,65,-57/g' $FILE 

if ! grep -q "102,Louisiana Tech,Q3 14:45,0,10,Return Touchdown,8,92"  $FILE; then
sed -i '' '105a\
102,Louisiana Tech,Q3 14:45,0,10,Return Touchdown,8,92,"#4 C.Thevenin return 7 yards to the LAT15 lateral to #1 D.Gandy TOUCHDOWN, clock 14:45 #48 J.Chance kick attempt good (H: #29 L.Matthews, LS: #41 E.Burch)",401757257101946303,20,14
' $FILE
fi

sed -i '' 's/401757257101946303,20,14/401757257101946303,14,20/g' $FILE

sed -i '' '/401757286927/d' $FILE

sed -i '' 's/Western Kentucky,Q3 14:1,4,6,Punt,71,0/Western Kentucky,Q3 14:1,4,6,Punt,71,42/g' $FILE

sed -i '' 's/Louisiana Tech,Q3 11:44,2,8,Penalty,70,5/Louisiana Tech,Q3 11:44,2,8,Penalty,70,-5/g' $FILE

sed -i '' 's/Western Kentucky,Q3 8:13,4,3,Punt Return,69,0/Western Kentucky,Q3 8:13,4,3,Punt,69,37/g' $FILE

sed -i '' 's/Q3 7:1,4,4,Penalty,38,5/Q3 7:1,4,4,Penalty,38,-5/g' $FILE

sed -i '' 's/Q3 6:48,4,9,Punt,33,0/Q3 6:48,4,9,Punt,33,50/g' $FILE

sed -i '' 's/Q3 6:9,2,16,Penalty,89,5/Q3 6:9,2,16,Penalty,89,-5/g' $FILE

sed -i '' 's/Q3 3:17,1,10,Penalty,55,10/Q3 3:17,1,10,Penalty,55,-10/g' $FILE

sed -i '' 's/Q4 8:43,1,10,Penalty,64,10/Q4 8:43,1,10,Penalty,64,-10/g' $FILE

if ! grep -q "102,Louisiana Tech,Q3 14:45,0,10,Return Touchdown,8,92"  $FILE; then
sed -i '' '105a\
102,Louisiana Tech,Q3 14:45,0,10,Return Touchdown,8,92,"#4 C.Thevenin return 7 yards to the LAT15 lateral to #1 D.Gandy TOUCHDOWN, clock 14:45 #48 J.Chance kick attempt good (H: #29 L.Matthews, LS: #41 E.Burch)",401757257101946303,20,14
' $FILE
fi

sed -i '' 's/Q5 0:0,3,2,Rush,98,2/Q5 0:0,3,2,Rushing Touchdown,98,2/g' $FILE

sed -i '' 's/Q5 0:0,1,4,Rush,4,4/Q5 0:0,1,4,Rushing Touchdown,4,4/g' $FILE

## 2025 SHSU
FILE=csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk10_Sam_Houston.csv
sed -i '' 's/Q1 5:47,2,10,Penalty,88,5/Q1 5:47,2,10,Penalty,88,-5/g' $FILE
sed -i '' 's/Q1 5:31,2,15,Penalty,93,3/Q1 5:31,2,15,Penalty,93,-3/g' $FILE

sed -i '' 's/Q1 5:2,2,18,Pass Reception,96,7/Q1 5:2,2,18,Penalty,96,22/g' $FILE

sed -i '' 's/Q2 10:59,4,9,Punt Return,10,21/Q2 10:59,0,9,Penalty,10,-5/g' $FILE

sed -i '' 's/Q2 0:0,1,10,End Period,98,0/Q2 0:0,1,10,End of Half,98,0/g' $FILE

if ! grep -q "92,Sam Houston,Q3 15:0,0,10,Penalty,75"  $FILE; then
sed -i '' '94a\
92,Sam Houston,Q3 15:0,0,10,Penalty,75,-12,"#48 J.Chance kickoff 65 yards to the SHU00, Touchback PENALTY SHU UNR: Unnecessary Roughness (#8 C.Johnson) 12 yards from SHU25 to SHU13",401757290388,27,0
' $FILE
fi

sed -i '' 's/Q3 12:56,4,2,Pass Incompletion,64,15/Q3 12:56,4,2,Pass Incompletion,64,0/g' $FILE

sed -i '' '/401757290419/d' $FILE
sed -i '' 's/Q3 12:56,1,10,Penalty,64,15/Q3 12:56,0,10,Penalty,64,-15/g' $FILE

sed -i '' '/401757257101946303/d' $FILE

sed -i '' 's/Q4 15:0,3,10,Penalty,80,5/Q4 15:0,3,10,Penalty,80,-5/g' $FILE
sed -i '' 's/Q4 15:0,2,11,Penalty,16,5/Q4 15:0,2,11,Penalty,16,-5/g' $FILE
sed -i '' 's/Q4 15:0,3,13,Penalty,18,5/Q4 15:0,3,13,Penalty,18,-5/g' $FILE
sed -i '' '/401757290658/d' $FILE

sed -i '' 's/Q4 11:13,2,10,Pass Incompletion,29,-5,No Huddle-Shotgun #3 M.Mettauer pass incomplete short middle to #5 L.Adkism thrown to LAT20,401757290716,14,48/Q4 11:13,2,10,Penalty,29,-5,PENALTY SHU Delay Of Game 5 yards from LAT29 to LAT34. NO PLAY,401757290731,14,48/g' $FILE
sed -i '' '/401757290730/d' $FILE

sed -i '' 's/Q4 11:13,1,10,Pass Reception,75,15/Q4 11:13,1,10,Penalty,75,0/g' $FILE

sed -i '' '/Q4 3:32,4,13,Punt Return,40,20/d' $FILE