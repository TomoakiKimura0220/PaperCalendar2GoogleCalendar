import unittest
from unittest.mock import MagicMock, patch
from google.genai.errors import ServerError, ClientError
from recognition import generate_with_retry

class RetryTests(unittest.TestCase):
    @patch('time.sleep')
    def test_recovers(self, sleep):
        client = MagicMock()
        client.models.generate_content.side_effect = [ServerError(503,{'error':{'message':'busy'}}),'ok']
        self.assertEqual(generate_with_retry(client,'m',[],None),'ok')
        sleep.assert_called_once_with(5)

    @patch('time.sleep')
    def test_bounded(self,sleep):
        client=MagicMock()
        client.models.generate_content.side_effect=ServerError(503,{'error':{'message':'busy'}})
        with self.assertRaises(ServerError): generate_with_retry(client,'m',[],None)
        self.assertEqual(client.models.generate_content.call_count,3)

    @patch('time.sleep')
    def test_no_retry_bad_key(self,sleep):
        client=MagicMock()
        client.models.generate_content.side_effect=ClientError(400,{'error':{'message':'bad'}})
        with self.assertRaises(ClientError): generate_with_retry(client,'m',[],None)
        sleep.assert_not_called()
