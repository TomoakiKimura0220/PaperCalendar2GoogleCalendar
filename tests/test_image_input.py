import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from image_input import pasted_image_bytes

class PasteTests(unittest.TestCase):
    def test_png_conversion(self):
        raw=pasted_image_bytes(Image.new('RGBA',(30,20),'white'))
        self.assertEqual(Image.open(io.BytesIO(raw)).size,(30,20))

    def test_size_limit(self):
        with self.assertRaises(ValueError):
            pasted_image_bytes(SimpleNamespace(width=10000,height=10000))

    @patch('grid_detection.detect_grid', return_value=[[.03,.08],[.97,.08],[.97,.96],[.03,.96]])
    @patch('key_store.load_key', return_value='')
    @patch('streamlit_paste_button.paste_image_button')
    def test_paste_preview_and_clear(self, paste, load, detect):
        from pathlib import Path
        from streamlit.testing.v1 import AppTest
        paste.return_value=SimpleNamespace(image_data=Image.new('RGB',(700,500),'white'))
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'), default_timeout=30).run()
        app.radio[0].set_value('クリップボードから貼り付け').run()
        self.assertFalse(app.exception)
        self.assertTrue(any(b.label=='画像を解析' for b in app.button))
        paste.return_value=SimpleNamespace(image_data=None)
        next(b for b in app.button if b.label=='貼り付けた画像をクリア').click().run()
        self.assertFalse(app.exception)
        self.assertFalse(any(b.label=='画像を解析' for b in app.button))
