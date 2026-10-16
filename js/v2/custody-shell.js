(function () {
  'use strict';

  const FRAME_STYLESHEET = '/css/v2/custody.css?v=20261016-session2';

  function prepareFrame(frame) {
    const wrapper = frame.closest('.custody-frame-wrap');
    try {
      const doc = frame.contentDocument;
      if (!doc || !doc.documentElement || frame.src === 'about:blank') return;
      doc.body?.classList.add('iaemloop-custody-frame');
      if (!doc.head.querySelector('link[data-v2-custody-theme]')) {
        const link = doc.createElement('link');
        link.rel = 'stylesheet';
        link.href = FRAME_STYLESHEET;
        link.dataset.v2CustodyTheme = 'true';
        doc.head.appendChild(link);
      }
      wrapper?.setAttribute('data-custody-loading', 'false');
    } catch (_) {
      wrapper?.setAttribute('data-custody-loading', 'false');
    }
  }

  function resetFrame() {
    document.querySelector('.custody-frame-wrap')?.setAttribute('data-custody-loading', 'true');
  }

  document.addEventListener('DOMContentLoaded', () => {
    const frame = document.querySelector('[data-private-frame]');
    if (!frame) return;
    frame.addEventListener('load', () => prepareFrame(frame));
    if (frame.src && frame.src !== 'about:blank') prepareFrame(frame);
  });
  document.addEventListener('iaemloop:session-invalidated', resetFrame);
})();
