import io
import hashlib
import json
import os
from datetime import date
from pathlib import Path
import streamlit as st
from PIL import Image, ImageOps
from perspective import EXAMPLE_CORNERS, marked_corners
from dotenv import load_dotenv
from core import event_body, month_overview
from recognition import DEFAULT_LAYOUT, prepare, week_image
import google_calendar as gc
from local_recognition import extract
from streamlit_paste_button import paste_image_button
from image_input import pasted_image_bytes
from grid_detection import detect_grid

os.chdir(Path(__file__).resolve().parent)
load_dotenv()
st.set_page_config(page_title='紙カレンダー取り込み', page_icon='📅', layout='wide')
st.title('紙カレンダー取り込み')
st.caption('MacBook上で画像を確認し、選んだ予定だけGoogleカレンダーへ追加します。')

with st.sidebar:
    st.header('設定')
    month = st.text_input('対象年月（YYYY-MM）', date.today().strftime('%Y-%m'))
    st.caption('認識：YomiToku（Mac上で実行・APIキー不要）')
    st.caption('初回のみモデルをダウンロードします。文字認識中に画像を外部へ送信しません。')
    detailed_ocr = st.checkbox('不確かなマスを拡大して再認識', value=True)
    st.caption('通常より時間がかかります。異なる読みは画像の下で比較できます。')
    saved = Path('data/layout.json')
    layout = json.loads(saved.read_text()) if saved.exists() else DEFAULT_LAYOUT.copy()
    with st.expander('固定レイアウトの調整'):
        st.caption('添付画像を基準に設定済み。赤枠が日付のマスに合うよう調整してください。画像全体に対する比率です。')
        for k, label in [('left', '左端'), ('top', '上端'), ('right', '右端'), ('bottom', '下端')]:
            layout[k] = st.number_input(label, 0.0, 1.0, float(layout[k]), step=0.001, format='%.3f')
        layout['rows'] = st.selectbox('週の行数', [4, 5, 6], index=[4, 5, 6].index(layout['rows']))
        if st.button('レイアウトを保存'):
            saved.parent.mkdir(exist_ok=True)
            saved.write_text(json.dumps(layout))
            st.success('保存しました')
    calendar_id = st.text_input('登録先カレンダーID', value='primary', placeholder='primary または専用カレンダーのID')
    st.caption('Googleカレンダーの「設定と共有 → カレンダーの統合」でIDを確認できます。')
    if st.button('Googleに接続'):
        try:
            st.session_state.service = gc.connect()
            st.session_state.pop('plan', None)
            st.success('接続しました')
        except Exception as exc:
            st.error(f'接続できませんでした（{type(exc).__name__}）。認証設定とREADMEを確認してください。')
    st.caption('接続済み' if 'service' in st.session_state else '未接続：認識だけなら接続不要')

input_method = st.radio('画像の入力方法', ['ファイルを選択', 'クリップボードから貼り付け'], horizontal=True)
upload = None
if input_method == 'ファイルを選択':
    upload = st.file_uploader('カレンダー画像を選択', type=['png', 'jpg', 'jpeg'])
else:
    st.caption('画像をコピーして「画像を貼り付け」を押してください。スクリーンショットはControl＋Shift＋Command＋4でクリップボードにコピーできます。')
    if st.button('貼り付けた画像をクリア'):
        st.session_state.pop('pasted_image', None)
        st.session_state.paste_generation = st.session_state.get('paste_generation', 0) + 1
    try:
        pasted = paste_image_button('画像を貼り付け', key='paste_' + str(st.session_state.get('paste_generation', 0)), errors='raise')
        if pasted.image_data is not None:
            st.session_state.pasted_image = pasted_image_bytes(pasted.image_data)
    except Exception:
        st.error('画像を貼り付けられませんでした。20MB・4000万画素以下の画像をコピーし直してください。')
    if st.session_state.get('pasted_image'):
        upload = io.BytesIO(st.session_state.pasted_image)
    st.caption('ブラウザがクリップボードの許可を求めたら許可してください。使えない場合はファイル選択を利用できます。')
if upload is None and st.session_state.get('source') not in (None, 'demo'):
    for name in ['records', 'plan', 'plan_signature', 'source']:
        st.session_state.pop(name, None)

if upload:
    raw = upload.getvalue()
    corners = None
    if st.checkbox('写真の四隅を合わせる（台形補正）', value=True):
        st.caption('日付マスの罫線から四隅を自動検出します。曜日の帯と余白は除外します。手動調整のX・Yは画像内の位置（%）です。')
        image_key = hashlib.sha256(raw).hexdigest()[:12]
        alignment = st.radio('マス合わせ', ['自動検出', '手動調整'], horizontal=True)
        if alignment == '自動検出':
            detection_key = image_key + '_' + str(layout['rows'])
            if st.session_state.get('detected_grid_key') != detection_key:
                try:
                    with st.spinner('カレンダーの罫線を検出しています…'):
                        detected = detect_grid(Image.open(io.BytesIO(raw)), int(layout['rows']))
                    st.session_state.detected_grid = detected
                    st.session_state.detected_grid_error = ''
                except ValueError as exc:
                    st.session_state.detected_grid = None
                    st.session_state.detected_grid_error = str(exc)
                st.session_state.detected_grid_key = detection_key
            corners = st.session_state.detected_grid
            if corners is None:
                st.warning(st.session_state.detected_grid_error + ' 「手動調整」に切り替えてください。週の行数も確認してください。')
                for stale in ['records', 'plan', 'plan_signature', 'source']:
                    st.session_state.pop(stale, None)
                st.stop()
            for i, pair in enumerate(corners):
                for j, value in enumerate(pair):
                    st.session_state[f'corner_{image_key}_{i}_{j}'] = value * 100
            st.caption('罫線から外枠を検出しました。赤枠を確認し、ずれていたら手動調整へ切り替えてください。')
        else:
            if st.button('添付した写真の位置を初期値にする'):
                for i, pair in enumerate(EXAMPLE_CORNERS):
                    for j, value in enumerate(pair):
                        st.session_state[f'corner_{image_key}_{i}_{j}'] = value * 100
            defaults = [[layout['left'], layout['top']], [layout['right'], layout['top']], [layout['right'], layout['bottom']], [layout['left'], layout['bottom']]]
            corners = []
            for i, col in enumerate(st.columns(4)):
                with col:
                    st.write(['1 左上', '2 右上', '3 右下', '4 左下'][i])
                    corners.append([st.number_input(axis + ' (%)', 0.0, 100.0, float(defaults[i][j]*100), step=0.1, format='%.2f', key=f'corner_{image_key}_{i}_{j}')/100 for j, axis in enumerate(['X', 'Y'])])
        try:
            original = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB')
            st.image(marked_corners(original, corners), caption='赤い四角をマス全体の外枠に合わせてください', width='stretch')
        except (ValueError, OSError) as exc:
            st.error(str(exc))
            st.stop()
    signature = hashlib.sha256(raw + json.dumps([month, layout, corners, 'yomitoku-detail-v1', detailed_ocr], sort_keys=True).encode()).hexdigest()
    if st.session_state.get('source') != signature:
        for key in ['records', 'plan', 'plan_signature']:
            st.session_state.pop(key, None)
        st.session_state.source = signature
    try:
        preview, crops, days = prepare(raw, layout, month, corners=corners)
    except Exception as exc:
        st.error(str(exc))
        st.stop()
    with st.expander('マス位置を確認', expanded=True):
        st.image(preview, caption='赤枠と日付が合っていることを確認してください', width='stretch')
    st.caption('YomiTokuで月全体をローカル解析します。1マスを1候補にまとめます。複数予定の分割・矢印の期間・取消線・印刷文字は確認画面で修正してください。')
    if st.button('画像を解析'):
        try:
            with st.spinner('手書きの予定を読み取っています…'):
                retry_status = st.empty()
                st.session_state.records = extract(crops, days, month, progress=retry_status.info, detailed=detailed_ocr)
                retry_status.empty()
                st.session_state.revision = st.session_state.get('revision', 0) + 1
            st.session_state.pop('plan', None)
        except Exception as exc:
            st.error(f'ローカル解析に失敗しました（{type(exc).__name__}）。初回のモデル取得にはインターネット接続が必要です。メモリ不足の場合は他のアプリを閉じてください。')
else:
    st.info('画像を選ぶか、デモで確認・編集の流れを試せます。')
    if st.button('デモの予定を読み込む（API不要）'):
        st.session_state.records = [{'selected': False, 'date': '2026-11-10', 'end_date': '2026-11-10', 'title': '歯医者', 'start': '14:00', 'end': '', 'text': '歯医者 14時', 'kind': 'handwritten', 'issue': '終了時刻なし：仮に1時間', 'cell': 9}, {'selected': False, 'date': '2026-11-23', 'end_date': '2026-11-23', 'title': '勤労感謝の日', 'start': '', 'end': '', 'text': '勤労感謝の日', 'kind': 'printed', 'issue': '印刷済みの例', 'cell': 22}]
        st.session_state.records.append({'selected': False, 'date': '2026-11-16', 'end_date': '2026-11-18', 'title': '出張', 'start': '', 'end': '', 'text': '← 出張 →', 'kind': 'handwritten', 'issue': '両端矢印の期間：開始日と最終日を確認', 'cell': 15})
        st.session_state.source = 'demo'
        st.session_state.pop('plan', None)

if 'records' not in st.session_state:
    st.stop()
st.subheader('予定を確認・修正')
st.caption('登録する行だけselectedをチェック。dateは開始日、end_dateは含める最終日（単日は同じ日）。期間不明の行は最終日を入力してください。複数日予定は終日で登録します。時刻はHH:MM、空欄は終日。終了時刻が空欄なら1時間。印刷文字・取り消し線・月外の予定を確認してください。')
records = st.session_state.records
with st.expander('1か月分の確認（日付は月末まで表示）', expanded=True):
    st.table(month_overview(month, records))
    st.caption('予定の抽出なしは、AIが予定を返さなかった日です。空欄か読み落としかは画像で確認してください。')
if not records:
    st.info('予定は見つかりませんでした。画像とマス位置を確認してください。')
    st.stop()
edited = st.data_editor(records, disabled=['text', 'kind', 'issue', 'cell', 'ocr_alternatives'], column_config={'ocr_alternatives': None}, num_rows='dynamic', width='stretch', key='editor_' + st.session_state.get('source', 'demo') + str(st.session_state.get('revision', 0)))
if upload:
    cell = st.selectbox('拡大して確認するマス', range(len(days)), format_func=lambda i: str(days[i]))
    st.image(crops[cell], width=400)
    for record in records:
        if record.get('cell') == cell and record.get('ocr_alternatives'):
            st.caption('別の読み（モデルの評価値で候補を選んでいますが、正しさの保証ではありません。title欄は自由に修正できます）')
            st.json(record['ocr_alternatives'])
    st.image(week_image(crops, (cell // 7) * 7, days), caption='矢印の両端を週全体で確認', width='stretch')
st.download_button('候補をJSONで保存', json.dumps(edited, ensure_ascii=False, indent=2), 'calendar-candidates.json', 'application/json')
selected = [r for r in edited if r.get('selected')]
try:
    bodies = [event_body(r) for r in selected]
except (ValueError, KeyError, TypeError) as exc:
    st.error(f'選択した予定を修正してください：{exc}')
    st.stop()
fingerprint = hashlib.sha256(json.dumps([calendar_id, bodies], sort_keys=True).encode()).hexdigest()
if st.session_state.get('plan_signature') != fingerprint:
    st.session_state.pop('plan', None)
if bodies:
    st.write('登録内容（補完した終了時刻を含む）')
    st.json(bodies, expanded=False)
is_demo = st.session_state.get('source') == 'demo'
if is_demo:
    st.info('デモではGoogleへの書き込みを無効にしています。実際の画像を選んで解析すると登録できます。')
ready = bool(bodies and calendar_id and 'service' in st.session_state and not is_demo)
if st.button('Googleの既存予定と照合', disabled=not ready):
    try:
        st.session_state.plan = gc.inspect(st.session_state.service, calendar_id, bodies)
        st.session_state.plan_signature = fingerprint
    except Exception as exc:
        st.error(f'照合できませんでした（{type(exc).__name__}）。カレンダーIDとアクセス権を確認してください。')
if 'plan' in st.session_state:
    plan = st.session_state.plan
    st.table([{'予定': p['body']['summary'], '開始': str(p['body']['start']), '終了（終日は翌日）': str(p['body']['end']), '判定': p['status'], '既存の候補': ' / '.join(p['matches'])} for p in plan])
    st.caption('登録済み・類似ありはスキップします。類似ありの予定はGoogle側で確認して手動登録してください。')
    confirmed = st.checkbox('日付・時刻・登録先を確認しました', key='confirm_' + fingerprint)
    if st.button('追加可能な予定をGoogleに登録', type='primary', disabled=not confirmed or not any(p['status'] == '追加可能' for p in plan)):
        try:
            result = gc.publish(st.session_state.service, calendar_id, bodies)
            st.table(result)
            st.session_state.pop('plan', None)
        except Exception as exc:
            st.error(f'処理を完了できませんでした（{type(exc).__name__}）。再照合して結果を確認してください。')
