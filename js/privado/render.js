(function () {
  'use strict';

  function text(value) {
    return document.createTextNode(value == null ? '—' : String(value));
  }

  function cell(value, className) {
    const td = document.createElement('td');
    if (className) td.className = className;
    td.appendChild(text(value));
    return td;
  }

  function button(label, action, id, danger = false) {
    const el = document.createElement('button');
    el.type = 'button';
    el.className = danger ? 'table-action danger' : 'table-action';
    el.dataset.action = action;
    el.dataset.id = id;
    el.appendChild(text(label));
    return el;
  }

  function emptyRow(colspan, message) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = colspan;
    td.className = 'empty-row';
    td.appendChild(text(message));
    tr.appendChild(td);
    return tr;
  }

  function money(value, currency = 'BRL') {
    const amount = Number(value || 0);
    try {
      return new Intl.NumberFormat('pt-BR', { style: 'currency', currency }).format(amount);
    } catch (_) {
      return `${currency} ${amount.toFixed(2)}`;
    }
  }

  function number(value, maximumFractionDigits = 4) {
    return new Intl.NumberFormat('pt-BR', { maximumFractionDigits }).format(Number(value || 0));
  }

  window.IAEMLOOPRender = Object.freeze({ text, cell, button, emptyRow, money, number });
})();
