"""Pure calendar logic; no network calls."""
import calendar
import hashlib
import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Tokyo')


def grid_dates(month, rows):
    first = date.fromisoformat(month + '-01')
    start = first - timedelta(days=(first.weekday() + 1) % 7)
    needed = ((first.weekday() + 1) % 7 + calendar.monthrange(first.year, first.month)[1] + 6) // 7
    if rows < needed:
        raise ValueError(f'この月は少なくとも{needed}行必要です')
    return [start + timedelta(days=i) for i in range(rows * 7)]


def normalize(value):
    return ''.join(unicodedata.normalize('NFKC', value).casefold().split())


def event_body(row):
    title = str(row.get('title', '')).strip()
    if not title:
        raise ValueError('予定名を入力してください')
    day = date.fromisoformat(str(row['date']))
    # Missing key keeps older single-day JSON compatible; blank means unresolved range.
    last_text = row.get('end_date', day.isoformat())
    if not last_text:
        raise ValueError('最終日を入力して期間を確定してください')
    last = date.fromisoformat(str(last_text))
    if last < day:
        raise ValueError('最終日は開始日以降にしてください')
    start = str(row.get('start', '') or '').strip()
    end = str(row.get('end', '') or '').strip()
    body = {'summary': title}
    if not start:
        if end:
            raise ValueError('終了時刻だけの予定は登録できません')
        body.update(start={'date': day.isoformat()}, end={'date': (last + timedelta(days=1)).isoformat()})
    else:
        if last != day:
            raise ValueError('複数日予定は終日で登録してください。時刻付きはGoogle側で手動登録してください')
        for t in (start, end):
            if t and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', t):
                raise ValueError('時刻はHH:MMで入力してください')
        begin = datetime.fromisoformat(f'{day}T{start}').replace(tzinfo=TZ)
        finish = datetime.fromisoformat(f'{day}T{end}').replace(tzinfo=TZ) if end else begin + timedelta(hours=1)
        if finish <= begin:
            raise ValueError('終了時刻は開始時刻より後にしてください。日またぎは初版では手動登録してください')
        body.update(start={'dateTime': begin.isoformat(), 'timeZone': str(TZ)}, end={'dateTime': finish.isoformat(), 'timeZone': str(TZ)})
    return body


def start_key(event):
    start = event['start']
    if 'date' in start:
        return start['date']
    return datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00')).astimezone(TZ).isoformat()


def end_key(event):
    return start_key({'start': event['end']}) if event.get('end') else None


def event_day(event):
    return start_key(event)[:10]


def event_id(body):
    # Google accepts lowercase base32hex; hex is a valid subset.
    data = [normalize(body['summary']), start_key(body)]
    return 'pc' + hashlib.sha256(json.dumps(data, ensure_ascii=False).encode()).hexdigest()[:40]


def conflicts(body, existing):
    same_day = [e for e in existing if e.get('status') != 'cancelled' and e.get('start') and event_day(e) == event_day(body)]
    exact = [e for e in same_day if normalize(e.get('summary', '')) == normalize(body['summary']) and start_key(e) == start_key(body) and end_key(e) == end_key(body)]
    possible = [e for e in same_day if e not in exact and (normalize(e.get('summary', '')) == normalize(body['summary']) or start_key(e) == start_key(body))]
    return exact, possible


def month_overview(month, records):
    first = date.fromisoformat(month + '-01')
    result = []
    for n in range(1, calendar.monthrange(first.year, first.month)[1] + 1):
        day = first.replace(day=n).isoformat()
        titles = [r['title'] for r in records if r.get('date', '') <= day <= (r.get('end_date') or r.get('date', ''))]
        result.append({'日付': day, '抽出結果': ' / '.join(titles) if titles else '予定の抽出なし（画像で確認）'})
    return result
