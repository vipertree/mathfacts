/* Self-selected practice: tap fact cells in the grids to build a set, then
 * "Practice these". The set is submitted as hidden fact_ids inputs; the server
 * saves it (so it's remembered) and launches custom practice. */
(function () {
  const page = document.getElementById('progress-page');
  if (!page) return;
  const form = document.getElementById('select-form');
  const inputs = document.getElementById('sel-inputs');
  const countEls = [document.getElementById('sel-count'),
                    document.getElementById('sel-count2')];
  const goBtn = document.getElementById('sel-go');
  const clearBtn = document.getElementById('sel-clear');

  const selected = new Set();
  document.querySelectorAll('.cell.selected[data-fact-id]').forEach(
    c => selected.add(c.dataset.factId));

  function refresh() {
    countEls.forEach(el => { if (el) el.textContent = selected.size; });
    if (goBtn) goBtn.disabled = selected.size === 0;
    inputs.innerHTML = '';
    selected.forEach(id => {
      const i = document.createElement('input');
      i.type = 'hidden'; i.name = 'fact_ids'; i.value = id;
      inputs.appendChild(i);
    });
  }

  page.querySelectorAll('.fact-grid.selectable .cell[data-fact-id]').forEach(cell => {
    cell.addEventListener('click', () => {
      const id = cell.dataset.factId;
      if (selected.has(id)) { selected.delete(id); cell.classList.remove('selected'); }
      else { selected.add(id); cell.classList.add('selected'); }
      refresh();
    });
  });

  if (clearBtn) clearBtn.addEventListener('click', () => {
    selected.clear();
    page.querySelectorAll('.cell.selected').forEach(c => c.classList.remove('selected'));
    refresh();
  });

  refresh();
})();
