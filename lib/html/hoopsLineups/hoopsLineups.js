/* Lineup tracker page: draws the scoreboard, score tracker and lineup charts from window.GTPDD_HOOPS_GAME */
(function () {
  'use strict';

  /* '?preview' shows just the scoreboard and score tracker, sized for the link-preview screenshot */
  if (/[?&]preview\b/.test(window.location.search)) document.documentElement.classList.add('preview');

  var NS = 'http://www.w3.org/2000/svg';
  var GAME = window.GTPDD_HOOPS_GAME;
  var MANIFEST = window.GTPDD_HOOPS_GAMES || { years: [], games: {} };
  var ROOT = document.body.getAttribute('data-root') || '';
  var CURRENT = document.body.getAttribute('data-current') || '';
  var tip = document.getElementById('hl-tooltip');
  if (!GAME) return;

  var TEAMS = GAME.teams;
  var TECH_SIDE = TEAMS.away.tech ? 'away' : 'home';
  var OTHER_SIDE = TECH_SIDE === 'away' ? 'home' : 'away';

  var SHOT_NAMES = { '3PTR': '3-pointer', JUMPER: 'jumper', LAYUP: 'layup', DUNK: 'dunk', TIPIN: 'tip-in' };
  var STAT_NAMES = { AST: 'Assist', STL: 'Steal', BLK: 'Block', TO: 'Turnover' };

  /* ------------------------------------------------------------ helpers */
  function svgEl(name, attrs, parent) {
    var node = document.createElementNS(NS, name);
    Object.keys(attrs || {}).forEach(function (k) { node.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(node);
    return node;
  }
  function svgText(parent, x, y, str, cls, anchor) {
    var t = svgEl('text', { x: x, y: y, class: cls || '' }, parent);
    if (anchor) t.setAttribute('text-anchor', anchor);
    t.textContent = str;
    return t;
  }
  function el(tag, cls, str, parent) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (str != null) node.textContent = str;
    if (parent) parent.appendChild(node);
    return node;
  }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  function ordinal(n) { var s = ['th', 'st', 'nd', 'rd'], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); }
  function signed(n) { return n > 0 ? '+' + n : String(n); }

  /* --------------------------------------------------------- game clock */
  /* The period a moment falls in; atEnd puts a period's final second in it rather than the next */
  function periodAt(t, atEnd) {
    var ps = GAME.periods;
    for (var i = ps.length - 1; i >= 0; i--) {
      if (atEnd ? t > ps[i].start : t >= ps[i].start) return ps[i];
    }
    return ps[0];
  }
  function mmss(secs) {
    secs = Math.max(0, Math.round(secs));
    return Math.floor(secs / 60) + ':' + ('0' + secs % 60).slice(-2);
  }
  function clockLeft(t, atEnd) {
    var p = periodAt(t, atEnd);
    return mmss(p.start + p.length - t);
  }
  function clockText(t, atEnd) { return periodAt(t, atEnd).label + ' ' + clockLeft(t, atEnd); }

  /* -------------------------------------------------------------- score */
  /* Score entries are [seconds, away, home, scoring side, play text], in game order */
  function scoreAt(t) {
    var s = GAME.scores, i = 0;
    while (i + 1 < s.length && s[i + 1][0] <= t) i++;
    return s[i];
  }
  function scoreText(entry) {
    return TEAMS.away.abbr + ' ' + entry[1] + ', ' + TEAMS.home.abbr + ' ' + entry[2];
  }
  function techMargin(entry) { return TECH_SIDE === 'away' ? entry[1] - entry[2] : entry[2] - entry[1]; }
  function sideScore(entry, side) { return side === 'away' ? entry[1] : entry[2]; }
  function onCourt(player, t) {
    return player.stints.some(function (s) { return s[0] <= t && (t < s[1] || (t === GAME.length && s[1] === t)); });
  }

  /* ------------------------------------------------------------ tooltip */
  function showTip(evt, title, rows) {
    clear(tip);
    el('div', 'tip-title', title, tip);
    (rows || []).forEach(function (r) { el('div', 'tip-row', r, tip); });
    tip.style.display = 'block';
    var x = evt.clientX + 14, y = evt.clientY + 14;
    tip.style.left = Math.max(6, Math.min(x, window.innerWidth - tip.offsetWidth - 10)) + 'px';
    tip.style.top = Math.min(y, window.innerHeight - tip.offsetHeight - 10) + 'px';
  }
  function hideTip() { tip.style.display = 'none'; }
  function hoverable(node, title, rows) {
    node.addEventListener('pointerenter', function (e) { showTip(e, title, rows); });
    node.addEventListener('pointermove', function (e) { showTip(e, title, rows); });
    node.addEventListener('pointerleave', hideTip);
  }

  /* ------------------------------------------------------------- cursor */
  /* Every chart and the scoreboard follow one shared moment in the game (null = the final) */
  var cursorListeners = [];
  function setCursor(t) { cursorListeners.forEach(function (fn) { fn(t); }); }
  /* Dragging across a chart's lead strip (y0..y1) moves the cursor; hovering a play jumps it there */
  function scrubbable(svg, x0, x1, y0, y1) {
    function move(e) {
      var pt = svg.createSVGPoint();
      pt.x = e.clientX; pt.y = e.clientY;
      var p = pt.matrixTransform(svg.getScreenCTM().inverse());
      if (p.y >= y0 && p.y <= y1) {
        setCursor(p.x < x0 || p.x > x1 ? null : Math.round((p.x - x0) / (x1 - x0) * GAME.length));
      } else if (!(e.target.closest && e.target.closest('.marker'))) {
        // Off the strip and off any play: nothing to show
        setCursor(null);
      }
    }
    svg.addEventListener('pointermove', move);
    svg.addEventListener('pointerdown', move);
    // A tap leaves the cursor where it landed; a mouse leaving the chart goes back to the final
    svg.addEventListener('pointerleave', function (e) { if (e.pointerType === 'mouse') setCursor(null); });
  }
  /* A vertical cursor line over a chart, spanning y0..y1 */
  function cursorLine(svg, xOf, y0, y1) {
    var line = svgEl('line', { class: 'cursor-line', y1: y0, y2: y1, visibility: 'hidden' }, svg);
    cursorListeners.push(function (t) {
      if (t == null) { line.setAttribute('visibility', 'hidden'); return; }
      line.setAttribute('x1', xOf(t)); line.setAttribute('x2', xOf(t));
      line.setAttribute('visibility', 'visible');
    });
  }

  /* ------------------------------------------------------------ pickers */
  function fillPickers() {
    var ysel = document.getElementById('hl-year');
    var gsel = document.getElementById('hl-game');
    var years = MANIFEST.years.length ? MANIFEST.years : [GAME.season];
    function option(sel, value, label, selected) {
      var o = el('option', null, label, sel);
      o.value = value;
      if (selected) o.selected = true;
    }
    function gamesFor(y) {
      var list = MANIFEST.games[y] || [];
      return list.length || y !== GAME.season ? list : [{ href: GAME.href, label: GAME.label }];
    }
    function fillGames(y) {
      clear(gsel);
      gamesFor(y).forEach(function (g) { option(gsel, g.href, g.label, g.href === CURRENT); });
    }
    years.forEach(function (y) { option(ysel, y, y, y === GAME.season); });
    fillGames(GAME.season);
    // Picking a season jumps to its latest game; picking a game opens its page
    ysel.addEventListener('change', function () {
      var list = gamesFor(ysel.value);
      if (list.length) window.location.href = ROOT + list[0].href;
    });
    gsel.addEventListener('change', function () { window.location.href = ROOT + gsel.value; });
  }

  /* --------------------------------------------------------- scoreboard */
  function teamLogo(team, cls) {
    if (!team.logo) return null;
    var img = el('img', cls);
    img.src = ROOT + team.logo;
    img.alt = '';
    return img;
  }
  function drawBoard() {
    var board = document.getElementById('hl-board');
    clear(board);
    var row = el('div', 'board-row', null, board);
    var refs = {};
    var ot = GAME.periods.length - GAME.periods.filter(function (p) { return !/OT/.test(p.label); }).length;
    var finalText = 'Final' + (ot ? '/' + (ot > 1 ? ot : '') + 'OT' : '');
    // The venue splits at its first comma, so the final reads date / arena / city
    var venue = GAME.venue || '', cut = venue.indexOf(', ');
    var finalDetail = [GAME.dateLabel].concat(cut < 0 ? [venue] : [venue.slice(0, cut), venue.slice(cut + 2)]);

    function teamBlock(side) {
      var team = TEAMS[side];
      var box = el('div', 'board-team ' + side, null, row);
      var logo = teamLogo(team, 'board-logo');
      if (logo) box.appendChild(logo);
      var names = el('div', 'board-name', null, box);
      el('div', 'name', team.name, names);
      el('div', 'sub', team.record, names);
      refs[side] = { score: el('div', 'board-score', String(team.score), box) };
    }
    teamBlock('away');
    var mid = el('div', 'board-mid', null, row);
    var status = el('div', 'status', finalText, mid);
    var detail = el('div', 'detail', null, mid);
    // Always the same three lines high, so the scoreboard doesn't jump while scrubbing
    function setDetail(lines) {
      clear(detail);
      lines.forEach(function (line) { if (line) el('div', null, line, detail).title = line; });
    }
    setDetail(finalDetail);
    teamBlock('home');

    // The trailing team's score is muted, at the final and while scrubbing
    function show(entry) {
      ['away', 'home'].forEach(function (side) {
        var mine = sideScore(entry, side), theirs = sideScore(entry, side === 'away' ? 'home' : 'away');
        refs[side].score.textContent = mine;
        refs[side].score.classList.toggle('trailing', mine < theirs);
      });
    }
    var finalEntry = [GAME.length, TEAMS.away.score, TEAMS.home.score];
    show(finalEntry);
    cursorListeners.push(function (t) {
      if (t == null) {
        status.textContent = finalText;
        setDetail(finalDetail);
        show(finalEntry);
        return;
      }
      var entry = scoreAt(t);
      status.textContent = t >= GAME.length ? finalText : clockText(t);
      setDetail(entry[4] ? ['Last score:', entry[4], clockText(entry[0], true)] : ['Tip-off']);
      show(entry);
    });
  }

  /* Lead changes, ties and each team's biggest lead, under the scoreboard */
  function drawFlowStats() {
    var host = document.getElementById('hl-flowstats');
    clear(host);
    var changes = 0, ties = 0, lastSign = 0;
    var best = {}; best[TECH_SIDE] = { lead: 0, t: 0 }; best[OTHER_SIDE] = { lead: 0, t: 0 };
    GAME.scores.forEach(function (s, i) {
      if (!i) return;
      var m = techMargin(s), sign = m > 0 ? 1 : m < 0 ? -1 : 0;
      if (sign === 0) ties++;
      else { if (lastSign && sign !== lastSign) changes++; lastSign = sign; }
      if (m > best[TECH_SIDE].lead) best[TECH_SIDE] = { lead: m, t: s[0] };
      if (-m > best[OTHER_SIDE].lead) best[OTHER_SIDE] = { lead: -m, t: s[0] };
    });

    function stat(labelText, value, note) {
      var box = el('div', 'stat', null, host);
      el('div', 'label', labelText, box);
      var v = el('div', 'value', value, box);
      if (note) { v.appendChild(document.createTextNode(' ')); el('small', null, note, v); }
    }
    stat('Lead changes', String(changes));
    stat('Times tied', String(ties));
    [TECH_SIDE, OTHER_SIDE].forEach(function (side) {
      var b = best[side];
      stat(TEAMS[side].abbr + ' largest lead', b.lead ? '+' + b.lead : '—', b.lead ? clockText(b.t, true) : null);
    });
  }

  /* ------------------------------------------------------ lineup charts */
  function eventTitle(e) {
    switch (e[1]) {
      case 'FG3': case 'FG2': return (e[2] ? 'Made ' : 'Missed ') + (SHOT_NAMES[e[3]] || e[3].toLowerCase());
      case 'FT': return e[3] === 1 ? (e[2] ? 'Made free throw' : 'Missed free throw')
                                   : 'Free throws: ' + e[2] + ' of ' + e[3];
      case 'REB': return (e[2] === 'OFF' ? 'Offensive' : e[2] === 'DEF' ? 'Defensive' : 'Dead-ball') + ' rebound';
      case 'PF': return ordinal(e[2]) + ' foul';
      default: return STAT_NAMES[e[1]] || e[1];
    }
  }

  /* Drawing priority on a stripe, least important first; anything not listed (assists) isn't drawn */
  var DRAW_ORDER = ['REB', 'STL', 'BLK', 'TO', 'FT', 'MISS', 'MADE', 'PF'];
  /* Free-throw pills' half width, and how far apart (in seconds) an and-one's basket, foul and free throw can be logged.
     A made lone free throw can't be a one-and-one's front end, so it's allowed to trail its basket by more. */
  var FT_HALF = 6.5, AND_ONE_SECS = 2, AND_ONE_MADE_SECS = 6;
  function drawRank(e) {
    var kind = e[1] === 'FG3' || e[1] === 'FG2' ? (e[2] ? 'MADE' : 'MISS') : e[1];
    return DRAW_ORDER.indexOf(kind);
  }

  function drawLineup(side, hostId, headId) {
    var team = TEAMS[side];
    var opp = TEAMS[side === 'away' ? 'home' : 'away'];
    var head = document.getElementById(headId);
    var host = document.getElementById(hostId);
    clear(head); clear(host);
    var logo = teamLogo(team, '');
    if (logo) head.appendChild(logo);
    el('h2', null, team.name, head);
    el('span', 'note', 'Drag across the lead chart to replay the score · hover a play for details', head);

    var starters = team.players.filter(function (p) { return p.starter; });
    var bench = team.players.filter(function (p) { return !p.starter; });
    // Lead strip on top, then a name line over a full-width stripe for each player, all on one time axis
    var W = 1000, HEAD = 24, STRIP = 110, LABEL = 26, ROW = 48, X0 = 8, X1 = 992;
    var S0 = HEAD + 6, S1 = S0 + STRIP;
    var H = S1 + 8 + LABEL * (bench.length ? 2 : 1) + ROW * team.players.length + 4;
    function xOf(t) { return X0 + t / GAME.length * (X1 - X0); }

    var svg = svgEl('svg', { viewBox: '0 0 ' + W + ' ' + H, class: 'lineup', role: 'img',
      'aria-label': team.name + ' lead over the game, and when each player was on the floor and what he did' }, host);

    // Period names along the top
    GAME.periods.forEach(function (p) { svgText(svg, xOf(p.start + p.length / 2), 16, p.label, 'col-head', 'middle'); });
    // Names and labels that stay at the left edge while the chart scrolls sideways on a phone
    var pinned = svgEl('g', { class: 'pinned' });

    /* --- lead strip: this team's lead, shaded in whichever team is ahead --- */
    var margins = GAME.scores.map(function (e) { return sideScore(e, side) - sideScore(e, side === 'away' ? 'home' : 'away'); });
    var maxAbs = Math.max(5, Math.max.apply(null, margins.map(Math.abs)));
    var step = maxAbs > 40 ? 20 : maxAbs > 20 ? 10 : 5;
    var top = Math.ceil(maxAbs / step) * step;
    function yOf(m) { return S0 + (top - m) / (2 * top) * STRIP; }

    for (var m = -top; m <= top; m += step) {
      svgEl('line', { class: m === 0 ? 'baseline' : 'gridline', x1: X0, x2: X1, y1: yOf(m), y2: yOf(m) }, svg);
    }
    var d = 'M' + xOf(0) + ' ' + yOf(0);
    GAME.scores.forEach(function (e, i) { if (i) d += ' H' + xOf(e[0]) + ' V' + yOf(margins[i]); });
    d += ' H' + xOf(GAME.length);
    var area = d + ' V' + yOf(0) + ' H' + xOf(0) + ' Z';
    var defs = svgEl('defs', {}, svg);
    var up = svgEl('clipPath', { id: 'hl-up-' + side }, defs);
    svgEl('rect', { x: X0, y: S0, width: X1 - X0, height: yOf(0) - S0 }, up);
    var down = svgEl('clipPath', { id: 'hl-down-' + side }, defs);
    svgEl('rect', { x: X0, y: yOf(0), width: X1 - X0, height: S1 - yOf(0) }, down);
    svgEl('path', { d: area, fill: team.color, 'fill-opacity': 0.8, 'clip-path': 'url(#hl-up-' + side + ')' }, svg);
    svgEl('path', { d: area, fill: opp.color, 'fill-opacity': 0.8, 'clip-path': 'url(#hl-down-' + side + ')' }, svg);
    svgEl('path', { d: d, class: 'flow-line' }, svg);
    // Which team each half of the strip belongs to, at its outer gridline
    svgText(pinned, X0 + 4, yOf(top) + 13, team.abbr + ' +' + top, 'lead-label').setAttribute('fill', team.color);
    svgText(pinned, X0 + 4, yOf(-top) - 5, opp.abbr + ' +' + top, 'lead-label').setAttribute('fill', opp.color);

    /* --- player rows --- */
    var y = S1 + 8;
    function section(name, players) {
      svgText(pinned, X0, y + 18, name, 'section-label').setAttribute('fill', team.color);
      y += LABEL;
      players.forEach(playerRow);
    }
    function tspan(parent, str, cls) {
      var t = svgEl('tspan', { class: cls }, parent);
      t.textContent = str;
      return t;
    }

    // The other team's fouls, for spotting and-ones
    var oppFouls = [];
    opp.players.forEach(function (op) {
      op.events.forEach(function (e) { if (e[1] === 'PF') oppFouls.push(e[0]); });
    });

    function playerRow(p) {
      var barY = y + 18, barH = 24, midY = barY + barH / 2;

      // Number, name and points on the line above the stripe
      var label = svgEl('text', { x: X0, y: y + 13 }, pinned);
      tspan(label, p.num + '  ', 'p-num');
      tspan(label, p.name, 'p-name');
      tspan(label, '   ' + p.pts + ' pts', 'p-stat');

      // Bench time in gray, floor time in the team color
      svgEl('rect', { class: 'track', x: X0, y: barY, width: X1 - X0, height: barH }, svg);
      p.stints.forEach(function (s) {
        svgEl('rect', { x: xOf(s[0]), y: barY, width: Math.max(0.5, xOf(s[1]) - xOf(s[0])),
                        height: barH, fill: team.color }, svg);
      });

      // Each play's tooltip, and the cursor jumps to it so the lead strip and scoreboard follow
      function hoverPlay(node, e, extra) {
        hoverable(node, eventTitle(e), [p.name, clockText(e[0], true) + ' · ' + scoreText(scoreAt(e[0]))].concat(extra || []));
        node.addEventListener('pointerenter', function () { setCursor(e[0]); });
      }

      // And-ones: a lone free throw right after his own made basket, with the other team whistled for a foul
      var andOnes = [], andOneFts = [];
      p.events.forEach(function (ft) {
        if (ft[1] !== 'FT' || ft[3] !== 1) return;
        var window = ft[2] ? AND_ONE_MADE_SECS : AND_ONE_SECS, basket = null;
        p.events.forEach(function (e) {
          var gap = ft[0] - e[0];
          if ((e[1] === 'FG3' || e[1] === 'FG2') && e[2] && gap >= -AND_ONE_SECS && gap <= window
              && (!basket || Math.abs(gap) < Math.abs(ft[0] - basket[0]))) basket = e;
        });
        var fouled = basket && oppFouls.some(function (t) {
          return t >= Math.min(basket[0], ft[0]) - AND_ONE_SECS && t <= ft[0] + AND_ONE_SECS;
        });
        if (basket && fouled && andOnes.indexOf(basket) < 0) { andOnes.push(basket); andOneFts.push(ft); }
      });

      // Space each shot disc and free-throw pill takes up on the stripe: [center x, half width]
      var taken = p.events.filter(function (e) { return e[1] === 'FG3' || e[1] === 'FG2'; })
        .map(function (e) { return [xOf(e[0]), andOnes.indexOf(e) < 0 ? 7.5 : 10]; });
      // A free throw drawn into a shot or another free throw steps past it, right first, then left
      function freeSpot(x) {
        function hits(fx) { return taken.filter(function (o) { return Math.abs(o[0] - fx) < o[1] + FT_HALF + 1; }); }
        for (var dir = 1; dir >= -1; dir -= 2) {
          var fx = x;
          for (var i = 0; i < 6 && hits(fx).length; i++) {
            var edges = hits(fx).map(function (o) { return o[0] + dir * (o[1] + FT_HALF + 1); });
            fx = dir > 0 ? Math.max.apply(null, edges) : Math.min.apply(null, edges);
          }
          if (!hits(fx).length && fx > X0 + FT_HALF && fx < X1 - FT_HALF) { taken.push([fx, FT_HALF]); return fx; }
        }
        taken.push([x, FT_HALF]);
        return x;
      }
      // Free throws get their spots in time order, then the spots are handed out left to right, so they stay chronological
      var fts = p.events.filter(function (e) { return e[1] === 'FT' && andOneFts.indexOf(e) < 0; });
      var spots = fts.map(function (e) { return freeSpot(xOf(e[0])); }).sort(function (a, b) { return a - b; });

      // Plays drawn least important first, so the ones that matter most land on top
      p.events
        .filter(function (e) { return drawRank(e) >= 0 && andOneFts.indexOf(e) < 0; })
        .sort(function (a, b) { return drawRank(a) - drawRank(b) || a[0] - b[0]; })
        .forEach(function (e) {
          var t = e[0], x = xOf(t), extra = null;
          var g = svgEl('g', { class: 'marker' }, svg);
          if (e[1] === 'FG3' || e[1] === 'FG2') {
            // A missed shot is filled with the stripe's own color, so nothing behind it shows through
            var off = onCourt(p, t) || onCourt(p, t - 1) ? '' : ' off';
            var disc = svgEl('circle', { class: 'shot ' + (e[2] ? 'made' : 'miss') + off, cx: x, cy: midY,
                                         r: e[2] ? 7.5 : 7 }, g);
            if (!e[2] && !off) disc.setAttribute('fill', team.color);
            var num = svgText(g, x, midY, e[1] === 'FG3' ? '3' : '2', 'shot-num ' + (e[2] ? 'made' : 'miss') + off);
            if (e[2]) num.setAttribute('fill', team.color);
            // An and-one's free throw rides on the basket as +1 (made) or +0 (missed)
            var ai = andOnes.indexOf(e);
            if (ai >= 0) {
              var made = andOneFts[ai][2];
              svgText(g, x + 5, barY + 3, '+' + made, 'andone').setAttribute('stroke', team.color);
              extra = ['And-one: free throw ' + (made ? 'made' : 'missed')];
            }
          } else if (e[1] === 'FT') {
            // A narrow pill with made over taken, like a fraction
            var fx = spots[fts.indexOf(e)];
            svgEl('rect', { class: 'ft', x: fx - FT_HALF, y: midY - 11, width: FT_HALF * 2, height: 22, rx: FT_HALF }, g);
            svgText(g, fx, midY - 5, String(e[2]), 'ft-num');
            svgEl('line', { class: 'ft-bar', x1: fx - 3.5, x2: fx + 3.5, y1: midY, y2: midY }, g);
            svgText(g, fx, midY + 5.5, String(e[3]), 'ft-num');
          } else {
            svgEl('rect', { class: 'hit', x: x - 4, y: barY, width: e[1] === 'PF' ? 16 : 8, height: barH }, g);
            svgEl('rect', { class: 'statline stat-' + e[1], x: x - 1.5, y: barY + 1, width: 3, height: barH - 2 }, g);
            // Fouls carry their number beside the line, so a player's second foul is easy to spot
            if (e[1] === 'PF') svgText(g, x + 3, barY + 8, String(e[2]), 'foul-num');
          }
          hoverPlay(g, e, extra);
        });

      svgEl('line', { class: 'rowline', x1: X0, x2: X1, y1: y + ROW - 0.5, y2: y + ROW - 0.5 }, svg);
      y += ROW;
    }

    section('STARTERS', starters);
    if (bench.length) section('BENCH', bench);

    // Period breaks in solid black, so they never read as a substitution
    GAME.periods.forEach(function (p, i) {
      if (i) svgEl('line', { class: 'break', x1: xOf(p.start), x2: xOf(p.start), y1: HEAD, y2: H }, svg);
    });

    // The cursor: a line down the whole chart, with a dot and the lead on the strip
    cursorLine(svg, xOf, HEAD, H);
    var dot = svgEl('circle', { class: 'cursor-dot', r: 4.5, visibility: 'hidden' }, svg);
    var leadText = svgText(svg, 0, 0, '', 'cursor-label');
    cursorListeners.push(function (t) {
      if (t == null) { dot.setAttribute('visibility', 'hidden'); leadText.textContent = ''; return; }
      var entry = scoreAt(t);
      var lead = sideScore(entry, side) - sideScore(entry, side === 'away' ? 'home' : 'away');
      var x = xOf(t), ly = yOf(lead);
      dot.setAttribute('cx', x); dot.setAttribute('cy', ly);
      dot.setAttribute('visibility', 'visible');
      leadText.textContent = lead === 0 ? 'Tied' : (lead > 0 ? team.abbr : opp.abbr) + ' +' + Math.abs(lead);
      // Keep the label inside the strip, flipping to the left near the right edge
      var flip = x > X1 - 90;
      leadText.setAttribute('x', flip ? x - 8 : x + 8);
      leadText.setAttribute('text-anchor', flip ? 'end' : 'start');
      leadText.setAttribute('y', Math.max(S0 + 12, Math.min(S1 - 6, ly - 8)));
    });
    scrubbable(svg, X0, X1, S0, S1);

    // Pinned labels go on top of everything, and slide right by however far the chart has scrolled
    svg.appendChild(pinned);
    var frame = null;
    host.addEventListener('scroll', function () {
      if (frame) return;
      frame = window.requestAnimationFrame(function () {
        frame = null;
        var scale = W / svg.getBoundingClientRect().width;
        pinned.setAttribute('transform', 'translate(' + (host.scrollLeft * scale).toFixed(1) + ' 0)');
      });
    }, { passive: true });
  }

  /* --------------------------------------------------------- plus/minus */
  /* One table per team, best to worst, with a bar on a shared scale so the two teams compare */
  function drawPlusMinus() {
    var host = document.getElementById('hl-pm');
    clear(host);
    var all = TEAMS.away.players.concat(TEAMS.home.players);
    var maxAbs = Math.max(1, Math.max.apply(null, all.map(function (p) { return Math.abs(p.pm); })));

    [TECH_SIDE, OTHER_SIDE].forEach(function (side) {
      var team = TEAMS[side];
      var box = el('div', 'pmteam', null, host);
      var head = el('div', 'pmhead', null, box);
      var logo = teamLogo(team, '');
      if (logo) head.appendChild(logo);
      el('h3', null, team.name, head);

      var table = el('table', 'pm', null, box);
      var hr = el('tr', null, null, el('thead', null, null, table));
      el('th', null, 'Player', hr);
      el('th', 'num', 'MIN', hr);
      el('th', 'num', '+/-', hr);
      var barHead = el('th', 'bar', null, hr);
      barHead.setAttribute('aria-hidden', 'true');

      var tbody = el('tbody', null, null, table);
      team.players.slice()
        .sort(function (a, b) { return b.pm - a.pm || b.secs - a.secs; })
        .forEach(function (p) {
          var tr = el('tr', null, null, tbody);
          var name = el('td', 'player', null, tr);
          el('span', 'pnum', p.num, name);
          name.appendChild(document.createTextNode(p.name));
          el('td', 'num', mmss(p.secs), tr);
          el('td', 'num pmval' + (p.pm > 0 ? ' plus' : p.pm < 0 ? ' minus' : ''), signed(p.pm), tr);
          // Diverging bar: gains run right of center, losses left
          var cell = el('td', 'bar', null, tr);
          cell.setAttribute('aria-hidden', 'true');
          var track = el('div', 'pmtrack', null, cell);
          if (p.pm) {
            var fill = el('div', 'pmfill ' + (p.pm > 0 ? 'plus' : 'minus'), null, track);
            fill.style.width = (Math.abs(p.pm) / maxAbs * 50).toFixed(1) + '%';
          }
        });
    });
  }

  /* --------------------------------------------------------------- draw */
  fillPickers();
  drawBoard();
  drawFlowStats();
  drawLineup(TECH_SIDE, 'hl-tech', 'hl-tech-head');
  drawLineup(OTHER_SIDE, 'hl-other', 'hl-other-head');
  drawPlusMinus();
})();
