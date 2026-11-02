import unittest
from core import grid_dates, event_body, event_id, conflicts

class CoreTests(unittest.TestCase):
    def test_month_boundaries(self):
        dates = grid_dates('2026-11', 5)
        self.assertEqual(str(dates[0]), '2026-11-01')
        self.assertEqual(str(dates[34]), '2026-12-05')
        self.assertEqual(str(grid_dates('2024-02', 5)[32]), '2024-02-29')

    def test_six_week_month(self):
        with self.assertRaises(ValueError): grid_dates('2026-05', 5)
        self.assertEqual(str(grid_dates('2026-05', 6)[0]), '2026-04-26')

    def test_all_day_exclusive_end(self):
        body = event_body({'title':'予定', 'date':'2026-12-31'})
        self.assertEqual(body['end']['date'], '2027-01-01')

    def test_default_duration_across_midnight(self):
        b = event_body({'title':'予定', 'date':'2026-11-30', 'start':'23:30'})
        self.assertEqual(b['end']['dateTime'], '2026-12-01T00:30:00+09:00')

    def test_bad_inputs(self):
        for row in [{'title':'', 'date':'2026-11-01'}, {'title':'x','date':'2026-02-30'}, {'title':'x','date':'2026-11-01','start':'24:00'}, {'title':'x','date':'2026-11-01','end':'12:00'}, {'title':'x','date':'2026-11-01','start':'14:00','end':'13:00'}]:
            with self.assertRaises(ValueError): event_body(row)

    def test_timezone_and_normalization(self):
        b = event_body({'title':'Ａ 会議','date':'2026-11-10','start':'14:00'})
        old = {'summary':'a会議', 'start':{'dateTime':'2026-11-10T05:00:00Z'}, 'end':{'dateTime':'2026-11-10T06:00:00Z'}}
        self.assertEqual(len(conflicts(b,[old])[0]), 1)
        self.assertEqual(event_id(b), event_id(old))

    def test_possible_collision(self):
        a = event_body({'title':'歯医者','date':'2026-11-10','start':'14:00'})
        b = event_body({'title':'歯医者','date':'2026-11-10','start':'15:00'})
        self.assertEqual(len(conflicts(a,[b])[1]), 1)

    def test_multiday_inclusive_last_date(self):
        b = event_body({'title':'出張','date':'2026-11-29','end_date':'2026-12-02'})
        self.assertEqual(b['start'], {'date':'2026-11-29'})
        self.assertEqual(b['end'], {'date':'2026-12-03'})

    def test_unresolved_reversed_or_timed_range(self):
        for row in [dict(end_date=''), dict(end_date='2026-11-09'), dict(end_date='2026-11-12', start='14:00')]:
            with self.assertRaises(ValueError):
                event_body({'title':'出張','date':'2026-11-10', **row})

    def test_changed_duration_is_possible_duplicate(self):
        a = event_body({'title':'出張','date':'2026-11-10','end_date':'2026-11-12'})
        b = event_body({'title':'出張','date':'2026-11-10','end_date':'2026-11-13'})
        self.assertEqual(conflicts(a,[b]), ([],[b]))
        self.assertEqual(conflicts(a,[a]), ([a],[]))
        self.assertEqual(event_id(a), event_id(b))  # Preserve retry identity; never silently add changed duration.

    def test_overview_all_month_lengths(self):
        from core import month_overview
        for month, count in [('2026-11',30),('2026-12',31),('2026-02',28),('2024-02',29)]:
            rows = month_overview(month, [])
            self.assertEqual(len(rows),count)
            self.assertEqual(rows[-1]['日付'],f'{month}-{count}')
