#!/usr/bin/env python3
"""Manual corrections to the cached CFBD play-by-play CSVs.

CFBD's play-by-play occasionally has a wrong yard line, a mislabelled play type, a
duplicated row, or a play missing outright. This applies the per-game corrections to
the CSVs under csv/fbPlaychartPBP/<year>/, so re-run it after refreshing a game:

    python fbPlaychart.py --year 2025 --week 9 --refresh-data
    python csv/fbPlaychartPBP/dataFixes.py --year 2025 --week 9

Command line:
    python csv/fbPlaychartPBP/dataFixes.py                 ## every game
    python csv/fbPlaychartPBP/dataFixes.py --year 2025 --week 9
    python csv/fbPlaychartPBP/dataFixes.py --list
    python csv/fbPlaychartPBP/dataFixes.py --dry-run -v    ## show edits, write nothing

Adding fixes for a new game: write a function taking a PbpFile, decorate it with
@gameFix(year, week, opponent), and use the six edit primitives (idempotent, so the
whole script can safely be re-run over an already-fixed CSV):

    @gameFix(2025, 11, 'Delaware')
    def fix2025Wk11Delaware(f):
        f.replace('Q1 5:47,2,10,Penalty,88,5', 'Q1 5:47,2,10,Penalty,88,-5')
        f.deleteRows('401757290419')          ## drop every row containing this text
        f.insertRow(94, '92,Delaware,...')    ## insert after line 94 (1-based, header is line 1)
        f.setRow(95, '91,Delaware,...')       ## overwrite line 95
        f.swapRows(94, 95, first='Q2 0:46')   ## put two out-of-order plays back in order
        f.moveRow(10, 2, 'Q1 15:0,1,10')      ## line 10 becomes line 2, lines 2-9 shift down

Edits run top to bottom exactly as written, and the line numbers refer to the file as it
stands at that point, so order matters once rows are added or deleted. swapRows is the
one primitive that needs help to stay idempotent: give it first=, a snippet of the row
that belongs on top, or a re-run will swap the pair straight back.
"""

import os
import re


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PBP_DIR = os.path.join(REPO_ROOT, 'csv', 'fbPlaychartPBP')

## (year, week) -> (opponent, fix function), in the order the fixes are declared below
FIXES = {}


def gameSlug(week, opponent):
    ## Matches fbPlaychart.gameSlug: 'wk<week>_<opponent>'
    opp = re.sub(r'[^0-9A-Za-z]+', '_', opponent).strip('_')
    return f"wk{week}_{opp}"


def pbpCsv(year, week, opponent):
    ## Path to a game's cached play-by-play, e.g. csv/fbPlaychartPBP/2025/fbPlaychartPBP_wk9_Western_Kentucky.csv
    return os.path.join(PBP_DIR, str(year), f"fbPlaychartPBP_{gameSlug(week, opponent)}.csv")


def gameFix(year, week, opponent):
    ## Register a game's fix function so applyFixes() picks it up
    def register(fn):
        FIXES[(year, week)] = (opponent, fn)
        return fn
    return register


class PbpFile:
    """A play-by-play CSV held in memory while its fixes are applied.

    Every edit reports one of three outcomes so a fix that silently stops matching
    (because CFBD changed the underlying data) shows up instead of passing quietly:
      applied  - the edit changed the file
      already  - the file is already in the fixed state, nothing to do
      MISSING  - neither the before nor the after state was found
    """

    def __init__(self, path):
        with open(path) as f:
            self.lines = f.read().split('\n')
        ## A trailing newline leaves an empty last element; remember it for the rewrite
        self.trailingNewline = self.lines and self.lines[-1] == ''
        if self.trailingNewline:
            self.lines.pop()
        self.path = path
        self.original = list(self.lines)
        self.log = []

    def _record(self, status, what):
        self.log.append((status, what))

    def replace(self, old, new):
        ## Literal text substitution over every line, like sed 's/old/new/g'
        hits = 0
        for i, line in enumerate(self.lines):
            if old in line:
                self.lines[i] = line.replace(old, new)
                hits += 1
        if hits:
            self._record('applied', f"replace {old!r} -> {new!r}")
        elif any(new in line for line in self.lines):
            self._record('already', f"replace {old!r} -> {new!r}")
        else:
            self._record('MISSING', f"replace {old!r} -> {new!r}")
        return hits

    def deleteRows(self, needle):
        ## Drop every line containing needle, like sed '/needle/d'
        kept = [line for line in self.lines if needle not in line]
        dropped = len(self.lines) - len(kept)
        self.lines = kept
        self._record('applied' if dropped else 'already',
                     f"delete {dropped} row(s) containing {needle!r}")
        return dropped

    def insertRow(self, afterLine, row, guard=None):
        ## Insert a row after line afterLine (1-based, header is line 1), like sed '<n>a\'.
        ## guard identifies the row for re-runs; it defaults to the row's first six
        ## fields (index, offense, clock, down, distance, type), which pin down the play
        ## without depending on values a later fix might still change.
        if guard is None:
            guard = ','.join(row.split(',')[:6])
        if any(guard in line for line in self.lines):
            self._record('already', f"insert after line {afterLine}: {guard}")
            return False
        if not 0 < afterLine <= len(self.lines):
            self._record('MISSING', f"insert after line {afterLine}: no such line "
                                    f"(file has {len(self.lines)} lines)")
            return False
        self.lines.insert(afterLine, row)
        self._record('applied', f"insert after line {afterLine}: {guard}")
        return True

    def setRow(self, lineNo, row):
        ## Overwrite line lineNo (1-based, header is line 1), like sed '<n>c\'
        if not 0 < lineNo <= len(self.lines):
            self._record('MISSING', f"set line {lineNo}: no such line "
                                    f"(file has {len(self.lines)} lines)")
            return False
        if self.lines[lineNo - 1] == row:
            self._record('already', f"set line {lineNo}")
            return False
        self.lines[lineNo - 1] = row
        self._record('applied', f"set line {lineNo}")
        return True

    def swapRows(self, lineA, lineB, first=None):
        ## Exchange two lines (1-based, header is line 1), for a pair of plays the
        ## source returned out of order. Pass first= a snippet of the row that belongs
        ## on top and the edit is idempotent like the rest; a bare swap has no way to
        ## tell a fixed file from a broken one, so re-running the script undoes it.
        for lineNo in (lineA, lineB):
            if not 0 < lineNo <= len(self.lines):
                self._record('MISSING', f"swap lines {lineA} and {lineB}: no line {lineNo} "
                                        f"(file has {len(self.lines)} lines)")
                return False
        a, b = lineA - 1, lineB - 1
        if first is not None:
            if first in self.lines[a]:
                self._record('already', f"swap lines {lineA} and {lineB}: {first!r} already on top")
                return False
            if first not in self.lines[b]:
                self._record('MISSING', f"swap lines {lineA} and {lineB}: neither holds {first!r}")
                return False
        self.lines[a], self.lines[b] = self.lines[b], self.lines[a]
        note = '' if first is not None else ' (unguarded: re-running undoes it)'
        self._record('applied', f"swap lines {lineA} and {lineB}{note}")
        return True

    def moveRow(self, fromLine, toLine, match):
        ## Pull line fromLine out and reinsert it so it becomes line toLine (1-based,
        ## header is line 1); the rows in between shift up or down by one to close the
        ## gap. match is a snippet of the row being moved, so a re-run finds it already
        ## sitting at toLine instead of moving whatever has since landed on fromLine.
        for lineNo in (fromLine, toLine):
            if not 0 < lineNo <= len(self.lines):
                self._record('MISSING', f"move line {fromLine} to {toLine}: no line {lineNo} "
                                        f"(file has {len(self.lines)} lines)")
                return False
        if match in self.lines[toLine - 1]:
            self._record('already', f"move line {fromLine} to {toLine}: {match!r} already there")
            return False
        if match not in self.lines[fromLine - 1]:
            self._record('MISSING', f"move line {fromLine} to {toLine}: line {fromLine} "
                                    f"does not hold {match!r}")
            return False
        self.lines.insert(toLine - 1, self.lines.pop(fromLine - 1))
        self._record('applied', f"move line {fromLine} to {toLine}: {match!r}")
        return True

    def changed(self):
        return self.lines != self.original

    def save(self):
        text = '\n'.join(self.lines) + ('\n' if self.trailingNewline else '')
        with open(self.path, 'w') as f:
            f.write(text)


## ---------------------------------------------------------------- 2025 ----
@gameFix(2025, 1, 'SE Louisiana')
def fix2025Wk1SELouisiana(f):
    f.replace('Q1 0:0,4,11,Punt,92,28','Q1 0:0,4,11,Punt,92,43')
    f.swapRows(45,49,"401757221102919601")
    f.swapRows(46,62,"401757221102924201")
    f.swapRows(47,63,"401757221102924202")
    f.swapRows(48,64,"401757221102927501")
    f.swapRows(49,69,"401757221102946301")
    f.swapRows(50,70,"401757221102955701")
    f.swapRows(51,71,"401757221102955703")
    f.swapRows(52,72,"401757221102955704")
    f.swapRows(53,73,"401757221102955705")
    f.swapRows(54,69,"401757221102899301")
    f.swapRows(55,62,"401757221102899303")
    f.swapRows(56,63,"401757221102899304")
    f.swapRows(57,64,"401757221102899305")
    f.swapRows(58,70,"401757221102919602")
    f.swapRows(59,71,"401757221102919604")
    f.replace('Q2 8:3,1,10,Penalty,82,15','Q2 8:3,1,10,Penalty,82,20')
    f.swapRows(60,72,"401757221102919605")
    f.swapRows(61,73,"401757221102919606")
    f.swapRows(62,69,"401757221102919607")
    f.swapRows(63,69,"401757221102919608")
    f.swapRows(64,69,"401757221102919609")
    f.swapRows(65,69,"401757221102919610")
    f.swapRows(66,70,"401757221102919611")
    f.swapRows(67,71,"401757221102919612")
    f.swapRows(68,72,"401757221102919613")
    f.swapRows(69,73,"401757221102919614")
    f.swapRows(71,73,"401757221102937303")
    f.swapRows(72,73,"401757221102937304")
    f.replace('Q2 0:47,4,20,Punt,53,53','Q2 0:47,4,20,Punt,43,43')
    f.deleteRows('401757221103849903')

    f.replace('Louisiana Tech,Q2 8:3,1,10,Rush,49,6','Louisiana Tech,Q2 15:0,1,10,Rush,49,6')
    f.replace('SE Louisiana,Q2 4:42,1,10,Pass Reception,73,0','SE Louisiana,Q2 12:00,1,10,Pass Reception,73,0')

@gameFix(2025, 2, 'LSU')
def fix2025Wk2Lsu(f):
    f.replace('401752687102886801,0,14', '401752687102886801,0,7')
    f.replace('Q2 0:32,4,16,Punt,63,46', 'Q2 0:32,4,16,Punt,63,56')
    f.replace('Q2 0:32,4,16,Punt Return,17,3', 'Q2 0:32,4,16,Punt Return,7,3')


@gameFix(2025, 3, 'New Mexico State')
def fix2025Wk3NewMexicoState(f):
    f.insertRow(36, '36,New Mexico State,Q1 5:36,1,10,Penalty,79,29,"John Hoyet Chance kickoff for 78 yds , Dijon Stanley return for 19 yds to the NMSU 39 Louisiana Tech Penalty, Fighting (John Hoyet Chance) to the 50 yard line",401757257101946303,3,0')
    f.replace('Q3 9:5,4,6,Punt,44,40', 'Q3 9:5,4,6,Punt,54,32')
    f.replace('Q3 7:2,4,3,Punt,77,46', 'Q3 7:2,4,3,Punt,77,63')
    f.replace('Q3 7:2,4,3,Punt Return,31,12', 'Q3 7:2,4,3,Punt Return,14,12')


@gameFix(2025, 4, 'Southern Miss')
def fix2025Wk4SouthernMiss(f):
    f.insertRow(43, '42,Louisiana Tech,Q1 3:29,1,10,Kickoff Return (Offense),1,35,"Exact play missing from box score",401757257101946303,10,10')


@gameFix(2025, 5, 'UTEP')
def fix2025Wk5Utep(f):
    f.deleteRows('401757272101947501')
    f.replace('35,UTEP,Q1 5:24,4,8,Punt,73,39,', '35,UTEP,Q1 5:24,4,8,Punt,73,62,')
    f.replace('36,Louisiana Tech,Q1 5:24,4,8,Punt Return,34,12', '36,Louisiana Tech,Q1 5:24,4,8,Punt Return,11,12')
    f.deleteRows('401757272102905603')
    f.insertRow(69, '70,Louisiana Tech,Q2 9:42,1,10,Penalty,38,-29,"Exact play missing from box score",401757257101946303,10,10')
    f.replace('Q2 0:3,3,6,Fumble Recovery (Own),77,-13', 'Q2 0:3,3,6,Fumble Recovery (Opponent),77,-47')
    f.replace('UTEP,Q3 12:32,1,10,Pass Reception,37,2', 'UTEP,Q3 12:32,1,10,Pass Reception,37,17')
    f.replace('Q4 10:30,2,8,Fumble Recovery (Own),31,7', 'Q4 10:30,2,8,Fumble Recovery (Opponent),31,7')
    f.replace('Q4 5:21,1,10,Penalty,85,5', 'Q4 5:21,1,10,Penalty,85,11')


@gameFix(2025, 7, 'Kennesaw State')
def fix2025Wk7KennesawState(f):
    f.insertRow(25, '24,Kennesaw State,Q1 7:11,0,8,Penalty,88,-6,"Kennesaw State Penalty, Offensive Holding (6 Yards) to the KENN 6",401757257101946303,10,10')
    f.insertRow(109, '105,Louisiana Tech,Q3 15:0,0,10,Penalty,26,-10,"Louisiana Tech Penalty, Offensive Holding (10 Yards) to the LT 16",401757257101946303,10,10')


@gameFix(2025, 9, 'Western Kentucky')
def fix2025Wk9WesternKentucky(f):
    f.replace('Q1 6:46,3,6,Pass Reception,94,6', 'Q1 6:46,3,6,Passing Touchdown,94,6')
    f.replace('Q1 1:9,3,5,Pass Reception,15,15', 'Q1 1:9,3,5,Passing Touchdown,15,15')
    f.replace('Q2 10:41,1,1,Rush,1,1', 'Q2 10:41,1,1,Rushing Touchdown,1,1')
    f.replace('Q2 10:32,1,10,Kickoff,65,-37', 'Q2 10:32,1,10,Kickoff,65,-65')
    f.replace('Q2 10:32,1,10,Kickoff,65,28', 'Q2 10:32,1,10,Kickoff,65,-65')
    f.insertRow(58, '57,Louisiana Tech,Q2 10:32,1,10,Kickoff Return (Offense),0,28,"#1 D.Gandy return 28 yards to the LAT28 (#25 X.Griffin)",401757257101946303,10,10')
    f.replace('Q2 2:28,1,10,Kickoff,65,-45', 'Q2 2:28,1,10,Kickoff,65,-30')
    f.insertRow(81, '79,Louisiana Tech,Q2 2:28,0,10,Penalty,35,-15,"PENALTY LAT Personal Foul (#4 C.Thevenin) 15 yards from LAT35 to LAT20",401757257101946303,10,10')
    f.replace('Q2 1:5,2,6,Penalty,76,10', 'Q2 1:5,2,6,Penalty,76,-10')
    f.setRow(94, '92,Louisiana Tech,Q2 0:46,2,16,Rush,66,1,Shotgun #5 B.Baker rush middle for 1 yard gain to the WKU33,401757286397,7,20')
    f.setRow(95, '91,Louisiana Tech,Q2 0:47,3,15,Pass Reception,67,20,"Shotgun #5 B.Baker pass complete short left to #4 C.Thevenin caught at WKU34, for 20 yards to the WKU13, out of bounds at WKU13, 1ST DOWN",401757286401,7,20')
    f.deleteRows('401757286406')
    f.replace('Louisiana Tech,Q2 0:0,4,2,End Period,95,-3', 'Louisiana Tech,Q2 0:0,4,2,End of Half,95,-3')
    f.replace('Q3 14:45,1,10,Kickoff,65,-30', 'Q3 14:45,1,10,Kickoff,65,-57')
    f.insertRow(105, '102,Louisiana Tech,Q3 14:45,0,10,Return Touchdown,8,92,"#4 C.Thevenin return 7 yards to the LAT15 lateral to #1 D.Gandy TOUCHDOWN, clock 14:45 #48 J.Chance kick attempt good (H: #29 L.Matthews, LS: #41 E.Burch)",401757257101946303,20,14')
    f.replace('401757257101946303,20,14', '401757257101946303,14,20')
    f.deleteRows('401757286927')
    f.replace('Western Kentucky,Q3 14:1,4,6,Punt,71,0', 'Western Kentucky,Q3 14:1,4,6,Punt,71,42')
    f.replace('Louisiana Tech,Q3 11:44,2,8,Penalty,70,5', 'Louisiana Tech,Q3 11:44,2,8,Penalty,70,-5')
    f.replace('Western Kentucky,Q3 8:13,4,3,Punt Return,69,0', 'Western Kentucky,Q3 8:13,4,3,Punt,69,37')
    f.replace('Q3 7:1,4,4,Penalty,38,5', 'Q3 7:1,4,4,Penalty,38,-5')
    f.replace('Q3 6:48,4,9,Punt,33,0', 'Q3 6:48,4,9,Punt,33,50')
    f.replace('Q3 6:9,2,16,Penalty,89,5', 'Q3 6:9,2,16,Penalty,89,-5')
    f.replace('Q3 3:17,1,10,Penalty,55,10', 'Q3 3:17,1,10,Penalty,55,-10')
    f.replace('Q4 8:43,1,10,Penalty,64,10', 'Q4 8:43,1,10,Penalty,64,-10')
    f.replace('Q5 0:0,3,2,Rush,98,2', 'Q5 0:0,3,2,Rushing Touchdown,98,2')
    f.replace('Q5 0:0,1,4,Rush,4,4', 'Q5 0:0,1,4,Rushing Touchdown,4,4')


@gameFix(2025, 10, 'Sam Houston')
def fix2025Wk10SamHouston(f):
    f.replace('Q1 5:47,2,10,Penalty,88,5', 'Q1 5:47,2,10,Penalty,88,-5')
    f.replace('Q1 5:31,2,15,Penalty,93,3', 'Q1 5:31,2,15,Penalty,93,-3')
    f.replace('Q1 5:2,2,18,Pass Reception,96,7', 'Q1 5:2,2,18,Penalty,96,22')
    f.replace('Q2 10:59,4,9,Punt Return,10,21', 'Q2 10:59,0,9,Penalty,10,-5')
    f.replace('Q2 0:0,1,10,End Period,98,0', 'Q2 0:0,1,10,End of Half,98,0')
    f.insertRow(94, '92,Sam Houston,Q3 15:0,0,10,Penalty,75,-12,"#48 J.Chance kickoff 65 yards to the SHU00, Touchback PENALTY SHU UNR: Unnecessary Roughness (#8 C.Johnson) 12 yards from SHU25 to SHU13",401757290388,27,0')
    f.replace('Q3 12:56,4,2,Pass Incompletion,64,15', 'Q3 12:56,4,2,Pass Incompletion,64,0')
    f.deleteRows('401757290419')
    f.replace('Q3 12:56,1,10,Penalty,64,15', 'Q3 12:56,0,10,Penalty,64,-15')
    f.deleteRows('401757257101946303')
    f.replace('Q4 15:0,3,10,Penalty,80,5', 'Q4 15:0,3,10,Penalty,80,-5')
    f.replace('Q4 15:0,2,11,Penalty,16,5', 'Q4 15:0,2,11,Penalty,16,-5')
    f.replace('Q4 15:0,3,13,Penalty,18,5', 'Q4 15:0,3,13,Penalty,18,-5')
    f.deleteRows('401757290658')
    f.replace('Q4 11:13,2,10,Pass Incompletion,29,-5,No Huddle-Shotgun #3 M.Mettauer pass incomplete short middle to #5 L.Adkism thrown to LAT20,401757290716,14,48',
              'Q4 11:13,2,10,Penalty,29,-5,PENALTY SHU Delay Of Game 5 yards from LAT29 to LAT34. NO PLAY,401757290731,14,48')
    f.deleteRows('401757290730')
    f.replace('Q4 11:13,1,10,Pass Reception,75,15', 'Q4 11:13,1,10,Penalty,75,0')
    f.deleteRows('Q4 3:32,4,13,Punt Return,40,20')

@gameFix(2025, 11, 'Delaware')
def fix2025Wk11Delaware(f):
    f.replace('Q2 0:0,1,10,End Period,75,25', 'Q2 0:0,1,10,End of Half,75,25')
    f.replace('Q3 15:0,2,10,Penalty,62,13', 'Q3 15:0,2,10,Penalty,62,-7')
    f.insertRow(109,'107,Delaware,Q3 12:5,0,6,Penalty,84,15,"PENALTY TECH Face Mask (#15 D.Pierro) 15 yards from DEL16 to DEL31, 1ST DOWN",401757295444,7,9')
    f.replace('Q3 7:3,2,6,Penalty,82,9','Q3 7:3,2,6,Penalty,82,-9')
    f.replace('Q4 15:0,1,10,Penalty,72,5', 'Q4 15:0,1,10,Penalty,72,-5')
    f.replace('Q4 9:2,2,8,Penalty,76,10','Q4 9:2,2,8,Penalty,76,-10')
    f.replace('Q4 6:41,1,10,Pass Reception,75,3','Q4 6:41,1,10,Penalty,75,-7')
    f.replace('Q4 3:9,3,10,Penalty,75,5','Q4 3:9,3,10,Penalty,75,-5')
    f.deleteRows('Louisiana Tech,Q4 0:33,1,10,Kickoff,65,-31')
    f.insertRow(192,'193,Delaware,Q4 0:33,1,10,Onside Kickoff,65,25,#91 N.Reed onside kickoff 25 yards to the TECH40,401757295796,22,27')
    f.insertRow(198,'196,Louisiana Tech,Q4 0:6,0,0,Kickoff,80,-45,#91 N.Reed kickoff 45 yards to the TECH35 #1 D.Gandy return 0 yards to the TECH35 (#58 C.Gallagher),401757295817,24,25')
    f.replace('Delaware,Q4 0:6,0,0,Penalty,80,10','Louisiana Tech,Q4 0:6,0,0,Penalty,35,-10')
    f.replace('Delaware,Q4 0:12,0,0,Penalty,65,15','Louisiana Tech,Q4 0:12,0,0,Penalty,65,15')
    f.deleteRows('401757295855')

@gameFix(2025, 12, 'Washington_State')
def fix2025Wk12WashingtonState(f):
    f.replace('Q1 9:53,2,8,Penalty,21,5','Q1 9:53,2,8,Penalty,21,-5')
    f.replace('Q1 4:3,2,5,Penalty,32,10','Q1 4:3,2,5,Penalty,32,-10')
    f.replace('Q1 1:39,2,9,Penalty,4,2','Q1 1:39,2,9,Penalty,4,-2')
    f.insertRow(72,'69,Louisiana Tech,Q2 3:45,0,0,Penalty,80,-15,(03:52) No Huddle-Shotgun #2 T.Kukuk rush left for 4 yards gain to the WSU20 (#1 T.Large) PENALTY LAT UNS: Unsportsmanlike Conduct (#2 T.Kukuk) 15 yards from WSU20 to WSU35,401752953284,0,14')
    f.replace('Q3 4:56,2,8,Penalty,49,15','Q3 4:56,2,8,Penalty,49,0')
    f.replace('Q4 10:35,1,10,Penalty,88,15','Q4 10:35,1,10,Penalty,88,-15')

@gameFix(2025, 13, 'Liberty')
def fix2025Wk13Liberty(f):
    f.insertRow(34,'32,Louisiana Tech,Q1 1:49,0,0,Penalty,35,15,"(01:51) Shotgun #22 O.Wiggins rush left for 2 yards gain to the LAT35 (#97 M.Jarvis; #13 D.Harmon), 1ST DOWN, PENALTY LUF Face Mask (#97 M.Jarvis) 15 yards from LAT35 to LAT50, 1ST DOWN",401757307132,7,3')
    f.replace('Q2 8:38,2,5,Penalty,40,5','Q2 8:38,2,5,Penalty,40,-5')
    f.replace('Q2 4:1,3,8,Penalty,30,10','Q2 4:1,3,8,Penalty,30,-10')
    f.swapRows(93,94,'Field Goal Missed')
    f.replace('Q4 10:24,1,10,Penalty,75,10','Q4 10:24,1,10,Penalty,75,-10')
    f.replace('Q5 0:0,2,7,Pass Interception Return,22,-53','Q5 0:0,2,7,Pass Interception Return,22,0')

@gameFix(2025, 14, 'Missouri_State')
def fix2025Wk14MissouriState(f):
    f.swapRows(54,55,'Q2 13:45,1,10,Pass Incompletion')
    f.insertRow(80,'78,Louisiana Tech,Q2 1:3,0,0,Penalty,34,-19,#36 Y.Obeid kickoff 65 yards to the LTU00 #1 D.Gandy return 34 yards to the LTU34 (#36 Y.Obeid) PENALTY LTU Holding (#4 C.Thevenin) 10 yards from LTU25 to LTU15,401757314319,10,14')
    f.replace('Q3 10:48,4,19,Fumble,62,11','Q3 10:48,4,19,Rush,62,11')
    f.replace('Q3 10:48,3,5,Penalty,95,5','Q3 10:48,3,5,Penalty,95,-5')
    f.replace('Q3 7:21,2,6,Rush,26,3','Q3 7:21,2,6,Rush,26,16')
    f.insertRow(115,'112,Louisiana Tech,Q3 7:21,0,0,Penalty,42,-23,No Huddle-Shotgun #0 A.Burnette rush left for 16 yards gain (3) to the LTU42 (#44 K.Young) PENALTY LTU Holding (#55 L.Nelson) 10 yards from LTU29 to LTU19,401757314457,21,17')
    f.swapRows(138,139,'Q4 14:12,4,4,Punt,69,48')
    f.insertRow(144,'141,Louisiana Tech,Q4 9:15,1,10,Kickoff,65,-58,"Y. Obeid kickoff for 58 yds, D. Gandy returns for 93 yds for a TD (K. Kent KICK)",401757314588,23,35')
    f.replace('Missouri State,Q4 9:15,1,10,Kickoff Return Touchdown,65,93,"Y. Obeid kickoff for 58 yds, D. Gandy returns for 93 yds for a TD (K. Kent KICK)",401757314588,23,35','Louisiana Tech,Q4 9:15,1,10,Return Touchdown,7,93,"Y. Obeid kickoff for 58 yds, D. Gandy returns for 93 yds for a TD (K. Kent KICK)",401757314588,35,23')

@gameFix(2025, 16, 'Coastal_Carolina')
def fix2025Wk16CoastalCarolina(f):
    f.replace('Q1 12:30,2,11,Pass Reception,48,7','Q1 12:30,2,11,Pass Reception,48,25')
    f.insertRow(13,'11,Coastal Carolina,Q1 12:30,2,11,Penalty,23,10,"Tad Hudson pass complete to Robby Washington for 21 yds to the LT 27 for a 1ST down Coastal Carolina Penalty, Personal Foul (14 Yards) to the LT 14 for a 1ST down",401778325101876901,0,0')
    f.replace('Q1 12:15,1,10,Pass Incompletion,41,0','Q1 12:15,1,10,Pass Incompletion,14,0')
    f.replace('Q1 12:0,2,10,Penalty,41,-5','Q1 12:0,2,10,Penalty,14,-5')
    f.replace('Q1 11:30,1,10,Rush,18,6','Q1 11:30,2,10,Rush,18,6')
    f.replace('Q1 11:0,2,4,Pass Incompletion,12,0','Q1 11:0,3,4,Pass Incompletion,12,0')
    f.insertRow(34,'31,Coastal Carolina,Q1 5:38,0,10,Penalty,70,-10,"John Hoyet Chance punt for 56 yds , Bryson Graves returns for 1 yd to the CCU 16 Coastal Carolina Penalty, Illegal Block (10 Yards) to the CCU 20",401778325101946101,0,0')
    f.deleteRows('401778325101988702')
    f.deleteRows('Q2 1:16,1,10,Rush,65,5')
    f.insertRow(107,'105,Coastal Carolina,Q2 0:37,0,0,Penalty,55,-10,"John Hoyet Chance punt for 56 yds , Bryson Graves returns for 10 yds to the CCU 19 Coastal Carolina Penalty, Illegal Block (10 Yards) to the CCU 35",401778325102996201,3,14')
    f.insertRow(108,'100,Coastal Carolina,Q2 0:37,1,10,Rush,65,5,Jevon Edwards run for 5 yds to the CCU 40,401778325102999901,14,3')
    f.replace('Q3 11:45,4,11,Kickoff,35,-47','Q3 11:45,4,11,Kickoff,35,-30')
    f.replace('Q3 9:28,2,4,Sack,78,-4','Q3 9:28,2,4,Fumble Recovery (Opponent),78,-4')
    f.insertRow(138,'134,Coastal Carolina,Q3 6:23,0,0,FG Recovery (Opponent),5,-28,"Kian Afrookhteh 22 yd FG BLOCKED blocked by Kenyatta McNeese Afrookhteh, Kian field goal attempt from 22 blocked, recovered by LATECH Foster, Jakari at LATECH20 spot at LATECH20 (blocked by McNeese, Kenyatta), Foster, Jakari for 13 yards to the LATECH33. Jakari Foster return for 13 yds to the LT 33",401778325103937601,14,6')
    f.replace('Q3 4:51,4,11,Punt,32,40','Q3 4:51,4,11,Punt,32,68')
    f.replace('Q4 11:20,2,7,Sack,72,0','Q4 11:20,2,7,Penalty,72,-10')
    f.replace('Q4 4:10,2,8,Rush,53,-1','Q4 4:10,2,8,Fumble Recovery (Opponent),53,-1')
    f.insertRow(203,'198,Louisiana Tech,Q4 2:13,0,1,Penalty,70,10,"John Hoyet Chance punt for 49 yds, fair catch by Bryson Graves at the CCU 30 Coastal Carolina Penalty, Offensive Holding (10 Yards) to the CCU 20",401778325104978601,20,14')

@gameFix(2026, 1, 'Northwestern_State')
def fix2026Wk1NorthwesternState(f):
    f.replace('Q1 7:52,1,10,Pass Reception','Q1 7:52,1,10,Passing Touchdown')

@gameFix(2026, 2, 'LSU')
def fix2026Wk2LSU(f):
    f.replace('Q1 0:8,1,10,Pass Reception,56,8','Q1 0:8,1,10,Penalty,56,-2')
    f.replace('Q2 14:59,1,12,Fumble Recovery (Opponent),58,35','Q2 14:59,1,12,Fumble Recovery (Opponent),58,-23')
    f.replace('Q3 10:12,4,6,Field Goal Good,6,25','Q3 10:12,4,6,Field Goal Good,11,25')
    f.replace('Q3 6:46,1,10,Rush,60,3','Q3 6:46,1,10,Penalty,60,18')
    f.replace('Q4 9:31,1,10,Kickoff,0,-65','Q4 9:31,1,10,Kickoff,65,-65')
    f.replace('Q4 9:31,1,10,Kickoff Return (Offense),-65,32','Q4 9:31,1,10,Kickoff Return (Offense),0,32')
    f.replace('Q4 2:37,1,10,Rush,34,-22','Q4 2:37,1,10,Penalty,34,-10')

@gameFix(2026, 3, 'Baylor')
def fix2026Wk3Baylor(f):
    f.replace('Q2 7:21,1,10,Pass Reception,59,5','Q2 7:21,1,10,Penalty,59,-5')
    f.replace('Q2 6:55,1,15,Rush,49,7','Q2 6:55,1,15,Rush,54,7')
    f.replace('Q2 5:48,2,10,Pass Incompletion,75,-75','Q2 5:48,2,10,Pass Incompletion,75,0')
    f.replace('Q3 8:41,2,8,Pass Reception,81,3','Q3 8:41,2,8,Penalty,81,18')
    f.insertRow(169,'167,Louisiana Tech,Q4 6:21,0,10,Penalty,74,15,"(06:32) No Huddle #2 T.Kukuk pass complete deep right to #84 E.Finley caught at BAYLOR27, for 21 yards to the BAYLOR26 (#24 M.Gifford; #41 K.Burns), 1ST DOWN, PENALTY BAYLOR Roughing The Passer (#91 T.Mitchell) 13 yards from BAYLOR26 to BAYLOR13, 1ST DOWN",401867804755,13,29')
    f.deleteRows('401867804787')
    f.replace('Q4 1:1,2,8,Rush,46,1','Q4 1:1,2,8,Penalty,46,-10')
    
    
@gameFix(2026, 5, 'Army')
def fix2026Wk5Army(f):
    f.moveRow(13,2,'Q1 14:54,1,10,Kickoff,65,-63')
    f.moveRow(14,3,'Q1 14:54,1,10,Kickoff Return')
    f.moveRow(28,4,'Q1 3:42,1,10,Rush')
    f.moveRow(31,39,'Q1 1:20,1,10,Rush,61,14')
    f.moveRow(31,39,'Q1 1:20,1,10,Penalty,47,-15')
    f.moveRow(31,39,'Q1 1:20,1,25,Rush,62,2')
    f.deleteRows('401869842232')
    f.insertRow(102,'101,Army,Q3 11:39,0,0,Penalty,63,-23,#31 H.Rioux kickoff 59 yards to the AWP06 #27 S.Howard return 31 yards to the AWP37 (#31 H.Rioux) PENALTY AWP Illegal Block in Back declined AWP Holding (#20 T.Kloska) 10 yards from AWP24 to AWP14,401869842425,22,15')
    f.insertRow(147,'146,Army,Q4 7:28,0,0,Penalty,61,15,"#27 S.Howard rush left for 6 yards gain to the AWP39 (#22 J.Mayfield), 1ST DOWN, PENALTY LAT Horse Collar Tackle (#22 J.Mayfield) 15 yards from AWP39 to LAT46, 1ST DOWN",401869842607,22,31')
    f.insertRow(160,'156,Louisiana Tech,Q4 3:52,0,0,Penalty,39,15,"(03:52) Shotgun #2 T.Kukuk rush left for 8 yards gain to the LAT39 (#50 D.Miller; #42 E.Walton), 1ST DOWN, PENALTY AWP Face Mask (#11 D.Thom-Rogers) 15 yards from LAT39 to AWP46, 1ST DOWN",401869842651,31,22')
    f.moveRow(180,178,'Q4 1:6,1,10,Kickoff,65,-10')
      ## ---------------------------------------------------------------- run ----


def applyGameFixes(year, week, dryRun=False, verbose=False):
    ## Apply one game's fixes; returns the PbpFile, or None if the CSV isn't cached yet
    opponent, fn = FIXES[(year, week)]
    path = pbpCsv(year, week, opponent)
    label = f"{year} wk{week} {opponent}"
    if not os.path.isfile(path):
        print(f"{label}: no CSV at {os.path.relpath(path, REPO_ROOT)}, skipped")
        return None

    f = PbpFile(path)
    fn(f)

    counts = {'applied': 0, 'already': 0, 'MISSING': 0}
    for status, _ in f.log:
        counts[status] += 1
    summary = f"{counts['applied']} applied, {counts['already']} already fixed"
    if counts['MISSING']:
        summary += f", {counts['MISSING']} NOT FOUND"
    print(f"{label}: {summary}")

    for status, what in f.log:
        if verbose or status == 'MISSING':
            print(f"    {status:>7}  {what}")

    if f.changed() and not dryRun:
        f.save()
    return f


def applyFixes(year=None, week=None, dryRun=False, verbose=False):
    ## Apply every registered fix, or just those for a year and/or a week
    games = [g for g in FIXES
             if (year is None or g[0] == year) and (week is None or g[1] == week)]
    if not games:
        target = ' '.join(f"{k} {v}" for k, v in (('year', year), ('week', week)) if v is not None)
        print(f"No fixes registered for {target or 'anything'}.")
        return []
    return [applyGameFixes(y, w, dryRun=dryRun, verbose=verbose) for y, w in games]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Apply manual corrections to the cached CFBD play-by-play CSVs.")
    parser.add_argument("--year", type=int, help="Only fix this season")
    parser.add_argument("--week", type=int, help="Only fix this week")
    parser.add_argument("--list", action="store_true", help="List the games that have fixes")
    parser.add_argument("--dry-run", action="store_true", help="Report the edits without writing")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print every edit")
    args = parser.parse_args()

    if args.list:
        for (y, w), (opponent, _) in FIXES.items():
            print(f"{y} wk{w:<3} {opponent}")
    else:
        applyFixes(year=args.year, week=args.week, dryRun=args.dry_run, verbose=args.verbose)
