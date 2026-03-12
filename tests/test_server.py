import json
import unittest
import urllib.error
import urllib.parse
from http.client import HTTPConnection
from unittest import mock

import server
from tests.support import ServerTestCase


class TestPathValidation(ServerTestCase):
    def test_valid_path_within_workspace(self):
        path = server.safe_join('workspace/hello.txt')
        self.assertEqual(path, (self.fixture.workspace / 'hello.txt').resolve())

    def test_valid_path_parent_root(self):
        path = server.safe_join('workspace/../workspace')
        self.assertEqual(path, self.fixture.workspace.resolve())

    def test_path_traversal_blocked(self):
        with self.assertRaises(PermissionError):
            server.safe_join('../../etc/passwd')

    def test_null_byte_in_path_blocked(self):
        with self.assertRaises(ValueError):
            server.safe_join('workspace/bad\x00file')


class TestBrowser(ServerTestCase):
    def test_root_redirect(self):
        conn = HTTPConnection(self.live.host, self.live.port)
        conn.request('GET', '/')
        res = conn.getresponse()
        self.assertEqual(res.status, 302)
        self.assertEqual(res.getheader('Location'), '/browse/workspace')

    def test_browse_root_lists_dirs_and_files(self):
        body = self.live.get('/browse/workspace').read().decode()
        self.assertIn('alpha/', body)
        self.assertIn('hello.txt', body)

    def test_breadcrumb_includes_parent_root_link(self):
        body = self.live.get('/browse/workspace/alpha').read().decode()
        self.assertIn("<a href='/browse/'>.openclaw</a> / <a href='/browse/workspace'>workspace</a> / <strong>alpha</strong>", body)

    def test_breadcrumb_marks_parent_root_current_at_parent_root(self):
        body = self.live.get('/browse/').read().decode()
        self.assertIn("<nav class=\"breadcrumb\"><strong>.openclaw</strong></nav>", body)

    def test_browse_dotfiles_hidden_by_default(self):
        body = self.live.get('/browse/workspace').read().decode()
        self.assertNotIn('.secret', body)

    def test_browse_dotfiles_shown_when_toggled(self):
        body = self.live.get('/browse/workspace?show_hidden=1').read().decode()
        self.assertIn('.secret', body)

    def test_browse_nonexistent_dir(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.live.get('/browse/workspace/nope')
        self.assertEqual(cm.exception.code, 404)


class TestViewer(ServerTestCase):
    def test_view_text_file(self):
        body = self.live.get('/browse/workspace/hello.txt').read().decode()
        self.assertIn('hello world', body)
        self.assertIn('<pre', body)

    def test_view_nonexistent_file(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.live.get('/browse/workspace/missing.txt')
        self.assertEqual(cm.exception.code, 404)

    def test_view_large_file_warning(self):
        big = self.fixture.workspace / 'big.txt'
        big.write_text('a' * (server.WARN_SIZE + 1))
        body = self.live.get('/browse/workspace/big.txt').read().decode()
        self.assertIn('Loading large files may slow your browser', body)


class TestEditor(ServerTestCase):
    def test_edit_page_loads_with_content(self):
        body = self.live.get('/edit/workspace/hello.txt').read().decode()
        self.assertIn('<textarea id="editor"', body)
        self.assertIn('hello world', body)

    def test_save_writes_file(self):
        body = urllib.parse.urlencode({'content': 'updated text'}).encode()
        conn = HTTPConnection(self.live.host, self.live.port)
        conn.request('POST', '/save/workspace/hello.txt', body=body, headers={'Content-Type': 'application/x-www-form-urlencoded'})
        res = conn.getresponse()
        self.assertEqual(res.status, 302)
        self.assertEqual((self.fixture.workspace / 'hello.txt').read_text(), 'updated text')

    def test_save_path_traversal_blocked(self):
        body = urllib.parse.urlencode({'content': 'x'}).encode()
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.live.request('POST', '/save/../../etc/passwd', body=body, headers={'Content-Type': 'application/x-www-form-urlencoded'})
        self.assertEqual(cm.exception.code, 403)

    def test_atomic_write_restores_owner_when_running_as_root(self):
        target = self.fixture.workspace / 'hello.txt'
        target.chmod(0o644)
        stat_result = target.stat()
        with mock.patch.object(server.os, 'geteuid', return_value=0), \
                mock.patch.object(server.os, 'chown') as mock_chown:
            server.atomic_write_text_preserving_metadata(target, 'updated text')

        mock_chown.assert_called_once()
        args = mock_chown.call_args.args
        self.assertEqual(args[1:], (stat_result.st_uid, stat_result.st_gid))
        self.assertEqual(target.stat().st_mode & 0o777, stat_result.st_mode & 0o777)
        self.assertEqual(target.read_text(), 'updated text')


class TestDelete(ServerTestCase):
    def test_delete_single_file(self):
        res = self.live.request('POST', '/delete', body=json.dumps({'paths': ['workspace/hello.txt']}).encode(), headers={'Content-Type': 'application/json'})
        data = json.loads(res.read())
        self.assertEqual(data['deleted'], ['workspace/hello.txt'])
        self.assertFalse((self.fixture.workspace / 'hello.txt').exists())

    def test_delete_empty_directory(self):
        res = self.live.request('POST', '/delete', body=json.dumps({'paths': ['workspace/emptydir']}).encode(), headers={'Content-Type': 'application/json'})
        data = json.loads(res.read())
        self.assertEqual(data['deleted'], ['workspace/emptydir'])

    def test_delete_nonempty_directory_blocked(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.live.request('POST', '/delete', body=json.dumps({'paths': ['workspace/alpha']}).encode(), headers={'Content-Type': 'application/json'})
        self.assertEqual(cm.exception.code, 400)


class TestRename(ServerTestCase):
    def test_rename_file(self):
        res = self.live.request('POST', '/rename', body=json.dumps({'path': 'workspace/hello.txt', 'new_name': 'renamed.txt'}).encode(), headers={'Content-Type': 'application/json'})
        data = json.loads(res.read())
        self.assertTrue(data['ok'])
        self.assertTrue((self.fixture.workspace / 'renamed.txt').exists())

    def test_rename_target_exists(self):
        (self.fixture.workspace / 'existing.txt').write_text('x')
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.live.request('POST', '/rename', body=json.dumps({'path': 'workspace/hello.txt', 'new_name': 'existing.txt'}).encode(), headers={'Content-Type': 'application/json'})
        self.assertEqual(cm.exception.code, 409)


class TestNewFile(ServerTestCase):
    def test_create_blank_file(self):
        res = self.live.request('POST', '/new-file', body=json.dumps({'dir': 'workspace', 'filename': 'blank.md'}).encode(), headers={'Content-Type': 'application/json'})
        data = json.loads(res.read())
        self.assertEqual(data['path'], 'workspace/blank.md')
        self.assertTrue((self.fixture.workspace / 'blank.md').exists())
        self.assertEqual((self.fixture.workspace / 'blank.md').read_text(), '')

    def test_create_file_already_exists(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.live.request('POST', '/new-file', body=json.dumps({'dir': 'workspace', 'filename': 'hello.txt'}).encode(), headers={'Content-Type': 'application/json'})
        self.assertEqual(cm.exception.code, 409)


class TestNewFolder(ServerTestCase):
    def test_create_folder(self):
        res = self.live.request('POST', '/new-folder', body=json.dumps({'dir': 'workspace', 'folder': 'docs'}).encode(), headers={'Content-Type': 'application/json'})
        data = json.loads(res.read())
        self.assertEqual(data['path'], 'workspace/docs')
        self.assertTrue((self.fixture.workspace / 'docs').is_dir())

    def test_create_folder_already_exists(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.live.request('POST', '/new-folder', body=json.dumps({'dir': 'workspace', 'folder': 'alpha'}).encode(), headers={'Content-Type': 'application/json'})
        self.assertEqual(cm.exception.code, 409)


if __name__ == '__main__':
    unittest.main()
