import time,unittest
from unittest.mock import Mock,patch
from aster.google import Gmail
from aster.core import AppError,ApiError
class ServiceQuotaTests(unittest.TestCase):
 def test_gmail_pause_allows_calendar(self):
  graph=Gmail(Mock());graph.auth.access_token.return_value="synthetic-test-token";graph.backoff_until=time.time()+600
  response=Mock(ok=True,status_code=200,content=b'{}');response.json.return_value={'items':[]}
  with patch('aster.google.requests.request',return_value=response) as request:
   self.assertEqual(graph.api('GET','calendars/primary/events',service='calendar'),{'items':[]})
   request.assert_called_once()
   with self.assertRaises(AppError):graph.api('GET','messages')
   request.assert_called_once()
 def test_calendar_quota_does_not_pause_gmail(self):
  graph=Gmail(Mock());graph.auth.access_token.return_value="synthetic-test-token";response=Mock(ok=False,status_code=429,headers={'Retry-After':'60'});response.json.return_value={'error':{'message':'quota','errors':[]}}
  with patch('aster.google.requests.request',return_value=response):
   with self.assertRaises(ApiError):graph.api('GET','calendars/primary/events',service='calendar')
  self.assertEqual(graph.backoff_until,0);self.assertGreater(graph.service_backoffs['calendar'],time.time())
