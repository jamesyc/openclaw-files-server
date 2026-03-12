# Unit Tests — OpenClaw File Browser

Test file: `test_server.py` (uses Python `unittest` + `unittest.mock`)

Run: `python3 -m pytest test_server.py -v` (or `python3 -m unittest test_server -v`)

---

## Test Groups

### 1. Path Validation (`test_path_validation.py` or class `TestPathValidation`)

| Test | Description |
|------|-------------|
| `test_valid_path_within_workspace` | Path inside workspace resolves correctly |
| `test_valid_path_parent_root` | Path inside `~/.openclaw` (one level up) is allowed |
| `test_path_traversal_blocked` | `../../etc/passwd` returns 403 |
| `test_path_above_parent_blocked` | Path escaping `~/.openclaw` returns 403 |
| `test_null_byte_in_path_blocked` | Path containing null byte returns 400 |
| `test_symlink_escape_blocked` | Symlink pointing outside root is blocked |

---

### 2. File Browser (`TestBrowser`)

| Test | Description |
|------|-------------|
| `test_root_redirect` | GET `/` redirects to `/browse/` |
| `test_browse_root_lists_dirs_and_files` | Response contains directory and file names |
| `test_browse_dirs_listed_before_files` | Folders appear before files in listing |
| `test_browse_nonexistent_dir` | Returns 404 |
| `test_browse_dotfiles_hidden_by_default` | Dotfiles not in listing by default |
| `test_browse_dotfiles_shown_when_toggled` | Dotfiles appear with `?show_hidden=1` |
| `test_breadcrumb_links_correct` | Each breadcrumb segment links to correct path |
| `test_up_one_level_from_workspace` | Parent link navigates to `~/.openclaw` |
| `test_no_up_link_at_parent_root` | No up-link shown when at `~/.openclaw` |

---

### 3. File Viewer (`TestViewer`)

| Test | Description |
|------|-------------|
| `test_view_text_file` | File contents appear in `<pre>` block |
| `test_view_nonexistent_file` | Returns 404 |
| `test_view_unreadable_file` | Permission error shows inline error, page still renders |
| `test_view_large_file_warning` | Files over threshold show a size warning |
| `test_view_binary_file` | Binary content displayed as-is (no crash) |

---

### 4. File Editor / Save (`TestEditor`)

| Test | Description |
|------|-------------|
| `test_edit_page_loads_with_content` | Textarea pre-filled with file content |
| `test_save_writes_file` | POST to `/save/` updates file content on disk |
| `test_save_atomic_write` | Uses tmp file + rename; original untouched on failure |
| `test_save_permission_denied` | Returns 409 with error JSON |
| `test_save_disk_full` | Returns 409 with error JSON |
| `test_save_path_traversal_blocked` | Returns 403 |
| `test_save_redirects_to_viewer` | Successful save redirects to `/browse/<path>` |

---

### 5. Delete (`TestDelete`)

| Test | Description |
|------|-------------|
| `test_delete_single_file` | File is removed from disk |
| `test_delete_multiple_files` | All selected files removed |
| `test_delete_empty_directory` | Empty dir is removed |
| `test_delete_nonempty_directory_blocked` | Returns 400 |
| `test_delete_nonexistent_file` | Returns 404 |
| `test_delete_partial_failure_response` | Mixed success/failure returns partial list |
| `test_delete_path_traversal_blocked` | Returns 403 |

---

### 6. Rename (`TestRename`)

| Test | Description |
|------|-------------|
| `test_rename_file` | File is renamed on disk |
| `test_rename_directory` | Directory is renamed on disk |
| `test_rename_target_exists` | Returns 409 |
| `test_rename_source_missing` | Returns 404 |
| `test_rename_invalid_chars_in_name` | Returns 400 (slash, null byte, etc.) |
| `test_rename_path_traversal_blocked` | Returns 403 |

---

### 7. New File (`TestNewFile`)

| Test | Description |
|------|-------------|
| `test_create_blank_file` | File created, exists on disk, empty |
| `test_create_file_already_exists` | Returns 409 |
| `test_create_invalid_filename` | Returns 400 |
| `test_create_in_nonexistent_dir` | Returns 404 |
| `test_create_path_traversal_blocked` | Returns 403 |

---

## Fixtures / Helpers

- `TempDirFixture` — creates a temporary directory tree for each test, patches the server root to point at it; torn down after each test
- `MockClient` — thin wrapper around Python's `http.client` or `urllib` to make test requests against a locally bound test server instance

---

## Running

```bash
# Run all tests
python3 -m pytest test_server.py -v

# Run a specific group
python3 -m pytest test_server.py::TestDelete -v

# Run with coverage (if pytest-cov installed)
python3 -m pytest test_server.py --cov=server --cov-report=term-missing
```
