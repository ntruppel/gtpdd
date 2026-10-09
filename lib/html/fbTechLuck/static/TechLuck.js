/*
 * Tech Luck test — shared logic for index.html, Schedules.html and Scores.html.
 *
 * All three pages load this file plus games.js. Which page we are on is read
 * from <body data-page="...">, so there are no inline event handlers and no
 * page-specific script tags to keep in sync.
 *
 * The run is kept in localStorage under a single JSON key. Rather than adding
 * to running totals as the user walks through the seasons, we store the raw
 * picks per year and tally them at the end — that way reloading or stepping
 * back through a season cannot double-count anything.
 */
(function () {
  'use strict';

  var GAMES = window.TECH_LUCK_GAMES || {};
  var STORAGE_KEY = 'techLuck';

  // Program-wide baselines the luck score is measured against, and the weight
  // each part of the record carries.
  var BASE_HOME_PCT = 0.698;
  var BASE_AWAY_PCT = 0.394;
  var BASE_PF = 28.7;
  var BASE_PA = 28.2;
  var HOME_WEIGHT = 10;
  var AWAY_WEIGHT = 13;
  var NEUTRAL_WIN = 3;
  var NEUTRAL_LOSS = 1;

  /* ---------------------------------------------------------------- state */

  function seasons() {
    return Object.keys(GAMES).sort();
  }

  function scheduleFor(year) {
    return GAMES[String(year)] || [];
  }

  function loadState() {
    try {
      var raw = window.localStorage.getItem(STORAGE_KEY);
      var state = raw ? JSON.parse(raw) : null;
      if (!state || !state.firstYear || !state.lastYear) return null;
      if (!state.selections) state.selections = {};
      return state;
    } catch (err) {
      return null;
    }
  }

  function saveState(state) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (err) {
      /* Private browsing with storage disabled — nothing useful to do here. */
    }
  }

  // Every page after the first needs a run in progress; without one, start over.
  function requireState() {
    var state = loadState();
    if (!state) window.location.href = 'index.html';
    return state;
  }

  /* --------------------------------------------------------------- scoring */

  // Roll the saved picks up into one record. Unknown years or indexes are
  // skipped so stale storage from an older data file cannot break the page.
  function tally(selections) {
    var totals = {
      games: 0, wins: 0, losses: 0, ties: 0,
      homeWins: 0, homeLosses: 0,
      awayWins: 0, awayLosses: 0,
      neutWins: 0, neutLosses: 0,
      pf: 0, pa: 0
    };

    Object.keys(selections || {}).forEach(function (year) {
      var schedule = scheduleFor(year);
      (selections[year] || []).forEach(function (index) {
        var game = schedule[index];
        if (!game) return;

        var bucket = game.setting === 'Home' ? 'home'
          : game.setting === 'Away' ? 'away' : 'neut';

        totals.games += 1;
        totals.pf += game.pf;
        totals.pa += game.pa;

        if (game.result === 'Win') {
          totals.wins += 1;
          totals[bucket + 'Wins'] += 1;
        } else if (game.result === 'Loss') {
          totals.losses += 1;
          totals[bucket + 'Losses'] += 1;
        } else {
          totals.ties += 1;
        }
      });
    });

    return totals;
  }

  function luckScore(totals) {
    if (!totals.games) return 0;

    var homeGames = totals.homeWins + totals.homeLosses;
    var awayGames = totals.awayWins + totals.awayLosses;

    // A fan who saw no home (or no away) games is neither lucky nor unlucky
    // there, so that term drops out rather than counting as a winless record.
    var homeTerm = homeGames
      ? HOME_WEIGHT * (totals.homeWins / homeGames - BASE_HOME_PCT) : 0;
    var awayTerm = awayGames
      ? AWAY_WEIGHT * (totals.awayWins / awayGames - BASE_AWAY_PCT) : 0;

    var neutralTerm = totals.neutWins * NEUTRAL_WIN - totals.neutLosses * NEUTRAL_LOSS;
    var scoringTerm = (totals.pf / totals.games - BASE_PF) + (BASE_PA - totals.pa / totals.games);

    return homeTerm + awayTerm + neutralTerm + scoringTerm;
  }

  function record(wins, losses, ties) {
    return ties ? wins + '-' + losses + '-' + ties : wins + '-' + losses;
  }

  /* ------------------------------------------------------------ formatting */

  // Opponents arrive either as slugs ("mississippi-state") or as plain names
  // ("Nicholls State"); upper-casing both gives one consistent look.
  function opponentName(opponent) {
    return opponent.replace(/-/g, ' ').toUpperCase();
  }

  function settingPrefix(setting) {
    if (setting === 'Away') return '@ ';
    if (setting === 'Neutral') return '(N) ';
    return '';
  }

  function gameLabel(game) {
    return game.date + ': ' + settingPrefix(game.setting) + opponentName(game.opponent);
  }

  /* ------------------------------------------------------------ start page */

  function initStart() {
    var firstSelect = document.getElementById('firstYear');
    var lastSelect = document.getElementById('lastYear');
    var answer = document.getElementById('answer');
    var years = seasons();

    years.forEach(function (year) {
      [firstSelect, lastSelect].forEach(function (select) {
        var option = document.createElement('option');
        option.value = year;
        option.textContent = year;
        select.appendChild(option);
      });
    });

    if (years.length) {
      firstSelect.value = years[0];
      lastSelect.value = years[years.length - 1];
    }

    function start() {
      var firstYear = firstSelect.value;
      var lastYear = lastSelect.value;

      if (Number(lastYear) < Number(firstYear)) {
        answer.textContent = 'The most recent year must be the same as or after the first year.';
        answer.hidden = false;
        return;
      }

      answer.hidden = true;
      saveState({
        fname: document.getElementById('fname').value.trim(),
        firstYear: firstYear,
        lastYear: lastYear,
        currentYear: firstYear,
        selections: {}
      });
      window.location.href = 'Schedules.html';
    }

    document.getElementById('submit').addEventListener('click', start);

    // Enter in the name field should move on rather than reload the page.
    document.getElementById('years').addEventListener('submit', function (event) {
      event.preventDefault();
      start();
    });
  }

  /* --------------------------------------------------------- schedule page */

  function initSchedule() {
    var state = requireState();
    if (!state) return;

    var list = document.getElementById('gameList');
    var header = document.getElementById('yearHeader');
    var progress = document.getElementById('progress');
    var nextButton = document.getElementById('submit');

    // Keep the run inside the range the user picked, even if storage is stale.
    var years = seasons().filter(function (year) {
      return Number(year) >= Number(state.firstYear) && Number(year) <= Number(state.lastYear);
    });
    if (!years.length) {
      window.location.href = 'index.html';
      return;
    }
    if (years.indexOf(String(state.currentYear)) === -1) state.currentYear = years[0];

    var boxes = [];

    function render() {
      var year = String(state.currentYear);
      var schedule = scheduleFor(year);
      var picked = state.selections[year] || [];

      header.textContent = year + ' Season';
      document.title = year + ' Season — Tech Luck Test';
      progress.textContent = 'Season ' + (years.indexOf(year) + 1) + ' of ' + years.length;
      nextButton.textContent = year === String(state.lastYear) ? 'See My Score' : 'Next Season';

      list.innerHTML = '';
      boxes = schedule.map(function (game, index) {
        var id = 'game-' + index;

        var item = document.createElement('li');
        var box = document.createElement('input');
        box.type = 'checkbox';
        box.id = id;
        box.checked = picked.indexOf(index) !== -1;

        var label = document.createElement('label');
        label.setAttribute('for', id);
        label.textContent = gameLabel(game);

        item.appendChild(box);
        item.appendChild(label);
        list.appendChild(item);
        return box;
      });
    }

    function setAll(predicate) {
      var schedule = scheduleFor(state.currentYear);
      boxes.forEach(function (box, index) {
        box.checked = predicate(schedule[index]);
      });
    }

    function savePicks() {
      var picked = [];
      boxes.forEach(function (box, index) {
        if (box.checked) picked.push(index);
      });
      state.selections[String(state.currentYear)] = picked;
      saveState(state);
    }

    document.getElementById('selectAll').addEventListener('click', function () {
      setAll(function () { return true; });
    });
    document.getElementById('selectHome').addEventListener('click', function () {
      setAll(function (game) { return game.setting === 'Home'; });
    });
    document.getElementById('unselectAll').addEventListener('click', function () {
      setAll(function () { return false; });
    });

    nextButton.addEventListener('click', function () {
      savePicks();

      var next = years[years.indexOf(String(state.currentYear)) + 1];
      if (!next) {
        window.location.href = 'Scores.html';
        return;
      }

      state.currentYear = next;
      saveState(state);
      render();
      window.scrollTo(0, 0);
    });

    render();
  }

  /* ----------------------------------------------------------- scores page */

  function initScores() {
    var state = requireState();
    if (!state) return;

    var totals = tally(state.selections);
    var name = state.fname;

    document.getElementById('scoreTitle').textContent = name
      ? "Here's your final score, " + name + '!'
      : "Here's your final score!";

    document.getElementById('luckScore').textContent = luckScore(totals).toFixed(2);
    document.getElementById('overallRecord').textContent =
      record(totals.wins, totals.losses, totals.ties);
    document.getElementById('homeRecord').textContent =
      record(totals.homeWins, totals.homeLosses);
    document.getElementById('awayRecord').textContent =
      record(totals.awayWins, totals.awayLosses);
    document.getElementById('neutRecord').textContent =
      record(totals.neutWins, totals.neutLosses);
    document.getElementById('luckPF').textContent = totals.pf;
    document.getElementById('luckPA').textContent = totals.pa;

    // With nothing selected every number is zero, which reads as a bug unless
    // we say why.
    var note = document.getElementById('noGames');
    if (note) note.hidden = totals.games > 0;

    document.getElementById('reset').addEventListener('click', function () {
      try {
        window.localStorage.removeItem(STORAGE_KEY);
      } catch (err) {
        /* Nothing to clear. */
      }
      window.location.href = 'index.html';
    });
    document.getElementById('gtpdd').addEventListener('click', function () {
      window.location.href = 'https://gtpdd.dog';
    });
  }

  /* ------------------------------------------------------------- dispatch */

  var PAGES = { start: initStart, schedule: initSchedule, scores: initScores };

  document.addEventListener('DOMContentLoaded', function () {
    var init = PAGES[document.body.getAttribute('data-page')];
    if (init) init();
  });
}());
