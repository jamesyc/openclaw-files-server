# OpenClaw File Browser — Design Doc

## Purpose

A lightweight Python web server running on port 80 that lets you browse, view, and edit files under `~/.openclaw` from any device on the local network (desktop or mobile) via a browser.

---

## Folder Structure (Option B)

```
server.py           # HTTP handler, routing, file system operations, HTML template rendering
static/
  style.css         # all styling — desktop + mobile responsive, dark mode
  app.js            # all client-side JS — sort, filter, shortcuts, modals, diff, localStorage
tests/
  test_server.py    # unit tests
docs/
  DESIGN.md         # this file
  TESTS.md          # test case listing
README.md           # setup and run instructions
```

`server.py` is at the repo root so `python3 server.py` is the obvious entry point. `static/` sits right next to it. Tests and docs are in subdirectories but easy to find. `README.md` at root is rendered automatically by GitHub.

---

## Stack

- **Python 3** — stdlib only (`http.server`, `urllib`, `os`, `shutil`, `json`)
- **Frontend:** CSS + vanilla JS, no frameworks; served from `static/`
- **No build step**, no npm, no pip installs

### Runtime Configuration

- Optional header dashboard link: set `OPENCLAW_DASHBOARD_URL` in `.env` at the repo root
- When `OPENCLAW_DASHBOARD_URL` is present, the header shows a `Dashboard` button that opens that URL in a new tab
- When `OPENCLAW_DASHBOARD_URL` is missing or blank, the `Dashboard` button is hidden

---

## Root & Navigation

- **Default root:** `/Users/james/.openclaw/workspace`
- Users can navigate **one level up** to `/Users/james/.openclaw` (parent), but not above it
- Directory listings should include a visible `../` folder-style entry at the top whenever the current directory is not the parent root, so users have an obvious "go up" affordance without needing toolbar buttons or keyboard shortcuts
- Attempts to traverse above the parent return 403

---

## Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Redirect to `/browse/` |
| GET | `/browse/<relpath>` | List directory or display file viewer |
| GET | `/edit/<relpath>` | Show edit form |
| GET | `/download/<relpath>` | Download file as attachment |
| GET | `/shortcuts` | Keyboard shortcuts reference page |
| POST | `/save/<relpath>` | Save edited file contents |
| POST | `/delete` | Delete selected files/folders (JSON body: list of relpaths) |
| POST | `/rename` | Rename a file or folder |
| POST | `/new-file` | Create a blank file |
| POST | `/upload` | Upload one or more files into the current directory |
| POST | `/move` | Move selected files to a target directory |
| POST | `/copy` | Copy selected files to a target directory |
| GET | `/static/<filename>` | Serve CSS/JS static assets |

---

## Design System

### Color Palette

**Light mode:**
- Background: `#f8f9fa`
- Surface (cards, panels): `#ffffff`
- Border: `#dee2e6`
- Text primary: `#212529`
- Text secondary: `#6c757d`
- Accent (links, active): `#0d6efd`
- Danger (delete): `#dc3545`
- Warning: `#ffc107`
- Success: `#198754`
- Hover row: `#f1f3f5`
- Selected row: `#e7f1ff`

**Dark mode** (toggled via class on `<body>`, persisted in localStorage):
- Background: `#1a1a2e`
- Surface: `#16213e`
- Border: `#2d3561`
- Text primary: `#e0e0e0`
- Text secondary: `#9e9e9e`
- Accent: `#4e9af1`
- Danger: `#e05c65`
- Hover row: `#1e2a45`
- Selected row: `#1a3a6e`

### Typography
- Body: system-ui, -apple-system, sans-serif; 14px base on desktop, 16px on mobile (avoids iOS zoom on inputs)
- Monospace (viewer, editor, filter input): `'JetBrains Mono', 'Fira Code', 'Cascadia Code', Consolas, monospace`; 13px on desktop, 14px on mobile
- Breadcrumb: 14px, medium weight
- Column headers: 12px uppercase, letter-spacing 0.05em, medium weight
- File names in table: 14px, normal weight
- Toolbar buttons: 13px

### Spacing
- Base unit: 4px
- Page padding desktop: 24px horizontal, 16px vertical
- Page padding mobile: 12px horizontal, 8px vertical
- Table cell padding: 8px 12px desktop, 10px 8px mobile
- Toolbar gap between buttons: 6px
- Modal padding: 24px desktop, 16px mobile

### Shadows & Borders
- Cards/panels: `box-shadow: 0 1px 3px rgba(0,0,0,0.08)`
- Modals: `box-shadow: 0 8px 32px rgba(0,0,0,0.18)`
- Border radius: 6px for buttons and inputs, 8px for modals and panels
- Table: no outer border; use `border-bottom` on each row

---

## Desktop UI (≥ 1024px)

### Global Layout
```
┌──────────────────────────────────────────────────────┐
│  HEADER: logo/title | breadcrumb         dark mode ☀ │
├──────────────────────────────────────────────────────┤
│  TOOLBAR: [New File] [Delete] [Rename] [Move] [Copy] │
│           [Show dotfiles ☐]                          │
├──────────────────────────────────────────────────────┤
│  FILTER: [🔍 Regex filter________________]           │
├──────────────────────────────────────────────────────┤
│  TABLE (full columns, see below)                     │
│  ...                                                 │
│  ...                                                 │
├──────────────────────────────────────────────────────┤
│  STATUS BAR: 42 items | 3 selected        [?shortcuts]│
└──────────────────────────────────────────────────────┘
```

### Header (desktop)
- Height: 52px; sticky at top
- Left: app name "OpenClaw Files" in bold, 16px
- Center: breadcrumb (see below)
- Right: optional `Dashboard` button when configured, plus dark mode toggle button (sun/moon icon, 32×32px)
- Background: surface color, bottom border

### Breadcrumb (desktop)
- Segments separated by `/` chevron
- Each segment is a clickable link (underline on hover)
- Current segment not a link, shown in bold
- Overflow: if total width exceeds ~600px, collapse middle segments into `…` with a dropdown showing full path
- Examples:
  - `.openclaw / workspace / ProjectSleep`
  - `.openclaw / workspace / … / subfolder / deep`

### Toolbar (desktop)
- Single row, height 44px, sits below header
- Left group: action buttons (New File, Upload File, Delete Selected, Rename, Move to, Copy to)
- Right group: Show dotfiles toggle, keyboard shortcut hint `[?]`
- Buttons:
  - **New File**: primary style (accent background), always enabled
  - **Upload File**: secondary style; opens file picker and uploads into the current directory
  - **Delete Selected**: danger style (red), disabled + grayed when 0 selected
  - **Rename**: secondary style, disabled when 0 or 2+ selected
  - **Move to...**: secondary style, disabled when 0 selected
  - **Copy to...**: secondary style, disabled when 0 selected
- Button anatomy: icon (16px) + label text, 8px gap, 10px 14px padding, 6px border radius
- Disabled state: 40% opacity, `cursor: not-allowed`
- Upload behavior: native file picker with support for single or multi-select; after upload, show a success/error banner and refresh the listing

### Regex Filter (desktop)
- Full-width input below toolbar, 38px tall
- Placeholder: "Filter by name (regex)…"
- Left icon: 🔍 (search icon)
- Right: clear ✕ button (visible only when non-empty)
- On invalid regex: border turns red, small error text below: "Invalid regex"
- Matches are highlighted in the Name column (bold or background highlight)

### File Table (desktop)
- Sticky header row with column labels
- When not already at the parent root, the first row in the listing should be a synthetic `../` folder entry that navigates up one level; it has no checkbox, no inline actions, and no file metadata
- Columns (left to right):
  1. Checkbox (24px wide) — "select all" in header
  2. Icon (24px) — folder icon or file icon or image thumbnail (28×28px, object-fit: cover) for image files
  3. **Name** — sortable; link styled (accent color, no underline until hover); appends `/` to folder names
  4. **Size** — sortable; right-aligned; human-readable (B, KB, MB); folders show "—"
  5. **Created** — sortable; `YYYY-MM-DD HH:mm`
  6. **Modified** — sortable; `YYYY-MM-DD HH:mm`
  7. Actions (96px) — icon buttons: ⬇ Download (files only), ✏ Rename, 🗑 Delete; shown on row hover only on desktop (always shown on mobile)
- Sort indicator in header: ▲ / ▼ next to active column label
- Alternating row background: subtle (2% lightness shift), even rows slightly darker
- Row hover: `#f1f3f5` (light) / `#1e2a45` (dark)
- Selected rows: `#e7f1ff` (light) / `#1a3a6e` (dark)
- Folders shown first regardless of sort column; within folders, alphabetical is secondary sort
- Row height: 40px

### Status Bar (desktop)
- Bottom of page, below table
- Left: "42 items" or "42 items, 3 selected"
- Right: keyboard shortcut hint "[?] Shortcuts"
- Height: 32px, text-secondary color, 12px font

---

## Mobile UI (≤ 767px)

### Breakpoints
- `≤ 767px`: Mobile layout (phones)
- `768px – 1023px`: Tablet layout (iPad) — same as mobile but wider gutters, Actions column visible
- `≥ 1024px`: Desktop layout

### Global Layout (mobile)
```
┌──────────────────────┐
│ HEADER: title | ☀ 🔍 │  (compact, 48px)
├──────────────────────┤
│ BREADCRUMB (2 lines) │
├──────────────────────┤
│ FILE LIST (cards)    │
│ ┌──────────────────┐ │
│ │ 📁 workspace     │ │
│ │ Modified: ...    │ │
│ └──────────────────┘ │
│ ...                  │
├──────────────────────┤
│ BOTTOM ACTION BAR    │
│ [+New][Del][More...] │
└──────────────────────┘
```

### Header (mobile)
- Height: 48px, sticky
- Left: app name "OpenClaw Files" (14px, bold)
- Right: dark mode toggle + search icon (taps to expand filter bar below header)
- No breadcrumb in header — breadcrumb is a separate row below

### Breadcrumb (mobile)
- Shown as a scrollable horizontal strip below the header (not in header)
- Segments separated by `>`, scroll horizontally if overflow
- Last 2 segments always visible; earlier ones truncated left with `…`
- Height: 36px, background slightly different from page background for visual separation

### Filter (mobile)
- Hidden by default; tapping the search icon in the header slides it open below the header (animated, ~200ms)
- Same behavior as desktop (regex, invalid state, clear button)
- Height: 44px (larger tap target)

### File List (mobile)
- **Card-based layout** instead of table rows — each item is a card
- When not already at the parent root, the first card in the list should be a synthetic `../` folder entry labeled as the parent folder so going up is obvious on touch devices too
- Card anatomy:
  ```
  ┌─────────────────────────────────────┐
  │ ☐  [icon/thumbnail]  Name           │
  │                      Modified: date │
  │                      Size (files)   │
  └─────────────────────────────────────┘
  ```
- Card height: ~64px for files/folders with text, ~80px for image thumbnails
- Tap on card name → navigate (folder) or view (file)
- Tap on checkbox → select
- Long-press on card → select (same as tapping checkbox)
- Swipe right on card → reveals quick-action buttons (Delete, Rename) — optional enhancement
- Image thumbnails: 44×44px, rounded 4px, object-fit: cover
- No Actions column — actions accessible via bottom bar when selected, or via swipe

### Bottom Action Bar (mobile)
- Fixed at bottom of screen, height 56px
- Hidden when nothing selected; slides up when ≥1 item selected
- Contains: **Delete** (danger), **Rename** (only if 1 selected), **Move**, **Copy**
- Item count shown: "3 selected"
- "New File" button always visible as a floating action button (FAB) — bottom-right corner, 56×56px circle, accent color, `+` icon
- FAB hides when bottom action bar is visible (they don't overlap)

### Toolbar / Overflow (mobile)
- No separate always-visible toolbar row
- The mobile header has an overflow `...` menu containing every action that does not fit comfortably in the main chrome
- **Nothing is desktop-only**: all features remain available on mobile through the overflow menu, bottom sheets, full-screen modals, or the selection action bar
- Overflow menu items:
  - New File
  - Upload File
  - Sort by...
  - Show dotfiles
  - Toggle dark mode
  - Toggle word wrap
  - Toggle line numbers
  - Shortcuts
  - Download current file (viewer)
  - Rename current file (viewer)
  - Delete current file (viewer)
  - Move / Copy current selection (browser)
- Dark mode toggle may still appear as a dedicated icon, but it is also duplicated inside the overflow menu for discoverability

### Sort (mobile)
- Accessed via a "Sort by..." button in the header overflow menu (`...`)
- Opens a bottom sheet with sort options (Name, Size, Created, Modified) and direction toggle
- Same sort model as desktop; persisted in localStorage

### Upload (mobile)
- Accessible from the overflow menu as **Upload File**
- Opens the native mobile file picker (`<input type="file">`) with optional multiple selection
- On iPhone/iPad this should allow Files picker, photos, and camera sources when the browser supports them
- Upload target is always the current directory being viewed
- Progress is shown as a simple inline spinner / "Uploading..." banner; after completion, show success/failure banner and refresh listing

### Modals (mobile)
- All modals are full-screen (100vw × 100vh) with slide-up animation
- Header bar: title on left, ✕ close button on right (44×44px tap target)
- Content scrollable
- Confirm dialogs use the native `confirm()` JS dialog or a full-screen modal (not a small centered box)

---

## Shared UI — File Viewer

### Desktop viewer layout
```
┌─────────────────────────────────────────────────┐
│ ← Back  |  path/to/file.md                      │
│ [Edit] [Download] [Rename] [Delete]  [Copy📋][⇔Wrap]│
├─────────────────────────────────────────────────┤
│ INFO BAR: Size: 4.2 KB | Modified: 2026-03-11   │
├─────────────────────────────────────────────────┤
│  1 │ # Hello World                              │
│  2 │                                            │
│  3 │ Some content here                          │
│ .. │ ...                                        │
└─────────────────────────────────────────────────┘
```

### Mobile viewer layout
- Back arrow + filename in sticky header
- Primary action icons may show Edit and Download directly when space allows; all viewer actions are also available in the `...` overflow menu
- Info bar collapses to a single tappable row that expands to show details
- Line numbers are available on mobile via the overflow menu toggle; off by default to save space
- Word wrap ON by default on mobile (small screens need it), but fully toggleable
- Full-width `<pre>` with horizontal scroll if wrap is off
- Rename, Delete, Copy to clipboard, Download, word wrap, line numbers, and shortcuts are all reachable on mobile without losing any desktop functionality

### Common viewer behavior
- **Line numbers:** `<span class="ln">N</span>` alongside each line, right-aligned, text-secondary color, fixed width; toggled via CSS class on `<pre>`
- **Word wrap:** toggle via CSS `white-space: pre-wrap` vs `pre`; state in localStorage
- **Copy to clipboard:** button copies full file content; shows "Copied!" for 1.5s then reverts
- **Read-only:** Edit button is disabled and visually grayed; if user taps/clicks it, a browser `alert()` popup says "This file is read-only."
- **Large file warning (>1MB):** yellow banner replaces content: "This file is [X] MB. Loading large files may slow your browser. [Load Anyway]". Content not rendered until confirmed.
- **Very large file (>10MB):** red banner: "File is too large to display ([X] MB). [Download instead]". No textarea.
- **Image files:** `<img src="/download/<relpath>">` rendered instead of `<pre>`. Max width 100%. Download button shown. No Edit button.

---

## Shared UI — File Editor

### Desktop editor layout
```
┌──────────────────────────────────────────────────────┐
│ ← Cancel  |  Editing: path/to/file.md               │
│ [Save ⌘S]  [Show Changes ⌘D]  [⇔ Wrap]              │
├──────────────────────────────────────────────────────┤
│ DRAFT BANNER (if draft exists):                      │
│ "Unsaved draft from 10:34 PM. [Restore] [Discard]"   │
├───────┬──────────────────────────────────────────────┤
│  1    │                                              │
│  2    │  <textarea — full height minus header>       │
│  3    │                                              │
│  ..   │                                              │
├───────┴──────────────────────────────────────────────┤
│ DIFF PANEL (hidden by default, toggles open below)   │
│  - / old line                                        │
│  + new line                                          │
└──────────────────────────────────────────────────────┘
```

### Mobile editor layout
- Full-screen: header (48px) + textarea (fills remaining height) + fixed bottom bar
- Fixed bottom bar (48px): **[Save]** (full-width primary button) | **[Cancel]** (secondary)
- "Show Changes", wrap toggle, line number toggle, and shortcuts all live in the header `...` overflow menu
- Keyboard auto-focuses textarea; browser's native keyboard pushes the bottom bar up (using `env(safe-area-inset-bottom)`)
- Draft banner appears below header as a dismissible strip
- Diff preview is fully available on mobile as a full-screen sheet or expandable panel, not desktop-only

### Common editor behavior
- **Atomic save:** POST to `/save/<relpath>`, server writes to `.tmp` then renames
- **On save success:** redirect to `/browse/<relpath>` with `?saved=1` query param; viewer shows green banner "Saved successfully."
- **On save error:** inline error banner above textarea; textarea content preserved
- **Draft auto-save:** debounced 5s after last keystroke; stored as `draft:<relpath>` in localStorage with timestamp
- **Draft discard:** removes localStorage key
- **Line numbers:** a dedicated gutter sits beside the textarea and is synced via JS; when word wrap is off it shows one number per logical line, and when word wrap is on wrapped continuations stay visually aligned under the same logical line number instead of getting new numbers
- **Word wrap interaction:** line number rendering must recompute on input, resize, and wrap-toggle changes so the gutter stays aligned with the editor's visual layout
- **Diff panel:** client-side unified diff (implement a minimal LCS diff in `app.js`, no library needed for basic line-level diff); shows removed lines in red background, added lines in green background

---

## Shared UI — Modals

### New File modal
```
┌───────────────────────────────┐
│ New File                   ✕ │
├───────────────────────────────┤
│ Filename:                     │
│ [____________________________]│
│ (in: /workspace/subfolder)    │
├───────────────────────────────┤
│           [Cancel] [Create]   │
└───────────────────────────────┘
```
- Input auto-focused on open
- Enter key submits; Escape closes
- Validation: no `/` or null bytes; not empty; shows inline error if name conflicts

### Rename modal
- Same layout; pre-filled with current name; full text selected on open

### Upload modal / picker
- Desktop: clicking **Upload File** opens the native file picker immediately; selected files POST as `multipart/form-data` to `/upload`
- Mobile: the same control opens the native iOS picker in a full-screen browser-native sheet
- If multiple files are selected, the UI shows `Uploading 3 files...` and then a result banner such as `Uploaded 2 files, 1 failed`
- Name collision behavior: default is **no overwrite**; if a filename already exists, upload for that file fails with 409 and is shown in the result list

### Move/Copy modal
```
┌──────────────────────────────────────┐
│ Move 3 items to...               ✕  │
├──────────────────────────────────────┤
│ Destination:                         │
│ [/workspace/____________________]    │
│ [Browse folders ▼]                   │
│                                      │
│ ▼ Browse panel (collapsible)         │
│   📁 ProjectSleep                    │
│   📁 reminders                       │
│   📁 notes                           │
├──────────────────────────────────────┤
│ Moving: file1.md, file2.md, +1 more  │
├──────────────────────────────────────┤
│              [Cancel] [Move here]    │
└──────────────────────────────────────┘
```
- Browse panel loads directory listing via `/browse/<path>?json=1` (server returns JSON when `json` query param present)
- Clicking a folder in the browse panel sets the destination input

### Delete confirm
- Uses native `window.confirm()` dialog:
  - Single: "Delete 'filename.md'? This cannot be undone."
  - Multiple: "Delete 3 items? This cannot be undone."
- No custom modal for delete (native confirm is faster to implement and harder to accidentally bypass)

---

## Feature Parity: Desktop vs Mobile

There should be **no desktop-only features**. Mobile must expose the full feature set; the only difference is presentation.

- Desktop uses visible toolbars, table headers, hover affordances, and wider inline layouts
- Mobile uses overflow menus, bottom sheets, full-screen modals, bottom action bars, and card layouts
- If a feature is available on desktop, it must also be reachable on mobile in no more than two taps from the relevant screen
- Hover-only affordances on desktop must always have a tap-accessible equivalent on mobile

Examples:
- **Upload**: desktop toolbar button; mobile overflow menu
- **Sort**: desktop table headers; mobile bottom sheet from overflow menu
- **Delete / Rename / Move / Copy**: desktop toolbar or row actions; mobile selection bar + overflow menu
- **Download / Copy to clipboard / Wrap / Line numbers / Diff preview / Shortcuts**: desktop visible buttons where space allows; mobile overflow menu or full-screen panel

## Keyboard Shortcuts

| Key | Action | Context |
|-----|--------|---------|
| `?` | Open shortcuts page | Global |
| `e` | Edit current file | Viewer |
| `d` | Download current file | Viewer |
| `Backspace` / `u` | Go up / back | Browser, Viewer |
| `n` | New file | Browser |
| `Del` | Delete selected (with confirm) | Browser |
| `/` | Focus regex filter | Browser |
| `Escape` | Clear filter / close modal | Browser |
| `a` | Select all / deselect all | Browser |
| `Ctrl/Cmd+S` | Save | Editor |
| `Escape` | Cancel edit, go back to viewer | Editor |
| `Ctrl/Cmd+D` | Toggle diff preview | Editor |

Shortcuts are disabled when focus is inside `<input>` or `<textarea>` (except `Ctrl/Cmd+S` in editor). On mobile, the `/shortcuts` page remains fully accessible from the overflow menu even though hardware keyboard usage is less common.

---

## LocalStorage Keys

| Key | Type | What it stores |
|-----|------|----------------|
| `sort_col` | string | Active sort column (`name`, `size`, `created`, `modified`) |
| `sort_dir` | string | `asc` or `desc` |
| `show_dotfiles` | bool string | `"true"` / `"false"` |
| `dark_mode` | bool string | `"true"` / `"false"` |
| `word_wrap` | bool string | `"true"` / `"false"` |
| `draft:<relpath>` | JSON | `{ "content": "...", "savedAt": "<ISO timestamp>" }` |

---

## Error Handling

### Path errors
- **403** if path escapes allowed root; **404** if path does not exist

### Read errors
- Permission / I/O error: inline error banner in viewer; nav intact

### Write / Save
- Atomic write via `.tmp` → rename; on failure: **409** JSON `{"error":"<reason>"}`, editor preserves content

### Delete
- Confirm dialog always shown first (JS, before any network request)
- Single: 404 or 500; batch: partial-success JSON `{"deleted":[...],"failed":[{"path":...,"error":...}]}`
- Non-empty directory: **400** "Directory is not empty."

### Rename / Move / Copy
- Target exists: **409**; source missing: **404**; invalid chars: **400**; outside root: **403**
- Would overwrite: **409** (no silent overwrite)
- Partial batch: JSON list of successes and failures

### Upload
- Empty upload body or malformed multipart request: **400**
- Target directory missing: **404**
- Uploaded filename collides with existing file: **409** for that file, with partial-success JSON for multi-file uploads
- Path escapes allowed root: **403**
- Uploaded file written atomically via temp file + rename where practical

### New File
- Already exists: **409**; invalid filename: **400**; parent missing: **404**

### General
- **500** plain-text message; traceback to stderr only (not exposed to browser)

---

## Large File Handling

- `WARN_SIZE = 1 * 1024 * 1024` (1 MB) — show warning banner, require click to load
- `MAX_EDIT_SIZE = 10 * 1024 * 1024` (10 MB) — refuse editor, show download link
- Both constants defined at top of `server.py` for easy adjustment

---

## Running

```bash
sudo python3 server.py
# Dev mode (no sudo needed above port 1024):
python3 server.py --port 8080
```

Binds to `0.0.0.0`. Optional `--port` flag (default: 80).

---

## Non-Goals

- No authentication
- No syntax highlighting
- No markdown rendering
- No non-empty directory deletion
- No server-side session or persistent state
