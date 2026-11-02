import json
import os
from pathlib import Path
from datetime import date, datetime, timedelta
from core import TZ, conflicts, event_day, event_id

SCOPES = ['https://www.googleapis.com/auth/calendar.events']


def connect():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    token = Path(os.getenv('GOOGLE_TOKEN', 'secrets/token.json'))
    client = Path(os.getenv('GOOGLE_CLIENT_SECRET', 'secrets/client_secret.json'))
    creds = Credentials.from_authorized_user_file(str(token), SCOPES) if token.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not client.exists():
                raise ValueError('secrets/client_secret.json にデスクトップ用OAuth認証情報を置いてください')
            creds = InstalledAppFlow.from_client_secrets_file(str(client), SCOPES).run_local_server(port=0, host='localhost', timeout_seconds=180)
        token.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(token), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(creds.to_json())
        token.chmod(0o600)
    return build('calendar', 'v3', credentials=creds, cache_discovery=False)


def existing_events(service, calendar_id, bodies):
    if not bodies:
        return []
    lo = min(event_day(b) for b in bodies)
    hi = date.fromisoformat(max(event_day(b) for b in bodies)) + timedelta(days=1)
    args = {'calendarId': calendar_id, 'timeMin': datetime.fromisoformat(lo).replace(tzinfo=TZ).isoformat(), 'timeMax': datetime.combine(hi, datetime.min.time(), TZ).isoformat(), 'singleEvents': True, 'maxResults': 2500}
    result = []
    while True:
        page = service.events().list(**args).execute()
        result.extend(page.get('items', []))
        if not page.get('nextPageToken'):
            return result
        args['pageToken'] = page['nextPageToken']


def inspect(service, calendar_id, bodies):
    existing = existing_events(service, calendar_id, bodies)
    plan = []
    for body in bodies:
        exact, possible = conflicts(body, existing)
        plan.append({'body': body, 'status': '登録済み' if exact else '類似あり' if possible else '追加可能', 'matches': [e.get('summary', '') for e in exact + possible]})
        existing.append(body)
    return plan


def publish(service, calendar_id, bodies):
    """Recheck at write time; deterministic IDs make retries idempotent."""
    from googleapiclient.errors import HttpError
    plan = inspect(service, calendar_id, bodies)
    outcomes = []
    for item in plan:
        body = dict(item['body'])
        if item['status'] != '追加可能':
            outcomes.append({'title': body['summary'], 'status': item['status'] + '：スキップ'})
            continue
        body['id'] = event_id(body)
        body['extendedProperties'] = {'private': {'source': 'paper-calendar'}}
        try:
            created = service.events().insert(calendarId=calendar_id, body=body).execute()
            outcome = {'title': body['summary'], 'status': '登録完了', 'id': created['id'], 'calendar': calendar_id}
        except HttpError as exc:
            if exc.resp.status == 409:
                outcome = {'title': body['summary'], 'status': '同一IDあり：スキップ', 'id': body['id']}
            else:
                outcomes.append({'title': body['summary'], 'status': f'登録失敗 HTTP {exc.resp.status}。再照合して再試行してください'})
                break
        except Exception:
            outcomes.append({'title': body['summary'], 'status': '通信結果を確認できません。再照合して再試行してください'})
            break
        outcomes.append(outcome)
        # Log success immediately, including partial batch success. Google IDs remain authoritative.
        Path('data').mkdir(exist_ok=True)
        with open('data/history.jsonl', 'a') as f:
            f.write(json.dumps(outcome, ensure_ascii=False) + '\n')
    return outcomes
