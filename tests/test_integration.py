import io
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image
from recognition import prepare, DEFAULT_LAYOUT
from core import event_body
import google_calendar as gc



class IntegrationTests(unittest.TestCase):
    def test_fixed_grid_crop(self):
        buf = io.BytesIO()
        Image.new('RGB',(1174,904),'white').save(buf,format='PNG')
        preview, crops, days = prepare(buf.getvalue(),DEFAULT_LAYOUT,'2026-11')
        self.assertEqual(len(crops),35)
        self.assertEqual(str(days[9]),'2026-11-10')
        self.assertGreater(crops[0].width,150)

    def test_pagination(self):
        service = MagicMock()
        service.events.return_value.list.return_value.execute.side_effect = [{'items':[{'id':'a'}], 'nextPageToken':'next'}, {'items':[{'id':'b'}]}]
        bodies = [event_body({'title':'x','date':'2026-11-10'})]
        self.assertEqual(len(gc.existing_events(service,'primary',bodies)),2)
        self.assertEqual(service.events.return_value.list.call_args.kwargs['pageToken'],'next')

    def test_repeated_import_and_batch_duplicate(self):
        service = MagicMock()
        service.events.return_value.list.return_value.execute.return_value = {'items':[]}
        service.events.return_value.insert.return_value.execute.return_value = {'id':'created'}
        body = event_body({'title':'x','date':'2026-11-10'})
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            try:
                os.chdir(d)
                result = gc.publish(service,'primary',[body, body])
                self.assertEqual(result[0]['status'],'登録完了')
                self.assertIn('スキップ',result[1]['status'])
                self.assertEqual(service.events.return_value.insert.call_count,1)
                service.events.return_value.list.return_value.execute.return_value = {'items':[body]}
                self.assertIn('スキップ',gc.publish(service,'primary',[body])[0]['status'])
            finally: os.chdir(old)

    def test_conflict_after_uncertain_network_result(self):
        from googleapiclient.errors import HttpError
        from httplib2 import Response
        service = MagicMock()
        service.events.return_value.list.return_value.execute.return_value = {'items':[]}
        service.events.return_value.insert.return_value.execute.side_effect = HttpError(Response({'status':'409'}), b'{}')
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            try:
                os.chdir(d)
                result = gc.publish(service,'primary',[event_body({'title':'x','date':'2026-11-10'})])
                self.assertIn('同一ID',result[0]['status'])
            finally: os.chdir(old)


    def test_app_demo(self):
        from streamlit.testing.v1 import AppTest
        from pathlib import Path
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'), default_timeout=30).run()
        self.assertFalse(app.exception)
        next(b for b in app.button if 'デモ' in b.label).click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('照合' in b.label for b in app.button))

    def test_week_image_preserves_line_across_cells(self):
        from recognition import week_image
        from core import grid_dates
        from PIL import ImageDraw
        original = Image.new('RGB',(707,100),'white')
        ImageDraw.Draw(original).line((0,50,706,50),fill='red',width=3)
        crops = [original.crop((i*101,0,(i+1)*101,100)) for i in range(7)]
        sheet = week_image(crops,0,grid_dates('2026-11',5))
        self.assertEqual(sheet.crop((0,30,707,130)).tobytes(),original.tobytes())


    def test_publish_multiday_payload(self):
        service = MagicMock()
        service.events.return_value.list.return_value.execute.return_value = {'items':[]}
        service.events.return_value.insert.return_value.execute.return_value = {'id':'created'}
        body = event_body({'title':'出張','date':'2026-11-10','end_date':'2026-11-13'})
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            try:
                os.chdir(d)
                gc.publish(service,'primary',[body])
                sent = service.events.return_value.insert.call_args.kwargs['body']
                self.assertEqual(sent['end'],{'date':'2026-11-14'})
            finally: os.chdir(old)
