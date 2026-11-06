(function () {
  var DATA = window.GTPDD_SUNBELT_RUNS || { years: [], runs: {} };
  var HIGHLIGHT = document.body.getAttribute('data-highlight') || '';
  /* '?preview' shows just the top of the page, sized for the link-preview screenshot */
  if (/[?&]preview\b/.test(window.location.search)) document.documentElement.classList.add('preview');
  /* Logo paths in the run data are relative to the page's asset folder */
  var ASSETS = document.body.getAttribute('data-assets') || '';
  var SVGNS = 'http://www.w3.org/2000/svg';
  var MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  var DIVISION_ORDER = ['West', 'East'];       // West reads first, left or on top

  var yearSel = document.getElementById('sb-year');
  var runSel = document.getElementById('sb-run');
  var tip = document.getElementById('sb-tooltip');

  var state = { year: null, index: 0 };

  /* ------------------------------------------------------------- helpers */
  function svgEl(name, attrs) {
    var e = document.createElementNS(SVGNS, name);
    for (var k in attrs) if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    return e;
  }
  function svgText(x, y, str, cls, anchor) {
    var t = svgEl('text', { x: x, y: y, 'class': cls, 'text-anchor': anchor || 'middle' });
    t.textContent = str;
    return t;
  }
  function el(tag, cls, str) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (str != null) e.textContent = str;
    return e;
  }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

  /* 'YYYY-MM-DD' as a local date -- new Date(string) would read it as UTC and
     roll the day back for anyone west of Greenwich. */
  function parseDay(s) {
    var p = String(s).split('-');
    return new Date(+p[0], +p[1] - 1, +p[2]);
  }
  function shortDay(s) { var d = parseDay(s); return MONTHS[d.getMonth()] + ' ' + d.getDate(); }
  /* Odds that round to 0% or 100% but aren't certain say so, rather than claim a lock. */
  function pct(x, digits) {
    digits = digits == null ? 1 : digits;
    var s = (x * 100).toFixed(digits);
    if (x > 0 && +s === 0) return '<' + (1 / Math.pow(10, digits)).toFixed(digits) + '%';
    if (x < 1 && +s === 100) return '>' + (100 - 1 / Math.pow(10, digits)).toFixed(digits) + '%';
    return s + '%';
  }

  function runsFor(year) { return (DATA.runs || {})[year] || []; }
  function current() { return runsFor(state.year)[state.index] || null; }
  function teamMap(run) {
    var m = {};
    (run ? run.teams : []).forEach(function (t) { m[t.id] = t; });
    return m;
  }
  function divisionsOf(run) {
    var rank = function (d) { var i = DIVISION_ORDER.indexOf(d); return i < 0 ? 99 : i; };
    return run.divisions.slice().sort(function (a, b) { return rank(a) - rank(b) || (a < b ? -1 : 1); });
  }
  function sortedDivision(run, div) {
    return run.teams.filter(function (t) { return t.division === div; })
      .sort(function (a, b) { return b.odds - a.odds || b.expectedWins - a.expectedWins; });
  }

  /* Each team wears one of its own colors, picked by the script to keep a division's
     teams apart. Color follows the team, never its rank, so the season's newest run
     sets every team's color and the flow's stacking order for the whole season. */
  function seasonColors(runs, div) {
    var names = {}, colors = {};
    runs.forEach(function (r) {
      r.teams.forEach(function (t) {
        if (t.division !== div) return;
        names[t.id] = t.name;
        colors[t.id] = t.color || colors[t.id] || 'var(--text-muted)';
      });
    });
    var latest = runs[runs.length - 1];
    var order = ((latest.flowOrder || {})[div] || []).filter(function (id) { return id in names; });
    /* Teams the stacking order doesn't know about go to the bottom, by name */
    Object.keys(names).sort(function (a, b) { return names[a] < names[b] ? -1 : 1; })
      .forEach(function (id) { if (order.indexOf(id) < 0) order.push(id); });
    return { order: order, colors: colors, names: names };
  }

  /* ------------------------------------------------------------- tooltip */
  function showTip(evt, title, rows) {
    clear(tip);
    tip.appendChild(el('div', 'tip-title', title));
    (rows || []).forEach(function (r) { tip.appendChild(el('div', 'tip-row', r)); });
    tip.style.display = 'block';
    var box = evt.target.getBoundingClientRect();
    var x = (evt.clientX != null ? evt.clientX : box.left + box.width / 2) + 14;
    var y = (evt.clientY != null ? evt.clientY : box.top) + 14;
    tip.style.left = Math.min(x, window.innerWidth - tip.offsetWidth - 10) + 'px';
    tip.style.top = Math.min(y, window.innerHeight - tip.offsetHeight - 10) + 'px';
  }
  function hideTip() { tip.style.display = 'none'; }

  /* Hover and keyboard focus get the same tooltip, so nothing is mouse-only. */
  function hoverable(node, title, rows, onActivate) {
    node.setAttribute('tabindex', '0');
    node.addEventListener('mouseenter', function (e) { showTip(e, title, rows); });
    node.addEventListener('mousemove', function (e) { showTip(e, title, rows); });
    node.addEventListener('mouseleave', hideTip);
    node.addEventListener('focus', function (e) { showTip(e, title, rows); });
    node.addEventListener('blur', hideTip);
    if (onActivate) {
      node.addEventListener('click', onActivate);
      node.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onActivate(); }
      });
    }
    return node;
  }

  /* A team's logo with its name as alt text, or just its name if there's no logo. */
  function teamMark(t, withName) {
    var span = el('span');
    if (t && t.logo) {
      var img = el('img', 'teamlogo');
      img.src = ASSETS + t.logo;
      img.alt = withName ? '' : t.name;   /* the name follows, so don't read it twice */
      img.title = t.name;
      span.appendChild(img);
    }
    if (withName || !(t && t.logo)) span.appendChild(document.createTextNode(t ? t.name : '?'));
    return span;
  }

  /* ------------------------------------------------ predicted championship */
  function fillMatchup(run) {
    var box = document.getElementById('sb-matchup');
    clear(box);
    var teams = teamMap(run);
    /* The most likely pairing; older runs without one fall back to the two favorites */
    var top = (run.matchups || [])[0];
    var ids = top ? top.teams : run.divisions.map(function (d) { return sortedDivision(run, d)[0].id; });
    /* Same side as the standings below: West on the left */
    var order = divisionsOf(run);
    ids = ids.slice().sort(function (a, b) {
      return order.indexOf(teams[a].division) - order.indexOf(teams[b].division);
    });

    box.appendChild(el('h2', null, 'Current predicted championship:'));
    var pair = el('div', 'pair');
    ids.forEach(function (id, i) {
      var t = teams[id];
      if (i) pair.appendChild(el('div', 'vs', 'vs'));
      var side = el('div', 'side');
      if (t.logoLarge || t.logo) {
        var img = el('img');
        img.src = ASSETS + (t.logoLarge || t.logo);
        img.alt = '';                     /* the name sits right under it */
        side.appendChild(img);
      }
      side.appendChild(el('div', 'name', t.name));
      side.appendChild(el('div', 'odds', pct(t.odds) + ' to win the ' + t.division));
      pair.appendChild(side);
    });
    box.appendChild(pair);
  }

  /* ------------------------------------------------------ division tables */
  function row(cells) {
    var tr = el('tr');
    cells.forEach(function (c) {
      var td = el(c.head ? 'th' : 'td', c.cls || (c.num ? 'num' : null));
      if (c.node) td.appendChild(c.node); else td.textContent = c.text;
      if (c.title) td.title = c.title;
      if (c.head) td.setAttribute('scope', 'row');
      tr.appendChild(td);
    });
    return tr;
  }

  /* Title chance as a bar. A team still alive never reads 0%, since no simulated title
     isn't the same as no way to win one; an eliminated team gets ELIMINATED across the bar. */
  function oddsBar(v, eliminated) {
    var wrap = el('div', 'bar' + (eliminated ? ' elim' : ''));
    var track = el('div', 'track');
    if (eliminated) {
      track.appendChild(el('span', 'elim-label', 'ELIMINATED'));
    } else {
      var fill = el('div', 'fill');
      fill.style.width = (Math.max(0, Math.min(1, v)) * 100).toFixed(1) + '%';
      track.appendChild(fill);
    }
    wrap.appendChild(track);
    wrap.appendChild(el('span', 'val', eliminated ? '' : v === 0 ? '<0.1%' : pct(v)));
    return wrap;
  }

  function swatch(color) {
    var s = el('span', 'swatch');
    s.style.background = color;
    s.setAttribute('aria-hidden', 'true');
    return s;
  }

  function fillStandings(run, runs) {
    var box = document.getElementById('sb-standings');
    clear(box);
    divisionsOf(run).forEach(function (div) {
      var colors = seasonColors(runs, div).colors;
      var sec = el('section');
      var head = el('header');
      head.appendChild(el('h2', null, div + ' Division'));
      sec.appendChild(head);

      var card = el('div', 'card scroller');
      var table = el('table', 'standings');
      var thead = el('thead'), htr = el('tr');
      [['Team'], ['Conf.', 'num'], ['Proj. wins', 'num', 'Projected conference wins'],
       ['Title chance', 'oddsbar']]
        .forEach(function (h) {
          var th = el('th', h[1] || null, h[0]);
          if (h[2]) th.title = h[2];
          htr.appendChild(th);
        });
      thead.appendChild(htr);
      table.appendChild(thead);

      var body = el('tbody');
      sortedDivision(run, div).forEach(function (t) {
        var name = teamMark(t, true);
        name.insertBefore(swatch(colors[t.id]), name.firstChild);
        var tr = row([
          { node: name, cls: 'team', head: true },
          { text: t.record, num: true },
          { text: t.expectedWins.toFixed(1), num: true },
          { node: oddsBar(t.odds, t.eliminated), cls: 'oddsbar' }
        ]);
        tr.className = (t.id === HIGHLIGHT ? 'is-home' : '') + (t.eliminated ? ' is-elim' : '');
        body.appendChild(tr);
      });
      table.appendChild(body);
      card.appendChild(table);
      sec.appendChild(card);
      box.appendChild(sec);
    });
  }

  /* ----------------------------------- each division's odds as a flow over time */
  function drawFlow(svg, runs, idx, div, palette, width) {
    /* Drawn at the card's real width, so text stays its true size whether the
       divisions sit side by side or stack */
    var W = Math.max(460, Math.round(width || 560)), H = 290, padL = 42, padR = 92, padTop = 10, padBottom = 32;
    var plotTop = padTop, plotBottom = H - padBottom, plotH = plotBottom - plotTop;
    var plotW = W - padL - padR;
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);

    /* Each run's odds per team, scaled to fill the column exactly despite rounding */
    var cols = runs.map(function (r, i) {
      var m = teamMap(r), total = 0, v = {};
      palette.order.forEach(function (id) {
        v[id] = m[id] && m[id].division === div ? m[id].odds : 0;
        total += v[id];
      });
      palette.order.forEach(function (id) { v[id] = total ? v[id] / total : 0; });
      return { run: r, i: i, v: v };
    });

    var t0 = parseDay(runs[0].date).getTime();
    var t1 = parseDay(runs[runs.length - 1].date).getTime();
    /* A single run has no time to span, so it draws as one column */
    var single = runs.length === 1, colHalf = 26;
    function xOf(r) {
      return single ? padL + plotW / 2
                    : padL + (parseDay(r.date).getTime() - t0) / (t1 - t0 || 1) * plotW;
    }
    function yOf(frac) { return plotBottom - frac * plotH; }

    /* Band edges at every run: slot 1 on top, stacking down */
    var xs = [], edges = {};
    cols.forEach(function (c) {
      var x = xOf(c.run);
      var px = single ? [x - colHalf, x + colHalf] : [x];
      var above = 0;
      palette.order.forEach(function (id) {
        (edges[id] = edges[id] || []);
        px.forEach(function (xx) {
          edges[id].push({ x: xx, top: 1 - above, bottom: 1 - above - c.v[id] });
        });
        above += c.v[id];
      });
      px.forEach(function (xx) { xs.push(xx); });
    });

    [0, 0.5, 1].forEach(function (v) {
      svg.appendChild(svgText(padL - 8, yOf(v) + 4, pct(v, 0), 'axis-label', 'end'));
    });

    /* One closed band per team: along its top edge, then back along its bottom */
    palette.order.forEach(function (id) {
      var e = edges[id];
      if (!e.some(function (p) { return p.top - p.bottom > 0; })) return;
      var d = e.map(function (p, i) { return (i ? 'L' : 'M') + p.x.toFixed(2) + ' ' + yOf(p.top).toFixed(2); })
        .concat(e.slice().reverse().map(function (p) { return 'L' + p.x.toFixed(2) + ' ' + yOf(p.bottom).toFixed(2); }))
        .join(' ') + 'Z';
      svg.appendChild(svgEl('path', { d: d, fill: palette.colors[id], 'class': 'band' }));
    });

    /* The run on screen, marked across the stack */
    if (!single) {
      var cx = xOf(runs[idx]);
      svg.appendChild(svgEl('line', { x1: cx, x2: cx, y1: plotTop, y2: plotBottom, 'class': 'current' }));
    }

    /* Direct labels off the right edge for every band tall enough to hold one */
    var lastCol = cols[cols.length - 1], lastX = xs[xs.length - 1];
    var teams = teamMap(lastCol.run), above = 0;
    palette.order.forEach(function (id) {
      var v = lastCol.v[id], h = v * plotH;
      if (h >= 15 && teams[id]) {
        var y = yOf(1 - above - v / 2) + 4;
        var label = svgText(lastX + 8, y, teams[id].abbr + ' ', 'band-label', 'start');
        var val = svgEl('tspan', { 'class': 'band-value' });
        val.textContent = pct(v, 0);
        label.appendChild(val);
        svg.appendChild(label);
      }
      above += v;
    });

    /* Date ticks thin out until they stop colliding; the newest run always keeps one. */
    var labelled = [], lastTick = -1e9;
    cols.forEach(function (c, i) {
      var x = xOf(c.run);
      if (i === 0 || x - lastTick >= 64) { labelled.push(i); lastTick = x; }
    });
    var lastI = cols.length - 1;
    while (labelled.length && labelled[labelled.length - 1] !== lastI &&
           xOf(runs[lastI]) - xOf(runs[labelled[labelled.length - 1]]) < 64) {
      labelled.pop();
    }
    if (labelled[labelled.length - 1] !== lastI) labelled.push(lastI);
    labelled.forEach(function (i) {
      var anchor = single ? 'middle' : i === 0 ? 'start' : i === lastI ? 'end' : 'middle';
      svg.appendChild(svgText(xOf(runs[i]), plotBottom + 20, shortDay(runs[i].date), 'axis-label', anchor));
    });

    /* One hover strip per run: the whole division's odds at that point */
    cols.forEach(function (c, i) {
      var x = xOf(c.run);
      var left = single ? x - colHalf : i === 0 ? padL : (xOf(runs[i - 1]) + x) / 2;
      var right = single ? x + colHalf : i === lastI ? padL + plotW : (x + xOf(runs[i + 1])) / 2;
      var rows = sortedDivision(c.run, div).filter(function (t) { return t.odds > 0; })
        .map(function (t) { return t.name + ' ' + pct(t.odds); });
      if (i !== idx) rows.push('Click to load this run');
      var hit = svgEl('rect', { x: left, y: plotTop, width: Math.max(1, right - left),
                                height: plotH, 'class': 'hit' });
      hoverable(hit, c.run.label + ' · ' + c.run.dateLabel, rows, function () { go(i); });
      svg.appendChild(hit);
    });
  }

  function fillFlows(runs, idx) {
    var box = document.getElementById('sb-flows');
    clear(box);
    divisionsOf(runs[idx]).forEach(function (div) {
      var palette = seasonColors(runs, div);
      var sec = el('section');
      var head = el('header');
      head.appendChild(el('h2', null, div + ' Title Odds'));
      sec.appendChild(head);

      var card = el('div', 'card scroller');
      /* The key, in stacking order: top band first */
      var legend = el('div', 'legend');
      palette.order.forEach(function (id) {
        var item = el('span');
        item.appendChild(swatch(palette.colors[id]));
        item.appendChild(document.createTextNode(palette.names[id]));
        legend.appendChild(item);
      });
      card.appendChild(legend);

      var svg = svgEl('svg', { 'class': 'flow', role: 'img',
                               'aria-label': div + ' Division title odds for each team, run by run' });
      card.appendChild(svg);
      sec.appendChild(card);
      box.appendChild(sec);
      /* The card's inner width, less its 8px side padding */
      drawFlow(svg, runs, idx, div, palette, card.clientWidth - 16);
    });
  }

  /* -------------------------------------------------- games still to play */
  /* A logo at a given size, or the team's abbreviation if it has none */
  function logoOrAbbr(t, cls) {
    if (t && t.logo) {
      var img = el('img', cls);
      img.src = ASSETS + t.logo;
      img.alt = t.name;
      img.title = t.name;
      return img;
    }
    return el('span', cls + ' abbr', t ? t.abbr : '?');
  }

  /* A change in title chance as '+6%' / '−2%': whole points, or one decimal under a point */
  function change(d) {
    var size = Math.abs(d * 100);
    var text = size >= 0.95 ? size.toFixed(0) : size.toFixed(1);
    if (+text === 0) return '0%';
    return (d > 0 ? '+' : '−') + text + '%';
  }

  /* One team the game moves: its logo, then 'ABBR wins' for each side (away on top,
     as in the table) with how far that result moves the team's title chance from
     where it stands now. Gains are green and losses red, with the sign saying it too;
     a result the script proved knocks the team out reads ELIM. */
  function swingItem(g, s, teams, sims) {
    var t = teams[s[0]], item = el('div', 'swing-item');
    item.appendChild(logoOrAbbr(t, 'swing-team'));
    var outcomes = el('div', 'outcomes');
    /* s is [team, odds if home wins, odds if away wins, eliminated if home wins, ...if away wins] */
    [[g.away, s[2], s[4]], [g.home, s[1], s[3]]].forEach(function (o) {
      var winner = teams[o[0]], line = el('div', 'outcome');
      var d = t ? o[1] - t.odds : 0;
      var elim = o[2] === 1 && !!t, ifWins = ' if ' + (winner ? winner.name : '?') + ' wins';
      var now = ' (' + (t ? pct(t.odds, 1) : '?') + ' now)';
      line.title = elim ? t.name + ' is mathematically eliminated' + ifWins + now
        : o[1] === 0 ? (t ? t.name : '?') + ' wins none of the ' + sims + ' simulated seasons' + ifWins +
                       ', but is still mathematically alive' + now
        : (t ? t.name : '?') + ': ' + pct(o[1], 1) + ' to win the division' + ifWins + now;
      line.appendChild(el('span', 'winner', (winner ? winner.abbr : '?') + ' wins'));
      var text = elim ? 'ELIM' : change(d);
      line.appendChild(el('span', 'val' + (elim ? ' down elim' : text === '0%' ? '' : d > 0 ? ' up' : ' down'), text));
      outcomes.appendChild(line);
    });
    item.appendChild(outcomes);
    return item;
  }

  /* Just the coming week's games: ESPN's week of the next game, or its first six days */
  function upcomingGames(run) {
    var games = run.games || [];
    if (!games.length) return [];
    var week = games[0].week;
    if (week != null) return games.filter(function (g) { return g.week === week; });
    return games.slice(0, 7);
  }

  function fillGames(run) {
    var body = document.querySelector('#sb-games tbody');
    clear(body);
    var teams = teamMap(run);
    var games = upcomingGames(run);
    document.getElementById('sb-games-title').textContent = games.length && games[0].week != null
      ? 'Week ' + games[0].week + ' Conference Games' : "This Week's Conference Games";
    if (!games.length) {
      var tr = row([{ text: 'The conference regular season is over.' }]);
      tr.firstChild.colSpan = 7;
      body.appendChild(tr);
    }
    games.forEach(function (g) {
      /* Each side's win odds sit under its logo, the favorite's in bold */
      var awayOdds = 1 - g.homeOdds, est = g.source === 'fpi' ? '' : ' (est.)';
      /* Round the home side and give the away side the rest, so the pair reads 100% */
      var homeWhole = Math.round(g.homeOdds * 100);
      var shown = homeWhole > 0 && homeWhole < 100
        ? { home: homeWhole + '%', away: (100 - homeWhole) + '%' }
        : { home: pct(g.homeOdds, 0), away: pct(awayOdds, 0) };
      function side(id, odds, text) {
        var box = el('div');
        box.appendChild(teamMark(teams[id]));
        box.appendChild(el('div', odds > 0.5 ? 'odds fav' : 'odds', text + est));
        return box;
      }
      /* The two teams playing come first (away, then home), then the other schools the
         game moves most; a team with no title chance either way is left off */
      var playing = [g.away, g.home].map(function (id) {
        return g.swing.filter(function (s) { return s[0] === id; })[0];
      }).filter(Boolean);
      var others = g.swing.filter(function (s) { return s[0] !== g.away && s[0] !== g.home; });
      var swings = playing.concat(others).slice(0, 3);
      /* One fixed-width column per team, so they line up down the table */
      var cells = [
        { text: g.date, head: true },
        { node: side(g.away, awayOdds, shown.away), cls: 'mark' },
        { text: '@', cls: 'at' },
        { node: side(g.home, g.homeOdds, shown.home), cls: 'mark' }
      ];
      for (var k = 0; k < 3; k++) {
        var s = swings[k];
        cells.push(s ? { node: swingItem(g, s, teams, run.sims.toLocaleString()), cls: 'swing' }
                     : { text: k || swings.length ? '' : 'Barely moves any race', cls: 'swing' });
      }
      body.appendChild(row(cells));
    });
    var estimated = games.some(function (g) { return g.source === 'even'; });
    document.getElementById('sb-games-note').textContent =
      estimated ? 'ESPN had no FPI projection for at least one game; those are held at 50%.' : '';
  }

  /* ---------------------------------------------------------------- render */
  function fillRunSelect(runs) {
    clear(runSel);
    runs.forEach(function (r, i) {
      var o = el('option', null, r.label + ' · ' + shortDay(r.date));
      o.value = i;
      runSel.appendChild(o);
    });
    runSel.value = state.index;
  }

  function render() {
    var runs = runsFor(state.year);
    if (!runs.length) return;
    state.index = Math.max(0, Math.min(state.index, runs.length - 1));
    var run = current();

    fillRunSelect(runs);
    yearSel.value = state.year;

    fillMatchup(run);
    fillStandings(run, runs);
    fillFlows(runs, state.index);
    fillGames(run);
    hideTip();
  }

  function go(i, keepHash) {
    state.index = i;
    if (!keepHash) {
      var r = runsFor(state.year)[i];
      if (r) history.replaceState(null, '', '#' + state.year + '-' + r.date);
    }
    render();
  }

  /* A hash of '#<year>-<run date>' makes one week of the season linkable. */
  function fromHash() {
    var m = /^#(\d{4})-(\d{4}-\d{2}-\d{2})$/.exec(window.location.hash || '');
    if (!m) return false;
    var runs = runsFor(m[1]);
    for (var i = 0; i < runs.length; i++) {
      if (runs[i].date === m[2]) { state.year = m[1]; state.index = i; return true; }
    }
    return false;
  }

  /* ------------------------------------------------------------------ init */
  var years = (DATA.years || []).map(String);
  if (!years.length) return;
  years.forEach(function (y) {
    var o = el('option', null, y);
    o.value = y;
    yearSel.appendChild(o);
  });

  state.year = years[0];                       // years arrive newest first
  state.index = Math.max(0, runsFor(state.year).length - 1);
  fromHash();

  yearSel.addEventListener('change', function () {
    state.year = yearSel.value;
    go(Math.max(0, runsFor(state.year).length - 1));
  });
  runSel.addEventListener('change', function () { go(+runSel.value); });
  window.addEventListener('hashchange', function () { if (fromHash()) render(); });
  /* The flows are drawn to fit, so redraw them once a resize settles */
  var resizeTimer = null;
  window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () { fillFlows(runsFor(state.year), state.index); }, 150);
  });
  document.addEventListener('keydown', function (e) {
    if (e.target && /^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) return;
    if (e.key === 'ArrowLeft' && state.index > 0) go(state.index - 1);
    if (e.key === 'ArrowRight' && state.index < runsFor(state.year).length - 1) go(state.index + 1);
  });

  render();
})();
