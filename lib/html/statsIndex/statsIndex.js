// Sport toggles for stats.gtpdd.dog: shows the cards for every selected sport
(function () {
  var buttons = Array.prototype.slice.call(document.querySelectorAll('.filter'));
  var cards = Array.prototype.slice.call(document.querySelectorAll('.card'));
  var allButton = buttons.filter(function (b) { return b.dataset.filter === 'all'; })[0];
  var sportButtons = buttons.filter(function (b) { return b !== allButton; });

  // Start from the selection the page was built with (statsIndex.py's DEFAULT_SECTIONS)
  var selected = {};
  sportButtons.forEach(function (b) {
    if (b.getAttribute('aria-pressed') === 'true') selected[b.dataset.filter] = true;
  });

  function countSelected() {
    return sportButtons.filter(function (b) { return selected[b.dataset.filter]; }).length;
  }

  // Syncs the toggles and the cards to the current selection
  function render() {
    sportButtons.forEach(function (b) {
      b.setAttribute('aria-pressed', selected[b.dataset.filter] ? 'true' : 'false');
    });
    // 'All Sports' reads as pressed whenever every sport is selected
    if (allButton) allButton.setAttribute('aria-pressed', countSelected() === sportButtons.length ? 'true' : 'false');
    cards.forEach(function (c) { c.hidden = !selected[c.dataset.section]; });
  }

  // 'All Sports' selects every sport
  if (allButton) allButton.addEventListener('click', function () {
    sportButtons.forEach(function (b) { selected[b.dataset.filter] = true; });
    render();
  });

  // A sport toggles on and off, but the last one selected stays on so the page is never empty
  sportButtons.forEach(function (b) {
    b.addEventListener('click', function () {
      var key = b.dataset.filter;
      if (selected[key] && countSelected() === 1) return;
      selected[key] = !selected[key];
      render();
    });
  });
})();
