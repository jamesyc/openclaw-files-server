import os
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from http.server import ThreadingHTTPServer

import server


class TempDirFixture:
    def __init__(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.parent = self.base / '.openclaw'
        self.workspace = self.parent / 'workspace'

    def __enter__(self):
        self.workspace.mkdir(parents=True)
        (self.workspace / 'alpha').mkdir()
        (self.workspace / 'emptydir').mkdir()
        (self.workspace / '.secret').write_text('hidden')
        (self.workspace / 'hello.txt').write_text('hello world')
        (self.workspace / 'alpha' / 'nested.md').write_text('# nested')
        return self

    def __exit__(self, exc_type, exc, tb):
        self.tempdir.cleanup()


class LiveServer:
    def __init__(self):
        self.httpd = None
        self.thread = None
        self.port = None
        self.host = '127.0.0.1'

    def __enter__(self):
        start_port = int(os.environ.get('TEST_HTTP_PORT_START', '18080'))
        bind_last_error = None
        for port in range(start_port, start_port + 100):
            try:
                self.httpd = ThreadingHTTPServer((self.host, port), server.FileBrowserHandler)
                self.port = port
                break
            except OSError as exc:
                bind_last_error = exc
                continue
        if self.httpd is None:
            raise RuntimeError(
                f'Unable to bind test server on {self.host}:{start_port}-{start_port + 99}'
            ) from bind_last_error
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.05)
        return self

    def __exit__(self, exc_type, exc, tb):
        self.httpd.shutdown()
        self.thread.join(timeout=2)
        self.httpd.server_close()

    def url(self, path):
        return f'http://{self.host}:{self.port}{path}'

    def get(self, path):
        return urllib.request.urlopen(self.url(path))

    def request(self, method, path, body=None, headers=None):
        req = urllib.request.Request(self.url(path), data=body, headers=headers or {}, method=method)
        return urllib.request.urlopen(req)


class ServerTestCase(unittest.TestCase):
    def setUp(self):
        self.fixture = TempDirFixture().__enter__()
        self.patches = [
            mock.patch.object(server, 'PARENT_ROOT', self.fixture.parent.resolve()),
            mock.patch.object(server, 'WORKSPACE_ROOT', self.fixture.workspace.resolve()),
        ]
        for patch in self.patches:
            patch.start()
        self.live = LiveServer().__enter__()

    def tearDown(self):
        self.live.__exit__(None, None, None)
        for patch in reversed(self.patches):
            patch.stop()
        self.fixture.__exit__(None, None, None)
