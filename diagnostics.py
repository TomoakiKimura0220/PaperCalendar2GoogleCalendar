"""API diagnostics without request bodies, URLs, or credentials."""
import re


def recognition_error(exc, api_key=''):
    if isinstance(exc, UnicodeEncodeError):
        # Never display exc.object: HTTP header encoding errors may contain the key.
        return '文字コードの変換に失敗しました。APIキーとモデル名を半角で入力し直してください。改善しない場合は、発生箇所の追加調査が必要です。'
    if isinstance(exc, ValueError) and str(exc).startswith(('APIキー', 'モデル名')):
        return str(exc)
    code = getattr(exc, 'code', None)
    hints = {
        400: 'APIキーの無効、またはモデルが受け付けないリクエストです。下の詳細を確認してください。',
        401: '認証できませんでした。AI StudioでAPIキーを確認してください。',
        403: 'アクセスが拒否されました。キーのAPI制限、プロジェクトの権限、利用条件を確認してください。',
        404: '指定したモデルが見つからないか、このAPIで利用できません。モデル名を確認してください。',
        429: '利用枠またはリクエスト上限に達しました。AI Studioの使用量・割り当て・課金設定を確認してください。',
        500: 'Google側でエラーが発生しました。時間を置いて再試行してください。',
        503: 'Google側が混雑しています。時間を置いて再試行してください。',
    }
    message = getattr(exc, 'message', '') or ''
    if not isinstance(message, str):
        message = ''
    if api_key:
        message = message.replace(api_key, '[APIキー非表示]')
    message = re.sub(r'AIza[\w-]+', '[APIキー非表示]', message)
    message = re.sub(r'https?://\S+', '[URL省略]', message)
    message = re.sub(r'(?i)(api[_ -]?key|token|authorization)(\s*[:=]\s*)\S+', r'\1\2[非表示]', message)
    title = f'解析に失敗しました（HTTP {code}）' if isinstance(code, int) else f'解析に失敗しました（{type(exc).__name__}）'
    hint = hints.get(code, '通信状況・モデル設定を確認してください。')
    return title + '\n\n' + hint + ('\n\nGoogleからの詳細：\n' + message[:2000] if message else '')
