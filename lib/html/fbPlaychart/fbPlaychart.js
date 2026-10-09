(function () {
  var nav = document.getElementById('gtpdd-nav');
  var cur = nav.getAttribute('data-current');
  var curYear = nav.getAttribute('data-year');
  var ysel = document.getElementById('gtpdd-year');
  var sel = document.getElementById('gtpdd-game');

  document.getElementById('gtpdd-go').addEventListener('click', function () {
    if (sel.value) window.location.href = sel.value;
  });

  // manifest.js carries every season and its games, so switching years costs no request.
  var manifest = window.GTPDD_PLAYCHARTS || { years: [], games: {} };

  // Hrefs are relative to this page, which sits in <root>/<year>/.
  function fillGames(y) {
    sel.innerHTML = '';
    (manifest.games[y] || []).forEach(function (g) {
      var o = document.createElement('option');
      o.value = '../' + y + '/' + g.href;
      o.textContent = g.label;
      if (String(y) === curYear && g.href === cur) o.selected = true;
      sel.appendChild(o);
    });
  }
  ysel.addEventListener('change', function () { fillGames(ysel.value); });

  if (manifest.years.length) {
    ysel.innerHTML = '';
    manifest.years.forEach(function (y) {
      var o = document.createElement('option');
      o.value = y;
      o.textContent = y;
      if (String(y) === curYear) o.selected = true;
      ysel.appendChild(o);
    });
  }
  fillGames(curYear);

  var tip = document.getElementById('pbp-tooltip');
  document.addEventListener('mousemove', function (e) {
    var g = e.target.closest ? e.target.closest("g[id^='pbp']") : null;
    var text = g && g.getAttribute('data-text');
    if (text) {
      tip.textContent = text;
      tip.style.display = 'block';
      tip.style.left = Math.min(e.clientX + 14, window.innerWidth - 260) + 'px';
      tip.style.top = (e.clientY + 14) + 'px';
    } else {
      tip.style.display = 'none';
    }
  });
})();
