import server
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


class TestStaticUiRegressions(ServerTestCase):
    def test_code_views_share_css_font_metrics(self):
        css = (server.STATIC_DIR / 'style.css').read_text()
        self.assertIn('--code-font-family:', css)
        self.assertIn('--code-font-size:', css)
        self.assertIn('--code-line-height:', css)
        self.assertIn('.ln, .lc {', css)
        self.assertIn('display: block;', css)
        self.assertIn('font-family: inherit;', css)
        self.assertIn('line-height: inherit;', css)
        self.assertIn('-webkit-text-size-adjust: 100%;', css)
        self.assertIn('text-size-adjust: 100%;', css)

    def test_editor_wrap_measurement_uses_rendered_character_widths(self):
        js = (server.STATIC_DIR / 'app.js').read_text()
        self.assertIn('const measureWrappedRows = (text, usableWidth) => {', js)
        self.assertIn("width = wrapMeasureContext.measureText(char).width;", js)
        self.assertNotIn("const charWidth = ctx.measureText('M').width || 8;", js)
