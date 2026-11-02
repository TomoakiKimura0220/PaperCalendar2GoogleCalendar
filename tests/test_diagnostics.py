import unittest
from google.genai.errors import ClientError
from diagnostics import recognition_error

class DiagnosticsTests(unittest.TestCase):
    def test_quota(self):
        error = ClientError(429, {'error': {'message': 'Quota exceeded', 'status': 'RESOURCE_EXHAUSTED'}})
        self.assertIn('利用枠', recognition_error(error))
        self.assertIn('Quota exceeded', recognition_error(error))

    def test_secret_redaction(self):
        key = 'AIzaSensitiveExample123'
        error = ClientError(400, {'error': {'message': f'Invalid key {key} https://example.com?key={key}', 'status': 'INVALID_ARGUMENT'}})
        result = recognition_error(error,key)
        self.assertNotIn(key,result)
        self.assertNotIn('https://',result)

    def test_unknown_exception_hides_request(self):
        self.assertNotIn('secret',recognition_error(RuntimeError('secret')))

    def test_unicode_error_does_not_expose_key(self):
        err = UnicodeEncodeError('ascii','secret日本語',6,9,'invalid')
        result = recognition_error(err)
        self.assertNotIn('secret',result)
        self.assertIn('文字コード',result)

    def test_settings_validation(self):
        from recognition import validate_api_settings
        self.assertEqual(validate_api_settings('  fake-key\n','gemini-3.8-flash '),('fake-key','gemini-3.8-flash'))
        for key, model in [('キー名','gemini-3.8-flash'),('fake key','gemini-3.8-flash'),('fake-key','ｇemini')]:
            with self.assertRaises(ValueError): validate_api_settings(key,model)
