(() => {
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => Array.from(root.querySelectorAll(s));
  const body = document.body;
  const currentRel = body.dataset.currentRel || 'workspace';

  const state = {
    selection: new Set(),
    filterRegex: null,
    wrap: localStorage.getItem('word_wrap') !== 'false',
    lineNumbers: localStorage.getItem('line_numbers') !== 'false',
  };

  function setTheme() {
    const dark = localStorage.getItem('dark_mode') === 'true';
    body.classList.toggle('dark', dark);
  }
  setTheme();

  function flash(message, kind = 'success') {
    const area = $('#flash-area');
    if (!area) return alert(message);
    area.innerHTML = `<div class="banner ${kind}">${message}</div>`;
    setTimeout(() => {
      if (area.firstChild) area.innerHTML = '';
    }, 3000);
  }

  function jsonFetch(url, options = {}) {
    return fetch(url, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options,
    }).then(async (res) => {
      const data = (await res.text()) || '{}';
      let parsed;
      try { parsed = JSON.parse(data); } catch { parsed = { raw: data }; }
      if (!res.ok && res.status !== 207) throw { status: res.status, data: parsed };
      return { status: res.status, data: parsed };
    });
  }

  function syncSelection() {
    state.selection.clear();
    $$('.row-check:checked').forEach((cb) => state.selection.add(cb.value));
    const count = state.selection.size;
    const status = $('#status-text');
    if (status) {
      const items = $$('.row-check').length;
      status.textContent = `${items} items${count ? `, ${count} selected` : ''}`;
    }
    ['#delete-selected', '#move-selected', '#copy-selected'].forEach((sel) => {
      const el = $(sel); if (el) el.disabled = count === 0;
    });
    const rename = $('#rename-selected');
    if (rename) rename.disabled = count !== 1;
  }

  function applyFilter() {
    const input = $('#filter-input');
    if (!input) return;
    const error = $('#filter-error');
    const clear = $('#clear-filter');
    clear.hidden = !input.value;
    try {
      state.filterRegex = input.value ? new RegExp(input.value, 'i') : null;
      if (error) error.hidden = true;
      input.classList.remove('invalid');
    } catch {
      state.filterRegex = null;
      if (error) error.hidden = false;
      input.classList.add('invalid');
    }
    const allItems = $$('.file-table tbody tr, .file-card');
    allItems.forEach((row) => {
      const nameEl = row.querySelector('.name-cell a, .file-card-name');
      const text = nameEl ? nameEl.textContent : row.dataset.name || '';
      let visible = true;
      if (input.value) {
        try { visible = new RegExp(input.value, 'i').test(text); } catch { visible = true; }
      }
      row.style.display = visible ? '' : 'none';
      if (nameEl && visible && input.value && state.filterRegex) {
        nameEl.innerHTML = text.replace(state.filterRegex, (m) => `<mark>${m}</mark>`);
      } else if (nameEl) {
        nameEl.textContent = text;
      }
    });
  }

  function openModal(title, html) {
    const modal = $('#modal');
    if (!modal) return;
    $('#modal-title').textContent = title;
    $('#modal-body').innerHTML = html;
    modal.hidden = false;
    const auto = modal.querySelector('input, textarea, button:not([data-close-modal])');
    if (auto) auto.focus();
  }

  function closeModal() {
    const modal = $('#modal');
    if (modal) modal.hidden = true;
  }

  async function createNewFile() {
    openModal('New File', `
      <form id="new-file-form">
        <label>Filename</label>
        <input name="filename" required>
        <div class="modal-actions">
          <button type="button" class="secondary-btn" data-close-modal="1">Cancel</button>
          <button type="submit" class="primary-btn">Create</button>
        </div>
      </form>
    `);
    $('#new-file-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const filename = new FormData(e.target).get('filename');
      try {
        const res = await jsonFetch('/new-file', { method: 'POST', body: JSON.stringify({ dir: currentRel, filename }) });
        location.href = '/edit/' + res.data.path;
      } catch (err) {
        flash(err.data?.error || 'Failed to create file', 'danger');
      }
    });
  }

  async function createNewFolder() {
    openModal('New Folder', `
      <form id="new-folder-form">
        <label>Folder name</label>
        <input name="folder" required>
        <div class="modal-actions">
          <button type="button" class="secondary-btn" data-close-modal="1">Cancel</button>
          <button type="submit" class="primary-btn">Create</button>
        </div>
      </form>
    `);
    $('#new-folder-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const folder = new FormData(e.target).get('folder');
      try {
        await jsonFetch('/new-folder', { method: 'POST', body: JSON.stringify({ dir: currentRel, folder }) });
        location.reload();
      } catch (err) {
        flash(err.data?.error || 'Failed to create folder', 'danger');
      }
    });
  }

  async function renamePath(path, currentName) {
    openModal('Rename', `
      <form id="rename-form">
        <label>New name</label>
        <input name="new_name" value="${currentName.replace(/"/g, '&quot;')}" required>
        <div class="modal-actions">
          <button type="button" class="secondary-btn" data-close-modal="1">Cancel</button>
          <button type="submit" class="primary-btn">Rename</button>
        </div>
      </form>
    `);
    const input = $('#rename-form input[name="new_name"]');
    if (input) input.select();
    $('#rename-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const new_name = new FormData(e.target).get('new_name');
      try {
        await jsonFetch('/rename', { method: 'POST', body: JSON.stringify({ path, new_name }) });
        location.reload();
      } catch (err) {
        flash(err.data?.error || 'Rename failed', 'danger');
      }
    });
  }

  async function deletePaths(paths, label) {
    const ok = confirm(paths.length === 1 ? `Delete '${label}'? This cannot be undone.` : `Delete ${paths.length} items? This cannot be undone.`);
    if (!ok) return;
    try {
      const res = await jsonFetch('/delete', { method: 'POST', body: JSON.stringify({ paths }) });
      if (res.status === 207) flash(`Deleted ${res.data.deleted.length}; ${res.data.failed.length} failed`, 'warning');
      else flash('Deleted successfully.');
      location.reload();
    } catch (err) {
      flash(err.data?.error || 'Delete failed', 'danger');
    }
  }

  async function copyMove(action) {
    const label = action === 'move' ? 'Move' : 'Copy';
    openModal(`${label} selected`, `
      <form id="copy-move-form">
        <label>Destination</label>
        <input name="destination" value="workspace" required>
        <div class="modal-actions">
          <button type="button" class="secondary-btn" data-close-modal="1">Cancel</button>
          <button type="submit" class="primary-btn">${label}</button>
        </div>
      </form>
    `);
    $('#copy-move-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const destination = new FormData(e.target).get('destination');
      try {
        await jsonFetch('/' + action, { method: 'POST', body: JSON.stringify({ paths: [...state.selection], destination }) });
        location.reload();
      } catch (err) {
        flash(err.data?.error || `${label} failed`, 'danger');
      }
    });
  }

  async function uploadFiles(files) {
    const form = new FormData();
    Array.from(files).forEach((f) => form.append('files', f, f.name));
    flash(`Uploading ${files.length} file${files.length === 1 ? '' : 's'}...`, 'warning');
    const res = await fetch(`/upload?dir=${encodeURIComponent(currentRel)}`, { method: 'POST', body: form });
    const data = await res.json();
    if (res.ok || res.status === 207) {
      const failed = data.failed?.length || 0;
      flash(`Uploaded ${data.uploaded?.length || 0} file(s)${failed ? `, ${failed} failed` : ''}`, failed ? 'warning' : 'success');
      setTimeout(() => location.reload(), 500);
    } else {
      flash(data.error || 'Upload failed', 'danger');
    }
  }

  function initBrowserPage() {
    const selectAll = $('#select-all');
    if (selectAll) selectAll.addEventListener('change', () => {
      $$('.row-check').forEach((cb) => { cb.checked = selectAll.checked; });
      syncSelection();
    });
    $$('.row-check').forEach((cb) => cb.addEventListener('change', syncSelection));
    syncSelection();

    const filterInput = $('#filter-input');
    if (filterInput) filterInput.addEventListener('input', applyFilter);
    const clear = $('#clear-filter');
    if (clear) clear.addEventListener('click', () => { filterInput.value = ''; applyFilter(); filterInput.focus(); });
    const mobileSearch = $('#mobile-search-toggle');
    if (mobileSearch) mobileSearch.addEventListener('click', () => $('#filter-panel')?.classList.toggle('open'));

    $('#new-file-btn')?.addEventListener('click', createNewFile);
    $('#new-folder-btn')?.addEventListener('click', createNewFolder);
    $('#upload-btn')?.addEventListener('click', () => $('#file-input')?.click());
    $('#mobile-overflow')?.addEventListener('click', () => openModal('Actions', `
      <div class="stack-actions">
        <button class="primary-btn" id="overflow-new-folder">New Folder</button>
        <button class="primary-btn" id="overflow-new">New File</button>
        <button class="secondary-btn" id="overflow-upload">Upload File</button>
        <button class="secondary-btn" id="overflow-sort">Sort info</button>
        <label class="checkbox-label"><input type="checkbox" id="overflow-dotfiles"> Show dotfiles</label>
        <a class="secondary-btn inline-link-btn" href="/shortcuts">Shortcuts</a>
      </div>
    `));

    document.addEventListener('click', (e) => {
      const renameBtn = e.target.closest('.js-rename');
      if (renameBtn) renamePath(renameBtn.dataset.path, renameBtn.dataset.name);
      const deleteBtn = e.target.closest('.js-delete-one');
      if (deleteBtn) deletePaths([deleteBtn.dataset.path], deleteBtn.dataset.name);
      if (e.target.matches('[data-close-modal]')) closeModal();
      if (e.target.id === 'overflow-new-folder') createNewFolder();
      if (e.target.id === 'overflow-new') createNewFile();
      if (e.target.id === 'overflow-upload') $('#file-input')?.click();
      if (e.target.id === 'overflow-sort') flash('Folders stay first. Use the regex filter and browser search for now.', 'warning');
    });

    $('#delete-selected')?.addEventListener('click', () => deletePaths([...state.selection], 'selected items'));
    $('#rename-selected')?.addEventListener('click', () => {
      const selected = [...state.selection][0];
      if (!selected) return;
      const name = selected.split('/').pop();
      renamePath(selected, name);
    });
    $('#move-selected')?.addEventListener('click', () => copyMove('move'));
    $('#copy-selected')?.addEventListener('click', () => copyMove('copy'));
    $('#file-input')?.addEventListener('change', (e) => {
      if (e.target.files?.length) uploadFiles(e.target.files);
    });
    $('#show-dotfiles')?.addEventListener('change', (e) => {
      const url = new URL(location.href);
      url.searchParams.set('show_hidden', e.target.checked ? '1' : '0');
      location.href = url.toString();
    });
  }

  function lineDiff(a, b) {
    const oldLines = a.split('\n');
    const newLines = b.split('\n');
    const out = [];
    let i = 0, j = 0;
    while (i < oldLines.length || j < newLines.length) {
      if (oldLines[i] === newLines[j]) {
        out.push(`<div class="diff-line same"> ${escapeHtml(oldLines[i] ?? '')}</div>`);
        i++; j++; continue;
      }
      if (j < newLines.length && !oldLines.slice(i + 1).includes(newLines[j])) {
        out.push(`<div class="diff-line add">+ ${escapeHtml(newLines[j])}</div>`);
        j++; continue;
      }
      if (i < oldLines.length) {
        out.push(`<div class="diff-line del">- ${escapeHtml(oldLines[i])}</div>`);
        i++; continue;
      }
      if (j < newLines.length) {
        out.push(`<div class="diff-line add">+ ${escapeHtml(newLines[j])}</div>`);
        j++;
      }
    }
    return out.join('');
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  async function saveEditor() {
    const editor = $('#editor');
    if (!editor) return;
    const error = $('#save-error');
    error.hidden = true;
    const form = new URLSearchParams({ content: editor.value });
    const res = await fetch(editor.dataset.saveUrl, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: form });
    if (res.redirected) {
      localStorage.removeItem(`draft:${currentRel}`);
      location.href = res.url;
      return;
    }
    let msg = 'Save failed';
    try { msg = (await res.json()).error || msg; } catch {}
    error.textContent = msg;
    error.hidden = false;
  }

  function initEditorPage() {
    const editor = $('#editor');
    if (!editor) return;
    const lines = $('#editor-lines');
    const getWrappedRows = (lineText) => {
      if (!editor.classList.contains('wrap')) return 1;
      const style = getComputedStyle(editor);
      const leftPad = parseFloat(style.paddingLeft || '0');
      const rightPad = parseFloat(style.paddingRight || '0');
      const usableWidth = editor.clientWidth - leftPad - rightPad;
      if (usableWidth <= 0) return 1;
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      if (!ctx) return 1;
      ctx.font = `${style.fontSize} ${style.fontFamily}`;
      const charWidth = ctx.measureText('M').width || 8;
      const columns = Math.max(1, Math.floor(usableWidth / charWidth));
      const tabSize = Number.parseInt(style.tabSize || '8', 10) || 8;
      const expanded = lineText.replace(/\t/g, ' '.repeat(tabSize));
      return Math.max(1, Math.ceil(Math.max(1, expanded.length) / columns));
    };
    const resizeEditorToContent = () => {
      editor.style.height = 'auto';
      editor.style.height = `${Math.max(editor.scrollHeight, 240)}px`;
    };
    const renderEditorLines = () => {
      if (!lines) return;
      const out = [];
      const logicalLines = editor.value.split('\n');
      for (let i = 0; i < logicalLines.length; i += 1) {
        out.push(i + 1);
        const wrappedRows = getWrappedRows(logicalLines[i]);
        for (let j = 1; j < wrappedRows; j += 1) out.push('');
      }
      lines.textContent = out.join('\n');
      lines.scrollTop = editor.scrollTop;
    };
    editor.addEventListener('scroll', () => {
      if (lines) lines.scrollTop = editor.scrollTop;
    });
    resizeEditorToContent();
    renderEditorLines();
    const draftKey = `draft:${currentRel}`;
    const savedDraft = localStorage.getItem(draftKey);
    const draftBanner = $('#draft-banner');
    if (savedDraft) {
      try {
        const draft = JSON.parse(savedDraft);
        if (draft.content !== editor.value) {
          draftBanner.hidden = false;
          draftBanner.innerHTML = `Unsaved draft from ${new Date(draft.savedAt).toLocaleString()}. <button id="restore-draft" class="link-btn">Restore</button> <button id="discard-draft" class="link-btn">Discard</button>`;
        }
      } catch {}
    }
    let timer;
    editor.addEventListener('input', () => {
      resizeEditorToContent();
      renderEditorLines();
      clearTimeout(timer);
      timer = setTimeout(() => {
        localStorage.setItem(draftKey, JSON.stringify({ content: editor.value, savedAt: new Date().toISOString() }));
      }, 5000);
    });
    $('#save-btn')?.addEventListener('click', saveEditor);
    $('#toggle-diff-btn')?.addEventListener('click', () => {
      const panel = $('#diff-panel');
      panel.hidden = !panel.hidden;
      if (!panel.hidden) panel.innerHTML = lineDiff($('#original-content').value, editor.value);
    });
    document.addEventListener('click', (e) => {
      if (e.target.id === 'restore-draft') {
        editor.value = JSON.parse(localStorage.getItem(draftKey)).content;
        resizeEditorToContent();
        renderEditorLines();
        draftBanner.hidden = true;
      }
      if (e.target.id === 'discard-draft') {
        localStorage.removeItem(draftKey);
        draftBanner.hidden = true;
      }
      if (e.target.matches('[data-close-modal]')) closeModal();
    });
    window.addEventListener('resize', renderEditorLines);
    window.addEventListener('editor-layout-changed', renderEditorLines);
  }

  function initViewerPage() {
    const raw = $('#viewer-raw');
    $('#copy-file-btn')?.addEventListener('click', async () => {
      if (!raw) return;
      await navigator.clipboard.writeText(raw.value);
      flash('Copied!');
    });
  }

  function toggleWrap() {
    state.wrap = !state.wrap;
    localStorage.setItem('word_wrap', state.wrap ? 'true' : 'false');
    $('#viewer-pre')?.classList.toggle('wrap', state.wrap);
    $('#editor')?.classList.toggle('wrap', state.wrap);
    window.dispatchEvent(new Event('editor-layout-changed'));
  }

  function toggleLineNumbers() {
    state.lineNumbers = !state.lineNumbers;
    localStorage.setItem('line_numbers', state.lineNumbers ? 'true' : 'false');
    body.classList.toggle('hide-line-numbers', !state.lineNumbers);
  }

  $('#theme-toggle')?.addEventListener('click', () => {
    localStorage.setItem('dark_mode', localStorage.getItem('dark_mode') === 'true' ? 'false' : 'true');
    setTheme();
  });
  $('#toggle-wrap-btn')?.addEventListener('click', toggleWrap);
  $('#toggle-lines-btn')?.addEventListener('click', toggleLineNumbers);

  if (!state.wrap) {
    $('#viewer-pre')?.classList.remove('wrap');
    $('#editor')?.classList.remove('wrap');
  }
  if (!state.lineNumbers) body.classList.add('hide-line-numbers');

  initBrowserPage();
  initEditorPage();
  initViewerPage();

  document.addEventListener('keydown', (e) => {
    const inField = /INPUT|TEXTAREA/.test(document.activeElement?.tagName || '');
    if (e.key === '?' && !inField) location.href = '/shortcuts';
    if (e.key === '/' && !inField && $('#filter-input')) { e.preventDefault(); $('#filter-input').focus(); }
    if (e.key.toLowerCase() === 'n' && !inField && $('#new-file-btn')) createNewFile();
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's' && $('#editor')) { e.preventDefault(); saveEditor(); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'd' && $('#editor')) {
      e.preventDefault(); $('#toggle-diff-btn')?.click();
    }
    if ((e.key === 'Backspace' || e.key.toLowerCase() === 'u') && !inField) {
      const back = document.querySelector('.ghost-btn[href^="/browse/"]');
      if (back) location.href = back.href;
    }
    if (e.key === 'Delete' && !inField && state.selection.size) deletePaths([...state.selection], 'selected items');
    if (e.key.toLowerCase() === 'e' && !inField) {
      const link = document.querySelector('a.primary-btn[href^="/edit/"]');
      if (link && !link.classList.contains('disabled-link')) location.href = link.href;
    }
    if (e.key.toLowerCase() === 'd' && !inField && !$('#editor')) {
      const link = document.querySelector('a.secondary-btn[href^="/download/"]');
      if (link) location.href = link.href;
    }
    if (e.key === 'Escape') closeModal();
    if (e.key.toLowerCase() === 'a' && !inField && $$('.row-check').length) {
      e.preventDefault();
      const shouldCheck = !$$('.row-check').every((cb) => cb.checked);
      $$('.row-check').forEach((cb) => { cb.checked = shouldCheck; });
      syncSelection();
    }
  });
})();
