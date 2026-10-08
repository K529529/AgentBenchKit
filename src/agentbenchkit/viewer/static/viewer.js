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
      function apply() {
        const query = (input?.value || '').trim().toLocaleLowerCase();
        let visible = 0;
        rows.forEach(row => {
          const matches = row.dataset.search.toLocaleLowerCase().includes(query)
            && (status === 'all' || row.dataset.status === status);
          row.hidden = !matches;
          if (matches) visible++;
        });
        panel.querySelector('[data-filter-count]').textContent = `${visible} / ${rows.length} 条`;
        panel.querySelector('[data-filter-empty]').hidden = visible !== 0;
        buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === status)));
      }
      input?.addEventListener('input', apply);
      buttons.forEach(button => button.addEventListener('click', () => {
        status = button.dataset.filter;
        apply();
      }));
      // A task-map link must still locate a row hidden by the current filter.
      document.querySelectorAll('.task-tile').forEach(tile => tile.addEventListener('click', () => {
        status = 'all';
        if (input) input.value = '';
        apply();
      }));
      apply();
    });
  }
  document.addEventListener('DOMContentLoaded', bindFilters);
  document.addEventListener('htmx:afterSwap', bindFilters);
})();
