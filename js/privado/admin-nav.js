(function () {
  'use strict';

  async function revealAdminEntry() {
    const entry = document.querySelector('[data-admin-entry]');
    if (!entry) return;
    entry.hidden = true;
    try {
      const context = await window.IAEMLOOPAuth.requireApprovedSession();
      const { data, error } = await context.client.rpc('admin_is_current_user');
      if (error) throw error;
      if (data === true) entry.hidden = false;
    } catch (_) {
      entry.hidden = true;
    }
  }

  document.addEventListener('DOMContentLoaded', revealAdminEntry);
  document.addEventListener('iaemloop:session-invalidated', () => {
    const entry = document.querySelector('[data-admin-entry]');
    if (entry) entry.hidden = true;
  });
})();
