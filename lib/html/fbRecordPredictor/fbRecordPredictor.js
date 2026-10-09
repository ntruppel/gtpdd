
(function () {
  var DATA = window.GTPDD_RECORD_RUNS || { years: [], runs: {}, bowlWins: 6 };
  var BOWL_WINS = DATA.bowlWins || 6;
  var SVGNS = 'http://www.w3.org/2000/svg';
  var MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  var yearSel = document.getElementById('rp-year');
  var runSel = document.getElementById('rp-run');
  var prevBtn = document.getElementById('rp-prev');
  var nextBtn = document.getElementById('rp-next');
  var tip = document.getElementById('rp-tooltip');

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
  function pct(x, digits) { return (x * 100).toFixed(digits == null ? 1 : digits) + '%'; }
  function signed(x, digits, unit) {
    var s = (x > 0 ? '+' : x < 0 ? '−' : '');
    return s + Math.abs(x).toFixed(digits) + (unit || '');
  }
  function recordLabel(k, n) { return k + '-' + (n - k); }

  function runsFor(year) { return (DATA.runs || {})[year] || []; }
  function current() { return runsFor(state.year)[state.index] || null; }
  function previousRun() { return state.index > 0 ? runsFor(state.year)[state.index - 1] : null; }

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

  /* --------------------------------------------------- the odds distribution */
  function drawOdds(run) {
    var svg = document.getElementById('rp-odds');
    clear(svg);
    var odds = run.odds, n = odds.length - 1;
    var W = 960, H = 380, padL = 16, padR = 16, padTop = 40, padBottom = 46;
    var plotTop = padTop, plotBottom = H - padBottom, plotH = plotBottom - plotTop;
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);

    var band = (W - padL - padR) / odds.length;
    var barW = Math.min(38, band * 0.72);
    var top = Math.max.apply(null, odds) * 1.14 || 1;

    /* Bowl eligibility is a real line on this axis, so it gets a hairline and a
       caption rather than a second color doing the same job. */
    /* The two colors are the two sides of bowl eligibility, so the divider is
       captioned on both sides -- the split is named, never color alone. */
    if (n >= BOWL_WINS) {
      var bx = padL + band * BOWL_WINS, by = plotTop - 22;
      svg.appendChild(svgEl('line', { x1: bx, x2: bx, y1: plotTop - 14, y2: plotBottom,
                                      'class': 'baseline' }));
      svg.appendChild(svgEl('path', {
        d: 'M' + (bx - 5) + ' ' + (by - 4) + 'l-6 4l6 4Z', fill: 'var(--text-muted)' }));
      svg.appendChild(svgText(bx - 16, by + 4, 'no bowl', 'note-label', 'end'));
      svg.appendChild(svgEl('path', {
        d: 'M' + (bx + 5) + ' ' + (by - 4) + 'l6 4l-6 4Z', fill: 'var(--text-muted)' }));
      svg.appendChild(svgText(bx + 16, by + 4,
                              'bowl eligible',
                              'note-label', 'start'));
    }
    svg.appendChild(svgEl('line', { x1: padL, x2: W - padR, y1: plotBottom, y2: plotBottom,
                                    'class': 'baseline' }));

    odds.forEach(function (v, k) {
      var cx = padL + band * (k + 0.5);
      var h = Math.max(0, (v / top) * plotH);
      var y = plotBottom - h;
      var r = Math.min(4, barW / 2, h);
      /* Rounded at the data end, square on the baseline. */
      var d = h <= 0
        ? 'M' + (cx - barW / 2) + ' ' + plotBottom + 'h' + barW
        : 'M' + (cx - barW / 2) + ' ' + plotBottom + 'V' + (y + r) +
          'a' + r + ' ' + r + ' 0 0 1 ' + r + ' ' + (-r) +
          'h' + (barW - 2 * r) +
          'a' + r + ' ' + r + ' 0 0 1 ' + r + ' ' + r +
          'V' + plotBottom + 'Z';
      svg.appendChild(svgEl('path', {
        d: d, fill: k >= BOWL_WINS ? 'var(--series-1)' : 'var(--series-2)' }));

      /* Value on the cap, but only where there is a bar to caption -- the rest
         are in the tooltip and the table view. */
      if (v >= 0.005) svg.appendChild(svgText(cx, y - 9, pct(v), 'value-label'));
      svg.appendChild(svgText(cx, plotBottom + 21, recordLabel(k, n), 'axis-label'));

      var orBetter = odds.slice(k).reduce(function (a, b) { return a + b; }, 0);
      var hit = svgEl('rect', { x: padL + band * k, y: plotTop - 14, width: band,
                                height: plotBottom - plotTop + 28, 'class': 'hit' });
      hoverable(hit, recordLabel(k, n), [
        pct(v, 1) + ' chance of exactly this record',
        pct(orBetter, 1) + ' chance of ' + k + ' wins or more'
      ]);
      svg.appendChild(hit);
    });
  }

  /* --------------------------------------------- bowl odds across the runs */
  function drawTrend(runs, idx) {
    var svg = document.getElementById('rp-trend');
    clear(svg);
    var W = 960, H = 240, padL = 46, padR = 26, padTop = 22, padBottom = 34;
    var plotTop = padTop, plotBottom = H - padBottom, plotH = plotBottom - plotTop;
    var plotW = W - padL - padR;
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);

    var t0 = parseDay(runs[0].date).getTime();
    var t1 = parseDay(runs[runs.length - 1].date).getTime();
    /* Inset the ends so the first and last dots sit clear of the axis rules. */
    var inset = 12, spanW = plotW - inset * 2;
    function xOf(r) {
      return t1 === t0 ? padL + plotW / 2
                       : padL + inset + (parseDay(r.date).getTime() - t0) / (t1 - t0) * spanW;
    }
    function yOf(v) { return plotBottom - v * plotH; }

    [0, 0.25, 0.5, 0.75, 1].forEach(function (v) {
      svg.appendChild(svgEl('line', { x1: padL, x2: W - padR, y1: yOf(v), y2: yOf(v),
                                      'class': v === 0 ? 'baseline' : 'gridline' }));
      svg.appendChild(svgText(padL - 10, yOf(v) + 4, pct(v, 0), 'axis-label', 'end'));
    });

    if (runs.length > 1) {
      var d = runs.map(function (r, i) {
        return (i ? 'L' : 'M') + xOf(r).toFixed(2) + ' ' + yOf(r.bowlOdds).toFixed(2);
      }).join(' ');
      svg.appendChild(svgEl('path', { d: d, fill: 'none', stroke: 'var(--series-1)',
                                      'stroke-width': 2, 'stroke-linejoin': 'round',
                                      'stroke-linecap': 'round' }));
    }

    /* Date ticks thin out until they stop colliding; the newest run always keeps one. */
    var labelled = [], lastX = -1e9;
    runs.forEach(function (r, i) {
      var x = xOf(r);
      if (i === 0 || x - lastX >= 78) { labelled.push(i); lastX = x; }
    });
    var lastI = runs.length - 1;
    while (labelled.length && labelled[labelled.length - 1] !== lastI &&
           xOf(runs[lastI]) - xOf(runs[labelled[labelled.length - 1]]) < 78) {
      labelled.pop();
    }
    if (labelled[labelled.length - 1] !== lastI) labelled.push(lastI);
    labelled.forEach(function (i) {
      svg.appendChild(svgText(xOf(runs[i]), plotBottom + 21, shortDay(runs[i].date), 'axis-label'));
    });

    runs.forEach(function (r, i) {
      var x = xOf(r), y = yOf(r.bowlOdds), on = i === idx;
      svg.appendChild(svgEl('circle', {
        cx: x, cy: y, r: on ? 6 : 4,
        fill: on ? 'var(--accent)' : 'var(--series-1)',
        stroke: 'var(--surface-1)', 'stroke-width': 2 }));
      if (on) {
        var above = y - 16 > plotTop;
        svg.appendChild(svgText(x, above ? y - 16 : y + 26, pct(r.bowlOdds), 'value-label'));
      }
      var hit = svgEl('circle', { cx: x, cy: y, r: 14, 'class': 'hit' });
      hoverable(hit, r.label + ' · ' + r.dateLabel, [
        pct(r.bowlOdds, 1) + ' chance of a bowl',
        'Tech was ' + r.record + ' · ' + r.expectedWins.toFixed(1) + ' projected wins',
        on ? 'Showing this run' : 'Click to load this run'
      ], function () { go(i); });
      svg.appendChild(hit);
    });
  }

  /* ------------------------------------------------------------- the tiles */
  /* Each tile pairs where the season is projected to end with where it actually
     stands right now, so the projection always has its footing beside it. */
  function tile(label, value, footer) {
    var t = el('div', 'tile');
    t.appendChild(el('div', 'label', label));
    t.appendChild(el('div', 'value', value));
    t.appendChild(el('div', 'delta', footer || '\u00a0'));
    return t;
  }

  function fillTiles(run) {
    var box = document.getElementById('rp-tiles');
    clear(box);
    var n = run.odds.length - 1;
    var best = run.odds.indexOf(Math.max.apply(null, run.odds));
    var wins = run.record.split('-')[0];

    box.appendChild(tile('Bowl Eligibility Chance', pct(run.bowlOdds), ''));
    box.appendChild(tile('Projected Wins', run.expectedWins.toFixed(1),
                         'Current: ' + wins ));
    box.appendChild(tile('Most Likely Record', recordLabel(best, n),
                         'Current: ' + run.record));
  }

  /* ------------------------------------------------------------- the tables */
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

  function fillGames(run, prev) {
    var body = document.querySelector('#rp-games tbody');
    clear(body);
    var before = {};
    (prev ? prev.schedule : []).forEach(function (g) { before[g.date + '|' + g.opponent] = g; });

    run.schedule.forEach(function (g) {
      /* Home is the unmarked case, the way a schedule reads on paper. The setting
         rides in the mark's alt/title too, so it is never the symbol alone. */
      var at = g.setting === 'Away' ? '@' : (g.setting === 'Neutral' ? 'N' : '');
      var named = g.setting === 'Away' ? 'at ' + g.opponent
                : g.setting === 'Neutral' ? g.opponent + ' (neutral site)' : g.opponent;
      var cells = [{ text: g.date, head: true },
                   { text: at, cls: 'at', title: at ? g.setting : '' }];
      if (g.logo) {
        var mark = el('img', 'teamlogo');
        mark.src = g.logo;
        mark.alt = named;           /* the name is still there for screen readers */
        mark.title = named;
        cells.push({ node: mark, cls: 'mark' });
      } else {
        cells.push({ text: g.opponent, cls: 'mark' });
      }
      if (g.source === 'final') {
        cells.push({ text: (g.pf > g.pa ? 'W ' : g.pf < g.pa ? 'L ' : 'T ') + g.pf + '-' + g.pa,
                     num: true });
        cells.push({ text: '—', num: true });
      } else {
        cells.push({ text: pct(g.odds) + (g.source === 'fpi' ? '' : ' (est.)'), num: true });
        var was = before[g.date + '|' + g.opponent];
        cells.push({ text: was && was.source !== 'final'
                       ? signed((g.odds - was.odds) * 100, 1, ' pts') : '—', num: true });
      }
      var tr = row(cells);
      if (g.source === 'final') tr.className = 'is-final';
      body.appendChild(tr);
    });

    var estimated = run.schedule.some(function (g) { return g.source === 'even'; });
    document.getElementById('rp-games-note').textContent = estimated
      ? 'ESPN had no FPI projection for at least one game; those are held at 50%.'
      : (prev ? 'Change is against the previous run, ' + prev.label + '.' : '');
  }

  /* ---------------------------------------------------------------- render */
  function fillRunSelect(runs) {
    clear(runSel);
    runs.forEach(function (r, i) {
      var o = el('option', null, r.label + ' · ' + r.record);
      o.value = i;
      runSel.appendChild(o);
    });
    runSel.value = state.index;
  }

  function render() {
    var runs = runsFor(state.year);
    if (!runs.length) return;
    state.index = Math.max(0, Math.min(state.index, runs.length - 1));
    var run = current(), prev = previousRun();

    fillRunSelect(runs);
    yearSel.value = state.year;
    prevBtn.disabled = state.index === 0;
    nextBtn.disabled = state.index === runs.length - 1;

    document.getElementById('rp-runline').textContent =
      "Using ESPN's FPI · " + run.label + ' · ' + run.dateLabel;

    fillTiles(run);
    drawOdds(run);
    drawTrend(runs, state.index);
    fillGames(run, prev);
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
  prevBtn.addEventListener('click', function () { go(state.index - 1); });
  nextBtn.addEventListener('click', function () { go(state.index + 1); });
  window.addEventListener('hashchange', function () { if (fromHash()) render(); });
  document.addEventListener('keydown', function (e) {
    if (e.target && /^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) return;
    if (e.key === 'ArrowLeft' && state.index > 0) go(state.index - 1);
    if (e.key === 'ArrowRight' && state.index < runsFor(state.year).length - 1) go(state.index + 1);
  });

  render();
})();
