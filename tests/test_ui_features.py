from tests.support import ServerTestCase


class TestBrowseUi(ServerTestCase):
    def test_workspace_page_has_new_folder_button(self):
        body = self.live.get('/browse/workspace').read().decode()
        self.assertIn('id="new-folder-btn"', body)

    def test_workspace_page_has_upload_button(self):
        body = self.live.get('/browse/workspace').read().decode()
        self.assertIn('id="upload-btn"', body)

    def test_workspace_page_includes_parent_shortcut(self):
        body = self.live.get('/browse/workspace').read().decode()
        self.assertIn('>../</a>', body)

    def test_parent_root_page_hides_parent_shortcut(self):
        body = self.live.get('/browse/').read().decode()
        self.assertNotIn('>../</a>', body)


class TestEditorUi(ServerTestCase):
    def test_edit_page_has_line_number_toggle(self):
        body = self.live.get('/edit/workspace/hello.txt').read().decode()
        self.assertIn('id="toggle-lines-btn"', body)

    def test_edit_page_has_line_number_gutter(self):
        body = self.live.get('/edit/workspace/hello.txt').read().decode()
        self.assertIn('id="editor-lines"', body)
