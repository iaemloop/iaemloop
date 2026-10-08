(function () {
  'use strict';

  var STORAGE_KEY = 'iaemloop-theme';
  var EDITORIAL = 'editorial';
  var CLASSIC = 'classic';

  function readTheme() {
    try {
      return window.localStorage.getItem(STORAGE_KEY) === EDITORIAL ? EDITORIAL : CLASSIC;
    } catch (_) {
      return CLASSIC;
    }
  }

  function updateButtons(theme) {
    var editorialActive = theme === EDITORIAL;
    document.querySelectorAll('[data-theme-toggle]').forEach(function (button) {
      button.setAttribute('aria-pressed', editorialActive ? 'true' : 'false');
      button.setAttribute('title', editorialActive ? 'Voltar ao visual clássico' : 'Ativar visual editorial');
      var label = button.querySelector('[data-theme-label]');
      if (label) label.textContent = editorialActive ? 'Visual clássico' : 'Visual editorial';
    });
  }

  function applyTheme(theme, persist) {
    var selected = theme === EDITORIAL ? EDITORIAL : CLASSIC;
    document.documentElement.classList.toggle('theme-editorial', selected === EDITORIAL);
    document.documentElement.dataset.theme = selected;
    if (persist) {
      try { window.localStorage.setItem(STORAGE_KEY, selected); } catch (_) {}
    }
    updateButtons(selected);
  }

  function toggleTheme() {
    applyTheme(document.documentElement.classList.contains('theme-editorial') ? CLASSIC : EDITORIAL, true);
  }

  window.IAEMLOOPTheme = { apply: applyTheme, toggle: toggleTheme, current: readTheme };
  applyTheme(readTheme(), false);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { updateButtons(readTheme()); });
  } else {
    updateButtons(readTheme());
  }

  window.addEventListener('storage', function (event) {
    if (event.key === STORAGE_KEY) applyTheme(readTheme(), false);
  });
})();
