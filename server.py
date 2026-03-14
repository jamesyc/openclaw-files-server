#!/usr/bin/env python3
import argparse
import html
import io
import json
import mimetypes
import os
import posixpath
import shutil
import sys
import tempfile
import urllib.parse
from datetime import datetime
from email.parser import BytesParser
from email.policy import default as email_default_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WORKSPACE_ROOT = Path('/Users/james/.openclaw/workspace').expanduser().resolve()
PARENT_ROOT = WORKSPACE_ROOT.parent.resolve()
WARN_SIZE = 1 * 1024 * 1024
MAX_EDIT_SIZE = 10 * 1024 * 1024
STATIC_DIR = Path(__file__).with_name('static')
ENV_FILE = Path(__file__).with_name('.env')


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key, value)


load_env_file(ENV_FILE)
DASHBOARD_URL = os.environ.get('OPENCLAW_DASHBOARD_URL', '').strip()

TEXT_EXTENSIONS = {
    '.txt', '.md', '.py', '.js', '.css', '.html', '.json', '.yaml', '.yml', '.xml', '.sh', '.toml', '.ini',
    '.cfg', '.conf', '.log', '.csv', '.ts', '.tsx', '.jsx', '.sql', '.gitignore', '.env', '.rb', '.go', '.rs'
}
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'}


def is_readable_text(path: Path) -> bool:
    if path.suffix.lower() in IMAGE_EXTENSIONS:
        return False
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    try:
        with path.open('rb') as f:
            chunk = f.read(2048)
        if b'\x00' in chunk:
            return False
        chunk.decode('utf-8')
        return True
    except Exception:
        return False


def fmt_size(size: int) -> str:
    units = ['B', 'KB', 'MB', 'GB']
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == 'B':
                return f'{int(value)} {unit}'
            return f'{value:.1f} {unit}'
        value /= 1024
    return f'{size} B'


def fmt_dt(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')


def split_relpath(relpath: str):
    relpath = relpath.strip('/')
    if not relpath:
        return []
    return [p for p in relpath.split('/') if p not in ('', '.')]


def safe_join(relpath: str) -> Path:
    if '\x00' in relpath:
        raise ValueError('Null byte in path')
    parts = split_relpath(urllib.parse.unquote(relpath))
    candidate = PARENT_ROOT
    for part in parts:
        if part == '..':
            candidate = candidate.parent
        else:
            candidate = candidate / part
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(PARENT_ROOT)
    except ValueError as exc:
        raise PermissionError('Path escapes allowed root') from exc
    return resolved


def rel_from_parent(path: Path) -> str:
    return path.resolve().relative_to(PARENT_ROOT).as_posix()


def rel_from_workspace(path: Path) -> str:
    return path.resolve().relative_to(WORKSPACE_ROOT).as_posix()


def breadcrumb_parts(path: Path):
    rel = path.resolve().relative_to(PARENT_ROOT)
    parts = rel.parts
    crumbs = [{
        'name': PARENT_ROOT.name,
        'href': '/browse/',
        'current': len(parts) == 0,
    }]
    accum = []
    for idx, part in enumerate(parts):
        accum.append(part)
        href = '/browse/' + '/'.join(accum)
        crumbs.append({'name': part, 'href': href, 'current': idx == len(parts) - 1})
    return crumbs


def list_dir(path: Path, show_hidden: bool):
    entries = []
    for entry in path.iterdir():
        if not show_hidden and entry.name.startswith('.'):
            continue
        try:
            stat = entry.stat()
        except OSError:
            continue
        is_dir = entry.is_dir()
        entries.append({
            'name': entry.name,
            'relpath': rel_from_parent(entry),
            'is_dir': is_dir,
            'size': None if is_dir else stat.st_size,
            'size_display': '—' if is_dir else fmt_size(stat.st_size),
            'created': stat.st_ctime,
            'created_display': fmt_dt(stat.st_ctime),
            'modified': stat.st_mtime,
            'modified_display': fmt_dt(stat.st_mtime),
            'icon': '📁' if is_dir else ('🖼️' if entry.suffix.lower() in IMAGE_EXTENSIONS else '📄'),
        })
    entries.sort(key=lambda e: (not e['is_dir'], e['name'].lower()))
    return entries


def html_page(title: str, body: str, *, current_rel: str = '', extra_head: str = '') -> bytes:
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="/static/style.css">
  {extra_head}
</head>
<body data-current-rel="{html.escape(current_rel)}">
{body}
<script src="/static/app.js"></script>
</body>
</html>'''.encode('utf-8')


def render_dashboard_link() -> str:
    if not DASHBOARD_URL:
        return ''
    escaped_url = html.escape(DASHBOARD_URL, quote=True)
    return (
        f'<a class="ghost-btn" href="{escaped_url}" target="_blank" '
        'rel="noopener noreferrer">Dashboard</a>'
    )


def parse_multipart(headers, body: bytes):
    content_type = headers.get('Content-Type', '')
    if 'multipart/form-data' not in content_type:
        raise ValueError('Expected multipart/form-data')
    message = BytesParser(policy=email_default_policy).parsebytes(
        f'Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n'.encode('utf-8') + body
    )
    files = []
    for part in message.iter_parts():
        if part.get_content_disposition() != 'form-data':
            continue
        name = part.get_param('name', header='content-disposition')
        if name != 'files':
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b''
        files.append((filename, payload))
    return files


def atomic_write_text_preserving_metadata(target: Path, content: str) -> None:
    original_stat = target.stat()
    fd, tmp_name = tempfile.mkstemp(prefix=target.name + '.', suffix='.tmp', dir=str(target.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as tmp:
            tmp.write(content)
        shutil.copystat(target, tmp_name)
        if os.geteuid() == 0:
            os.chown(tmp_name, original_stat.st_uid, original_stat.st_gid)
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


class FileBrowserHandler(BaseHTTPRequestHandler):
    server_version = 'OpenClawFileBrowser/0.1'

    def log_message(self, fmt, *args):
        sys.stderr.write('%s - - [%s] %s\n' % (self.address_string(), self.log_date_time_string(), fmt % args))

    def parsed(self):
        return urllib.parse.urlparse(self.path)

    def send_html(self, content: bytes, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, obj, status=200):
        data = json.dumps(obj).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_text(self, text: str, status=200, content_type='text/plain; charset=utf-8'):
        data = text.encode('utf-8', errors='replace')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location: str, status=302):
        self.send_response(status)
        self.send_header('Location', location)
        self.end_headers()

    def read_body_json(self):
        length = int(self.headers.get('Content-Length', '0') or '0')
        raw = self.rfile.read(length)
        return json.loads(raw.decode('utf-8') or '{}')

    def current_show_hidden(self, query):
        return query.get('show_hidden', ['0'])[-1] == '1'

    def get_target_path(self, relpath: str):
        try:
            return safe_join(relpath)
        except ValueError as e:
            self.send_text(str(e), 400)
            return None
        except PermissionError as e:
            self.send_text(str(e), 403)
            return None

    def get_static_path(self, name: str) -> Path:
        return (STATIC_DIR / name).resolve()

    def do_GET(self):
        parsed = self.parsed()
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == '/':
            self.redirect('/browse/workspace')
            return
        if path == '/shortcuts':
            self.handle_shortcuts()
            return
        if path.startswith('/static/'):
            self.handle_static(path[len('/static/'):])
            return
        if path.startswith('/browse/'):
            self.handle_browse(path[len('/browse/'):], query)
            return
        if path.startswith('/edit/'):
            self.handle_edit(path[len('/edit/'):])
            return
        if path.startswith('/download/'):
            self.handle_download(path[len('/download/'):])
            return
        self.send_text('Not found', 404)

    def do_POST(self):
        parsed = self.parsed()
        path = parsed.path
        if path.startswith('/save/'):
            self.handle_save(path[len('/save/'):])
            return
        if path == '/delete':
            self.handle_delete()
            return
        if path == '/rename':
            self.handle_rename()
            return
        if path == '/new-file':
            self.handle_new_file()
            return
        if path == '/new-folder':
            self.handle_new_folder()
            return
        if path == '/upload':
            self.handle_upload()
            return
        if path == '/move':
            self.handle_batch_copy_move(move=True)
            return
        if path == '/copy':
            self.handle_batch_copy_move(move=False)
            return
        self.send_text('Not found', 404)

    def handle_static(self, filename: str):
        target = self.get_static_path(posixpath.basename(filename))
        if not target.exists() or STATIC_DIR not in target.parents:
            self.send_text('Not found', 404)
            return
        ctype = mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
        data = target.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def render_layout(self, title: str, inner: str, current: Path):
        crumbs = breadcrumb_parts(current)
        crumb_html = ' / '.join(
            f"<a href='{html.escape(c['href'])}'>{html.escape(c['name'])}</a>" if not c['current'] else f"<strong>{html.escape(c['name'])}</strong>"
            for c in crumbs
        )
        rel = rel_from_parent(current)
        dashboard_link = render_dashboard_link()
        return html_page(title, f'''
<div class="app-shell">
<header class="topbar">
  <div class="brand"><a href="/browse/workspace">OpenClaw Files</a></div>
  <nav class="breadcrumb">{crumb_html}</nav>
  <div class="topbar-actions">
    {dashboard_link}
    <button id="theme-toggle" class="icon-btn" type="button" aria-label="Toggle dark mode">◐</button>
    <button id="mobile-menu-button" class="icon-btn mobile-only" type="button" aria-label="Open menu">⋯</button>
  </div>
</header>
{inner}
</div>
''', current_rel=rel)

    def handle_browse(self, relpath: str, query):
        target = self.get_target_path(relpath)
        if target is None:
            return
        if not target.exists():
            self.send_text('Not found', 404)
            return
        if target.is_file():
            self.render_file_view(target, query)
            return
        show_hidden = self.current_show_hidden(query)
        if query.get('json', ['0'])[-1] == '1':
            self.send_json({'cwd': rel_from_parent(target), 'entries': list_dir(target, show_hidden)})
            return
        entries = list_dir(target, show_hidden)
        up_link = ''
        if target != PARENT_ROOT:
            up_link = f"<a class='ghost-btn' href='/browse/{html.escape(rel_from_parent(target.parent))}'>Up</a>"
        rows = []
        if target != PARENT_ROOT:
            parent_rel = rel_from_parent(target.parent)
            parent_href = '/browse/' + parent_rel
            rows.append(f'''
<tr data-name=".." data-kind="up">
  <td></td>
  <td class="icon-cell">📁</td>
  <td class="name-cell"><a href="{html.escape(parent_href)}">../</a></td>
  <td class="size-cell">—</td>
  <td>—</td>
  <td>—</td>
  <td class="actions-cell"></td>
</tr>''')
        for e in entries:
            href = '/browse/' + e['relpath']
            actions = []
            if not e['is_dir']:
                actions.append(f"<a class='row-action' href='/download/{html.escape(e['relpath'])}'>⬇</a>")
            actions.append(f"<button class='row-action js-rename' data-path='{html.escape(e['relpath'])}' data-name='{html.escape(e['name'])}'>✏</button>")
            actions.append(f"<button class='row-action danger js-delete-one' data-path='{html.escape(e['relpath'])}' data-name='{html.escape(e['name'])}'>🗑</button>")
            rows.append(f'''
<tr data-name="{html.escape(e['name'])}" data-kind="{'dir' if e['is_dir'] else 'file'}">
  <td><input type="checkbox" class="row-check" value="{html.escape(e['relpath'])}"></td>
  <td class="icon-cell">{e['icon']}</td>
  <td class="name-cell"><a href="{html.escape(href)}">{html.escape(e['name'])}{'/' if e['is_dir'] else ''}</a></td>
  <td class="size-cell">{html.escape(e['size_display'])}</td>
  <td>{html.escape(e['created_display'])}</td>
  <td>{html.escape(e['modified_display'])}</td>
  <td class="actions-cell">{''.join(actions)}</td>
</tr>''')
        content = self.render_layout('Browse', f'''
<section class="toolbar desktop-toolbar">
  <div class="toolbar-group">
    <button id="new-folder-btn" class="primary-btn" type="button">New Folder</button>
    <button id="new-file-btn" class="primary-btn" type="button">New File</button>
    <button id="upload-btn" class="secondary-btn" type="button">Upload File</button>
    {up_link}
    <button id="delete-selected" class="danger-btn" type="button" disabled>Delete Selected</button>
    <button id="rename-selected" class="secondary-btn" type="button" disabled>Rename</button>
    <button id="move-selected" class="secondary-btn" type="button" disabled>Move to...</button>
    <button id="copy-selected" class="secondary-btn" type="button" disabled>Copy to...</button>
  </div>
  <div class="toolbar-group right-tools">
    <label class="checkbox-label"><input type="checkbox" id="show-dotfiles" {'checked' if show_hidden else ''}> Show dotfiles</label>
    <a href="/shortcuts" class="ghost-btn">?</a>
  </div>
</section>
<section class="mobile-controls mobile-only">
  <div class="mobile-breadcrumb-tools">
    {up_link}
    <button id="mobile-search-toggle" class="secondary-btn" type="button">Search</button>
    <button id="mobile-overflow" class="secondary-btn" type="button">More</button>
  </div>
</section>
<section class="filter-panel" id="filter-panel">
  <div class="filter-wrap">
    <span class="filter-icon">🔍</span>
    <input id="filter-input" class="mono" type="text" placeholder="Filter by name (regex)…">
    <button id="clear-filter" class="icon-btn" type="button" hidden>✕</button>
  </div>
  <div id="filter-error" class="form-error" hidden>Invalid regex</div>
</section>
<section id="flash-area"></section>
<section class="table-panel desktop-only">
  <table class="file-table">
    <thead>
      <tr>
        <th><input type="checkbox" id="select-all"></th>
        <th></th>
        <th>Name</th>
        <th>Size</th>
        <th>Created</th>
        <th>Modified</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows) or '<tr><td colspan="7" class="empty-state">This folder is empty.</td></tr>'}
    </tbody>
  </table>
</section>
<section class="mobile-list mobile-only" id="mobile-list">
  {''.join(self.mobile_cards(target, entries)) or '<div class="empty-state card">This folder is empty.</div>'}
</section>
<footer class="status-bar"><span id="status-text">{len(entries)} items</span><a href="/shortcuts">[?] Shortcuts</a></footer>
<input id="file-input" type="file" multiple hidden>
{self.modal_shell()}
''', target)
        self.send_html(content)

    def mobile_cards(self, current: Path, entries):
        cards = []
        if current != PARENT_ROOT:
            parent_rel = rel_from_parent(current.parent)
            parent_href = '/browse/' + parent_rel
            cards.append(f'''
<div class="file-card" data-name="..">
  <div></div>
  <div class="file-card-icon">📁</div>
  <div class="file-card-body">
    <a class="file-card-name" href="{html.escape(parent_href)}">../</a>
    <div class="file-card-meta">Parent folder</div>
  </div>
</div>
''')
        for e in entries:
            href = '/browse/' + e['relpath']
            cards.append(f'''
<div class="file-card" data-name="{html.escape(e['name'])}">
  <label class="file-card-select"><input type="checkbox" class="row-check" value="{html.escape(e['relpath'])}"></label>
  <div class="file-card-icon">{e['icon']}</div>
  <div class="file-card-body">
    <a class="file-card-name" href="{html.escape(href)}">{html.escape(e['name'])}{'/' if e['is_dir'] else ''}</a>
    <div class="file-card-meta">Modified: {html.escape(e['modified_display'])}</div>
    <div class="file-card-meta">{html.escape(e['size_display'])}</div>
  </div>
</div>
''')
        return cards

    def render_file_view(self, target: Path, query):
        suffix = target.suffix.lower()
        stat = target.stat()
        rel = rel_from_parent(target)
        can_edit = is_readable_text(target) and stat.st_size <= MAX_EDIT_SIZE
        saved_banner = '<div class="banner success">Saved successfully.</div>' if query.get('saved', ['0'])[-1] == '1' else ''
        info = f"Size: {fmt_size(stat.st_size)} | Modified: {fmt_dt(stat.st_mtime)}"
        content_html = ''
        if suffix in IMAGE_EXTENSIONS:
            content_html = f"<div class='image-viewer'><img src='/download/{html.escape(rel)}' alt='{html.escape(target.name)}'></div>"
        elif stat.st_size > MAX_EDIT_SIZE:
            content_html = f"<div class='banner danger'>File is too large to display ({fmt_size(stat.st_size)}). <a href='/download/{html.escape(rel)}'>Download instead</a>.</div>"
        elif stat.st_size > WARN_SIZE and query.get('load', ['0'])[-1] != '1':
            content_html = f"<div class='banner warning'>This file is {fmt_size(stat.st_size)}. Loading large files may slow your browser. <a href='/browse/{html.escape(rel)}?load=1'>Load Anyway</a></div>"
        else:
            try:
                text = target.read_text('utf-8', errors='replace')
                lines = text.splitlines() or ['']
                rendered = []
                for idx, line in enumerate(lines, start=1):
                    rendered.append(f"<div class='code-line'><span class='ln'>{idx}</span><span class='lc'>{html.escape(line)}</span></div>")
                content_html = f"<div id='viewer-pre' class='viewer-pre'>{''.join(rendered)}</div><textarea id='viewer-raw' hidden>{html.escape(text)}</textarea>"
            except Exception as exc:
                content_html = f"<div class='banner danger'>Unable to read file: {html.escape(str(exc))}</div>"
                can_edit = False
        edit_href = f"/edit/{rel}" if can_edit else '#'
        viewer = self.render_layout(target.name, f'''
<section class="viewer-header">
  <div><a class="ghost-btn" href="/browse/{html.escape(rel_from_parent(target.parent))}">← Back</a></div>
  <div class="viewer-title mono">{html.escape(rel)}</div>
  <div class="viewer-actions">
    <a class="primary-btn {'disabled-link' if not can_edit else ''}" href="{html.escape(edit_href)}" {'aria-disabled="true"' if not can_edit else ''}>Edit</a>
    <a class="secondary-btn" href="/download/{html.escape(rel)}">Download</a>
    <button class="secondary-btn js-rename" data-path="{html.escape(rel)}" data-name="{html.escape(target.name)}">Rename</button>
    <button class="danger-btn js-delete-one" data-path="{html.escape(rel)}" data-name="{html.escape(target.name)}">Delete</button>
    <button class="secondary-btn" id="copy-file-btn" type="button">Copy</button>
    <button class="secondary-btn" id="toggle-wrap-btn" type="button">Wrap</button>
    <button class="secondary-btn" id="toggle-lines-btn" type="button">Line #</button>
  </div>
</section>
<div class="info-bar">{html.escape(info)}</div>
{saved_banner}
<section class="viewer-content">{content_html}</section>
{self.modal_shell()}
''', target)
        self.send_html(viewer)

    def handle_edit(self, relpath: str):
        target = self.get_target_path(relpath)
        if target is None:
            return
        if not target.exists():
            self.send_text('Not found', 404)
            return
        if not target.is_file():
            self.send_text('Not a file', 400)
            return
        stat = target.stat()
        if stat.st_size > MAX_EDIT_SIZE or not is_readable_text(target):
            self.send_text('File is read-only or too large to edit', 400)
            return
        try:
            text = target.read_text('utf-8', errors='replace')
        except Exception as exc:
            self.send_text(f'Unable to read file: {exc}', 500)
            return
        rel = rel_from_parent(target)
        page = self.render_layout('Edit', f'''
<section class="editor-header">
  <a class="ghost-btn" href="/browse/{html.escape(rel)}">← Cancel</a>
  <div class="viewer-title mono">Editing: {html.escape(rel)}</div>
  <div class="viewer-actions">
    <button id="save-btn" class="primary-btn" type="button">Save</button>
    <button id="toggle-diff-btn" class="secondary-btn" type="button">Show Changes</button>
    <button id="toggle-wrap-btn" class="secondary-btn" type="button">Wrap</button>
    <button id="toggle-lines-btn" class="secondary-btn" type="button">Line #</button>
    <a class="secondary-btn" href="/shortcuts">Shortcuts</a>
  </div>
</section>
<div id="draft-banner" class="banner warning" hidden></div>
<div id="save-error" class="banner danger" hidden></div>
<section class="editor-shell">
  <div class="editor-grid">
    <pre id="editor-lines" class="editor-lines mono" aria-hidden="true">1</pre>
    <textarea id="editor" class="editor-text mono" data-save-url="/save/{html.escape(rel)}">{html.escape(text)}</textarea>
  </div>
</section>
<section id="diff-panel" class="diff-panel" hidden></section>
<textarea id="original-content" hidden>{html.escape(text)}</textarea>
{self.modal_shell()}
''', target)
        self.send_html(page)

    def handle_download(self, relpath: str):
        target = self.get_target_path(relpath)
        if target is None:
            return
        if not target.exists() or not target.is_file():
            self.send_text('Not found', 404)
            return
        data = target.read_bytes()
        ctype = mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Disposition', f'attachment; filename="{target.name}"')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_save(self, relpath: str):
        target = self.get_target_path(relpath)
        if target is None:
            return
        if not target.exists() or not target.is_file():
            self.send_text('Not found', 404)
            return
        length = int(self.headers.get('Content-Length', '0') or '0')
        raw = self.rfile.read(length).decode('utf-8', errors='replace')
        data = urllib.parse.parse_qs(raw)
        content = data.get('content', [''])[-1]
        try:
            atomic_write_text_preserving_metadata(target, content)
        except OSError as exc:
            self.send_json({'error': str(exc)}, 409)
            return
        self.redirect('/browse/' + rel_from_parent(target) + '?saved=1')

    def handle_delete(self):
        try:
            payload = self.read_body_json()
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
            return
        paths = payload.get('paths') or []
        deleted = []
        failed = []
        for rel in paths:
            try:
                target = safe_join(rel)
                if not target.exists():
                    failed.append({'path': rel, 'error': 'Not found', 'status': 404})
                    continue
                if target.is_dir():
                    if any(target.iterdir()):
                        failed.append({'path': rel, 'error': 'Directory is not empty.', 'status': 400})
                        continue
                    target.rmdir()
                else:
                    target.unlink()
                deleted.append(rel)
            except PermissionError:
                failed.append({'path': rel, 'error': 'Forbidden', 'status': 403})
            except Exception as exc:
                failed.append({'path': rel, 'error': str(exc), 'status': 500})
        status = 200 if not failed else (failed[0]['status'] if not deleted and len(failed) == 1 else 207)
        self.send_json({'deleted': deleted, 'failed': failed}, status)

    def handle_rename(self):
        try:
            payload = self.read_body_json()
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
            return
        rel = payload.get('path', '')
        new_name = payload.get('new_name', '')
        if not new_name or '/' in new_name or '\x00' in new_name:
            self.send_json({'error': 'Invalid name'}, 400)
            return
        try:
            target = safe_join(rel)
        except ValueError:
            self.send_json({'error': 'Invalid path'}, 400)
            return
        except PermissionError:
            self.send_json({'error': 'Forbidden'}, 403)
            return
        if not target.exists():
            self.send_json({'error': 'Not found'}, 404)
            return
        new_path = target.with_name(new_name)
        try:
            new_path.relative_to(PARENT_ROOT)
        except ValueError:
            self.send_json({'error': 'Forbidden'}, 403)
            return
        if new_path.exists():
            self.send_json({'error': 'Target exists'}, 409)
            return
        target.rename(new_path)
        self.send_json({'ok': True, 'path': rel_from_parent(new_path)})

    def handle_new_file(self):
        try:
            payload = self.read_body_json()
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
            return
        directory_rel = payload.get('dir', 'workspace')
        filename = payload.get('filename', '')
        if not filename or '/' in filename or '\x00' in filename:
            self.send_json({'error': 'Invalid filename'}, 400)
            return
        try:
            directory = safe_join(directory_rel)
        except ValueError:
            self.send_json({'error': 'Invalid path'}, 400)
            return
        except PermissionError:
            self.send_json({'error': 'Forbidden'}, 403)
            return
        if not directory.exists() or not directory.is_dir():
            self.send_json({'error': 'Parent missing'}, 404)
            return
        target = directory / filename
        if target.exists():
            self.send_json({'error': 'Already exists'}, 409)
            return
        target.write_text('', encoding='utf-8')
        self.send_json({'ok': True, 'path': rel_from_parent(target)})

    def handle_new_folder(self):
        try:
            payload = self.read_body_json()
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
            return
        directory_rel = payload.get('dir', 'workspace')
        folder_name = payload.get('folder', '')
        if not folder_name or '/' in folder_name or '\x00' in folder_name:
            self.send_json({'error': 'Invalid folder name'}, 400)
            return
        try:
            directory = safe_join(directory_rel)
        except ValueError:
            self.send_json({'error': 'Invalid path'}, 400)
            return
        except PermissionError:
            self.send_json({'error': 'Forbidden'}, 403)
            return
        if not directory.exists() or not directory.is_dir():
            self.send_json({'error': 'Parent missing'}, 404)
            return
        target = directory / folder_name
        if target.exists():
            self.send_json({'error': 'Already exists'}, 409)
            return
        target.mkdir()
        self.send_json({'ok': True, 'path': rel_from_parent(target)})

    def handle_upload(self):
        parsed = self.parsed()
        query = urllib.parse.parse_qs(parsed.query)
        directory_rel = query.get('dir', ['workspace'])[-1]
        try:
            directory = safe_join(directory_rel)
        except ValueError:
            self.send_json({'error': 'Invalid path'}, 400)
            return
        except PermissionError:
            self.send_json({'error': 'Forbidden'}, 403)
            return
        if not directory.exists() or not directory.is_dir():
            self.send_json({'error': 'Target directory missing'}, 404)
            return
        length = int(self.headers.get('Content-Length', '0') or '0')
        body = self.rfile.read(length)
        try:
            files = parse_multipart(self.headers, body)
        except ValueError as exc:
            self.send_json({'error': str(exc)}, 400)
            return
        if not files:
            self.send_json({'error': 'No files uploaded'}, 400)
            return
        uploaded = []
        failed = []
        for filename, payload in files:
            name = os.path.basename(filename or '')
            if not name:
                failed.append({'file': '', 'error': 'Missing filename', 'status': 400})
                continue
            target = directory / name
            if target.exists():
                failed.append({'file': name, 'error': 'Target exists', 'status': 409})
                continue
            fd, tmp_name = tempfile.mkstemp(prefix=name + '.', suffix='.upload', dir=str(directory))
            with os.fdopen(fd, 'wb') as tmp:
                tmp.write(payload)
            os.replace(tmp_name, target)
            uploaded.append(name)
        status = 200 if not failed else 207
        self.send_json({'uploaded': uploaded, 'failed': failed}, status)

    def handle_batch_copy_move(self, move: bool):
        try:
            payload = self.read_body_json()
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
            return
        paths = payload.get('paths') or []
        dest_rel = payload.get('destination', '')
        try:
            destination = safe_join(dest_rel)
        except ValueError:
            self.send_json({'error': 'Invalid path'}, 400)
            return
        except PermissionError:
            self.send_json({'error': 'Forbidden'}, 403)
            return
        if not destination.exists() or not destination.is_dir():
            self.send_json({'error': 'Destination missing'}, 404)
            return
        done = []
        failed = []
        for rel in paths:
            try:
                source = safe_join(rel)
                if not source.exists():
                    failed.append({'path': rel, 'error': 'Not found'})
                    continue
                target = destination / source.name
                if target.exists():
                    failed.append({'path': rel, 'error': 'Target exists'})
                    continue
                if source.is_dir():
                    if move:
                        shutil.move(str(source), str(target))
                    else:
                        shutil.copytree(source, target)
                else:
                    if move:
                        shutil.move(str(source), str(target))
                    else:
                        shutil.copy2(source, target)
                done.append(rel)
            except PermissionError:
                failed.append({'path': rel, 'error': 'Forbidden'})
            except Exception as exc:
                failed.append({'path': rel, 'error': str(exc)})
        self.send_json({'done': done, 'failed': failed}, 200 if not failed else 207)

    def handle_shortcuts(self):
        page = self.render_layout('Shortcuts', '''
<section class="shortcuts-hero">
  <div>
    <h1>Keyboard Shortcuts</h1>
    <p>Quick navigation and editing shortcuts for the file browser.</p>
  </div>
  <a class="primary-btn" href="/browse/workspace">Back to browser</a>
</section>
<section class="shortcuts-grid">
  <div class="shortcut-card"><div class="shortcut-group-title">Global</div><ul><li><kbd>?</kbd><span>Open shortcuts page</span></li></ul></div>
  <div class="shortcut-card"><div class="shortcut-group-title">Browser</div><ul><li><kbd>/</kbd><span>Focus regex filter</span></li><li><kbd>n</kbd><span>New file</span></li><li><kbd>a</kbd><span>Select all / deselect all</span></li><li><kbd>Del</kbd><span>Delete selected</span></li><li><kbd>Esc</kbd><span>Clear filter / close modal</span></li><li><kbd>Backspace</kbd> <kbd>u</kbd><span>Go up / back</span></li></ul></div>
  <div class="shortcut-card"><div class="shortcut-group-title">Viewer</div><ul><li><kbd>e</kbd><span>Edit current file</span></li><li><kbd>d</kbd><span>Download current file</span></li></ul></div>
  <div class="shortcut-card"><div class="shortcut-group-title">Editor</div><ul><li><kbd>Ctrl/Cmd</kbd> + <kbd>S</kbd><span>Save</span></li><li><kbd>Ctrl/Cmd</kbd> + <kbd>D</kbd><span>Toggle diff preview</span></li><li><kbd>Esc</kbd><span>Close modal</span></li></ul></div>
</section>
<section class="table-panel shortcuts-table-panel">
  <table class="file-table shortcuts-table">
    <thead><tr><th>Key</th><th>Action</th><th>Context</th></tr></thead>
    <tbody>
      <tr><td><kbd>?</kbd></td><td>Open shortcuts page</td><td>Global</td></tr>
      <tr><td><kbd>e</kbd></td><td>Edit current file</td><td>Viewer</td></tr>
      <tr><td><kbd>d</kbd></td><td>Download current file</td><td>Viewer</td></tr>
      <tr><td><kbd>Backspace</kbd> / <kbd>u</kbd></td><td>Go up / back</td><td>Browser, Viewer</td></tr>
      <tr><td><kbd>n</kbd></td><td>New file</td><td>Browser</td></tr>
      <tr><td><kbd>Del</kbd></td><td>Delete selected</td><td>Browser</td></tr>
      <tr><td><kbd>/</kbd></td><td>Focus regex filter</td><td>Browser</td></tr>
      <tr><td><kbd>Escape</kbd></td><td>Clear filter / close modal</td><td>Browser</td></tr>
      <tr><td><kbd>a</kbd></td><td>Select all / deselect all</td><td>Browser</td></tr>
      <tr><td><kbd>Ctrl/Cmd+S</kbd></td><td>Save</td><td>Editor</td></tr>
      <tr><td><kbd>Ctrl/Cmd+D</kbd></td><td>Toggle diff preview</td><td>Editor</td></tr>
    </tbody>
  </table>
</section>
''', WORKSPACE_ROOT)
        self.send_html(page)

    def modal_shell(self):
        return '''
<div id="modal" class="modal" hidden>
  <div class="modal-backdrop" data-close-modal="1"></div>
  <div class="modal-card">
    <div class="modal-header"><h2 id="modal-title">Action</h2><button class="icon-btn" data-close-modal="1">✕</button></div>
    <div id="modal-body" class="modal-body"></div>
  </div>
</div>
'''


def build_parser():
    parser = argparse.ArgumentParser(description='OpenClaw file browser')
    parser.add_argument('--port', type=int, default=80)
    return parser


def run_server(port: int):
    httpd = ThreadingHTTPServer(('0.0.0.0', port), FileBrowserHandler)
    print(f'Serving OpenClaw file browser on http://0.0.0.0:{port}', flush=True)
    httpd.serve_forever()


if __name__ == '__main__':
    args = build_parser().parse_args()
    run_server(args.port)
