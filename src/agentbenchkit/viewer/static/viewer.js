/* Local presentation only. Never fetch, mutate or persist evaluation evidence. */
(() => {
  function bindFilters() {
    document.querySelectorAll('[data-result-filter]').forEach(panel => {
      if (panel.dataset.filterBound) return;
      panel.dataset.filterBound = 'true';
      const input = panel.querySelector('[data-search-input]');
      const buttons = [...panel.querySelectorAll('[data-filter]')];
      const rows = [...panel.querySelectorAll('[data-result-row]')];
      let status = 'all';
      let page = 1;
      const pageSize = 25;
      const extras = [...panel.querySelectorAll('.matrix-extra input, .matrix-extra select')];
      const memoryKey = 'abk-filter:' + location.pathname + (location.pathname === '/compare' ? location.search : '');
      try {
        const saved = JSON.parse(sessionStorage.getItem(memoryKey) || '{}');
        status = saved.status || 'all'; page = saved.page || 1; if (input) input.value = saved.query || '';
        extras.forEach((x,i) => { if (saved.extras?.[i] !== undefined) { if (x.type === 'checkbox') x.checked = saved.extras[i]; else x.value = saved.extras[i]; }});
      } catch {}
      const value = selector => panel.querySelector(selector)?.value || '';

      function apply() {
        const query = (input?.value || '').trim().toLocaleLowerCase();
        let visible = 0;
        rows.forEach(row => {
          const matches = row.dataset.search.toLocaleLowerCase().includes(query)
            && (status === 'all' || row.dataset.status === status)
            && (!value('[data-matrix-repo]') || row.dataset.search.toLowerCase().includes(value('[data-matrix-repo]').toLowerCase()))
            && (!value('[data-matrix-agent]') || row.dataset.agent === value('[data-matrix-agent]'))
            && (!value('[data-matrix-execution]') || row.dataset.execution === value('[data-matrix-execution]'))
            && (!value('[data-matrix-verifier]') || row.dataset.verifier === value('[data-matrix-verifier]'))
            && (!panel.querySelector('[data-matrix-investigate]')?.checked || row.dataset.investigate === '1');
          row.hidden = !matches;
          if (matches) visible++;
        });
        panel.querySelector('[data-filter-count]').textContent = `${visible} / ${rows.length} 条`;
        panel.querySelector('[data-filter-empty]').hidden = visible !== 0;
        const matching = rows.filter(row => !row.hidden);
        const pageCount = Math.max(1, Math.ceil(matching.length / pageSize));
        page = Math.min(Math.max(1,page),pageCount);
        const order = value('[data-matrix-sort]');
        const sorted = order ? [...rows].sort((a,b) => Number(b.dataset[order] ?? -1) - Number(a.dataset[order] ?? -1)) : rows;
        sorted.forEach(row => row.parentNode.append(row));
        const displayed = sorted.filter(row => matching.includes(row));
        displayed.forEach((row,i) => row.hidden = i < (page-1)*pageSize || i >= page*pageSize);
        const pageLabel = panel.querySelector('[data-matrix-page]');
        if (pageLabel) pageLabel.textContent = `第 ${page} / ${pageCount} 页 · 每页 ${pageSize} 条`;
        const prev = panel.querySelector('[data-page-prev]'), next = panel.querySelector('[data-page-next]');
        if (prev) prev.disabled = page <= 1;
        if (next) next.disabled = page >= pageCount;
        try { sessionStorage.setItem(memoryKey, JSON.stringify({status, page, query:input?.value, extras:extras.map(x => x.type === 'checkbox' ? x.checked : x.value)})); } catch {}
        buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === status)));
      }
      input?.addEventListener('input', () => { page=1; apply(); });
      extras.forEach(x => x.addEventListener('input', () => {page=1; apply();}));
      panel.querySelector('[data-page-prev]')?.addEventListener('click', () => {page--;apply();});
      panel.querySelector('[data-page-next]')?.addEventListener('click', () => {page++;apply();});
      buttons.forEach(button => button.addEventListener('click', () => {
        status = button.dataset.filter; page=1;
        apply();
      }));
      // A task-map link must still locate a row hidden by the current filter.
      document.querySelectorAll('.task-tile').forEach(tile => tile.addEventListener('click', () => {
        status = 'all';
        const target = document.querySelector(tile.getAttribute('href'));
        page = Math.floor(Math.max(0, rows.indexOf(target))/pageSize)+1;
        extras.forEach(x => { if (x.type === 'checkbox') x.checked = false; else x.value = ''; });
        if (input) input.value = '';
        apply();
      }));
      apply();
    });
  }
  document.addEventListener('DOMContentLoaded', bindFilters);
  document.addEventListener('htmx:afterSwap', bindFilters);
})();
// All untrusted content stays text nodes. Syntax accents never evaluate HTML.
(() => {
  function setup() {
    document.querySelectorAll('[data-go-back]').forEach(b => b.addEventListener('click', () => history.back()));
    document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {
      const text = document.querySelector(button.dataset.copy)?.textContent || '';
      try { await navigator.clipboard.writeText(text); button.textContent = '已复制'; }
      catch { button.textContent = '复制不可用，请选中文本复制'; }
    }));
    document.querySelectorAll('[data-highlight]').forEach(code => {
      const source = code.textContent;
      const pattern = /(#.*$|\/\/.*$|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|\b(?:def|class|return|import|from|if|else|elif|for|while|try|except|raise|async|await|const|let|function|public|private|new|true|false|None|True|False)\b)/gm;
      let end = 0;
      code.textContent = '';
      for (const m of source.matchAll(pattern)) {
        code.append(document.createTextNode(source.slice(end, m.index)));
        const span = document.createElement('span');
        span.className = /^#|^\/\//.test(m[0]) ? 'token-comment' : /^["']/.test(m[0]) ? 'token-string' : 'token-keyword';
        span.textContent = m[0]; code.append(span); end = m.index + m[0].length;
      }
      code.append(document.createTextNode(source.slice(end)));
    });
    document.querySelectorAll('[data-loading-form]').forEach(form => form.addEventListener('submit', () => {
      const message = document.querySelector('[data-loading-message]'); if (message) message.hidden = false;
    }));
  }
  document.addEventListener('DOMContentLoaded', setup);
})();
