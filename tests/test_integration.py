import io
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image
from recognition import prepare, DEFAULT_LAYOUT, extract
from core import event_body
import google_calendar as gc

def weekly_response(entries):
    import json, re
    from types import SimpleNamespace
    def respond(**kwargs):
        targets = {int(i) for i in re.findall(r'cell=(\d+)', kwargs['contents'][1])}
        return SimpleNamespace(text=json.dumps({'entries':[e for e in entries if e['cell'] in targets]}))
    return respond


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

    def test_model_results_use_fixed_dates(self):
        from google import genai
        client = MagicMock()
        client.__enter__.return_value = client
        import json
        client.models.generate_content.side_effect = weekly_response(json.loads('{"entries":[{"cell":9,"text":"歯医者14時","title":"歯医者","start":"14:00","end":"","kind":"handwritten","issue":""}]}')["entries"])
        from core import grid_dates
        with patch.object(genai,'Client',return_value=client):
            result = extract([Image.new('RGB',(100,100))]*35,grid_dates('2026-11',5),'2026-11','fake','test')
        self.assertEqual(result[0]['date'],'2026-11-10')
        self.assertFalse(result[0]['selected'])

    @patch("key_store.load_key", return_value="")
    def test_app_demo(self, load_key):
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

    def test_arrow_extraction_and_uncertain_week_crossing(self):
        import json
        from google import genai
        from core import grid_dates
        entries = []
        for cell, last, span in [(8,11,'range'), (13,15,'range'), (20,None,'uncertain')]:
            entries.append(dict(cell=cell,end_cell=last,span=span,text='←出張→',title='出張',start='',end='',kind='handwritten',issue=''))
        client = MagicMock()
        client.__enter__.return_value = client
        client.models.generate_content.side_effect = weekly_response(entries)
        with patch.object(genai,'Client',return_value=client):
            result = extract([Image.new('RGB',(100,100))]*35,grid_dates('2026-11',5),'2026-11','fake','test')
        self.assertEqual(result[0]['date'],'2026-11-09')
        self.assertEqual(result[0]['end_date'],'2026-11-12')
        self.assertEqual(result[1]['end_date'],'')
        self.assertEqual(result[2]['end_date'],'')
        for r in result[1:]:
            with self.assertRaises(ValueError): event_body(r)

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

    def test_every_week_including_last_day_is_requested(self):
        from google import genai
        from core import grid_dates
        for month, rows, last in [('2026-11',5,30),('2026-05',6,31),('2024-02',5,29)]:
            days = grid_dates(month,rows)
            cell = next(i for i,d in enumerate(days) if str(d)==f'{month}-{last}')
            client = MagicMock()
            client.__enter__.return_value = client
            client.models.generate_content.side_effect = weekly_response([dict(cell=cell,text='月末予定',title='月末予定',start='',end='',kind='handwritten',issue='')])
            with patch.object(genai,'Client',return_value=client):
                result=extract([Image.new('RGB',(100,100))]*len(days),days,month,'fake','test')
            self.assertEqual(result[0]['date'],f'{month}-{last}')
            self.assertEqual(client.models.generate_content.call_count,rows)
