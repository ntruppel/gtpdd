## 2025 LSU
sed -i '' 's/Q2 0:32,4,16,Punt,63,46/Q2 0:32,4,16,Punt,63,56/g' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk2_LSU.csv
sed -i '' 's/Q2 0:32,4,16,Punt Return,17,3/Q2 0:32,4,16,Punt Return,7,3/g' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk2_LSU.csv

# 2025 NMSU
if ! grep -q "36,New Mexico State,Q1 5:36,1,10,Penalty"  csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk3_New_Mexico_State.csv; then
sed -i '' '36a\
36,New Mexico State,Q1 5:36,1,10,Penalty,79,29,"John Hoyet Chance kickoff for 78 yds , Dijon Stanley return for 19 yds to the NMSU 39 Louisiana Tech Penalty, Fighting (John Hoyet Chance) to the 50 yard line",401757257101946303,3,0
' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk3_New_Mexico_State.csv
fi

sed -i '' 's/Q3 7:2,4,3,Punt,77,46/Q3 7:2,4,3,Punt,77,63/g' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk3_New_Mexico_State.csv
sed -i '' 's/Q3 7:2,4,3,Punt Return,31,12/Q3 7:2,4,3,Punt Return,14,12/g' csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk3_New_Mexico_State.csv
