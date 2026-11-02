import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from core import grid_dates
from local_recognition import records_from_words, parse_text, extract

class LocalTests(unittest.TestCase):
    def test_times(self):
        self.assertEqual(parse_text('会議 １３：００〜１５：００'), ('会議','13:00','15:00'))
        self.assertEqual(parse_text('面談14時30分'), ('面談','14:30',''))
        self.assertEqual(parse_text('A 10:00 B 15:00')[1:], ('',''))

    def test_month_end_and_adjacent_month(self):
        for month in ['2026-11','2026-02','2028-02','2026-08']:
            days=grid_dates(month,6)
            crops=[Image.new('RGB',(100,100)) for d in days]
            words=[SimpleNamespace(content='予定', points=[[i%7*100+20,i//7*100+40],[i%7*100+60,i//7*100+60]]) for i in range(42)]
            records=records_from_words(words,crops,days,month)
            expected=[d.isoformat() for d in days if d.isoformat().startswith(month)]
            self.assertEqual([r['date'] for r in records],expected)
            self.assertTrue(all(not r['selected'] for r in records))

    @patch('local_recognition.engine')
    def test_local_engine_receives_grid(self, engine):
        engine.return_value.return_value=(SimpleNamespace(words=[]),None)
        crops=[Image.new('RGB',(100,100)) for _ in range(35)]
        self.assertEqual(extract(crops,grid_dates('2026-11',5),'2026-11',detailed=False),[])
        self.assertEqual(engine.return_value.call_args.args[0].shape,(500,700,3))

    @patch('local_recognition.engine')
    def test_detail_includes_blank_month_end(self, engine):
        word=SimpleNamespace(content='面談', rec_score=.9, points=[[60,120],[180,180]])
        engine.return_value.side_effect=[(SimpleNamespace(words=[]),None)]+[(SimpleNamespace(words=[word]),None)]*30
        crops=[Image.new('RGB',(100,100)) for _ in range(35)]
        rows=extract(crops,grid_dates('2026-11',5),'2026-11')
        self.assertEqual(len(rows),30)
        self.assertEqual(rows[-1]['date'],'2026-11-30')
        self.assertFalse(any(r['selected'] for r in rows))

    def test_detail_retains_confident_original(self):
        from local_recognition import detail_words
        from unittest.mock import Mock
        word=SimpleNamespace(content='会議',rec_score=.99,points=[[20,40],[60,60]])
        ocr=Mock(return_value=(SimpleNamespace(words=[]),None))
        crops=[Image.new('RGB',(100,100)) for _ in range(35)]
        words, alternatives=detail_words(ocr,crops,grid_dates('2026-11',5),'2026-11',[word])
        self.assertIn(word,words)
        self.assertNotIn(0,alternatives)
        self.assertEqual(ocr.call_count,29)
