import unittest
from unittest.mock import patch
import key_store

class KeyStoreTests(unittest.TestCase):
    @patch('key_store.backend')
    def test_save_load_delete(self, backend):
        backend.return_value.get_password.return_value = 'test-secret'
        key_store.save_key(' test-secret ')
        backend.return_value.set_password.assert_called_once_with(key_store.SERVICE,key_store.ACCOUNT,'test-secret')
        self.assertEqual(key_store.load_key(),'test-secret')
        key_store.delete_key()
        backend.return_value.delete_password.assert_called_once_with(key_store.SERVICE,key_store.ACCOUNT)

    @patch('key_store.backend')
    def test_invalid_not_saved(self, backend):
        with self.assertRaises(ValueError): key_store.save_key('日本語')
        backend.assert_not_called()

    @patch('key_store.backend', side_effect=RuntimeError('denied'))
    def test_no_fallback(self, backend):
        with self.assertRaises(RuntimeError): key_store.save_key('test-secret')

    @patch('key_store.load_key',return_value='stored-secret')
    @patch('key_store.save_key')
    @patch('key_store.delete_key')
    def test_ui_never_prefills_saved_key(self, delete, save, load):
        from streamlit.testing.v1 import AppTest
        from pathlib import Path
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertFalse(any('Gemini' in f.label for f in app.text_input))
        load.assert_not_called()
        save.assert_not_called()
        delete.assert_not_called()
