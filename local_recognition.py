"""Local OCR. Model downloads contain no calendar images."""
import os
import re
import threading
import unicodedata
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

os.environ.setdefault('HF_HOME', str(Path(__file__).resolve().parent / 'data/models'))
os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')
_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def engine():
    from huggingface_hub import hf_hub_download
    import json
    import onnxruntime
    onnxruntime.disable_telemetry_events()
    from yomitoku import OCR
    configs = {}
    for component, name in [('text_detector', 'dbnet-v2_1'), ('text_recognizer', 'parseq-middle-dynw-v5')]:
        repo = 'KotaroKinoshita/yomitoku-' + component.replace('_', '-') + '-' + name
        try:
            weights = hf_hub_download(repo, 'model.safetensors', local_files_only=True)
        except FileNotFoundError:
            weights = hf_hub_download(repo, 'model.safetensors')
        except Exception as exc:
            from huggingface_hub.errors import LocalEntryNotFoundError
            if not isinstance(exc, LocalEntryNotFoundError):
                raise
            weights = hf_hub_download(repo, 'model.safetensors')
        config = Path(__file__).resolve().parent / 'data/models' / (component + '.json')
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps({'hf_hub_repo': str(Path(weights).parent)}))
        configs[component] = {'model_name': name.replace('dbnet-', 'dbnet'), 'path_cfg': str(config)}
    return OCR(configs=configs, device='cpu', visualize=False)


def parse_text(text):
    normalized = unicodedata.normalize('NFKC', text)
    pattern = r'(?<!\d)([01]?\d|2[0-3])(?:[:：]([0-5]\d)|時(?:([0-5]?\d)分?)?)(?!\d)'
    matches = list(re.finditer(pattern, normalized))
    times = [f'{int(m[1]):02d}:{int(m[2] or m[3] or 0):02d}' for m in matches]
    # Only infer an end time when a range separator explicitly connects the times.
    is_range = len(matches) == 2 and bool(re.fullmatch(r'\s*[〜～~\-–—−]\s*', normalized[matches[0].end():matches[1].start()]))
    ambiguous = len(matches) > 1 and not is_range
    start = times[0] if times and not ambiguous else ''
    end = times[1] if is_range else ''
    title = normalized
    if matches and not ambiguous:
        title = normalized[:matches[0].start()] + normalized[matches[-1].end():]
        title = title.strip(' \n〜～~-:：')
    return title or text, start, end


def records_from_words(words, crops, days, month):
    width = max(c.width for c in crops)
    height = max(c.height for c in crops)
    grouped = {}
    for word in words:
        text = word.content.strip()
        points = np.asarray(word.points)
        x, y = points.mean(axis=0)
        col, row = int(x // width), int(y // height)
        cell = row * 7 + col
        if not (0 <= col < 7 and 0 <= cell < len(days)) or not days[cell].isoformat().startswith(month):
            continue
        # Printed date numerals are in the top-right corner. Preserve other numbers.
        if text.isdigit() and x % width > width * .70 and y % height < height * .20:
            continue
        if text:
            grouped.setdefault(cell, []).append((y, x, text))
    records = []
    for cell, lines in sorted(grouped.items()):
        text = '\n'.join(item[2] for item in sorted(lines))
        title, start, end = parse_text(text)
        issue = '印刷・手書きの区別、複数予定の分割、矢印の期間、取消線は要確認'
        if not start:
            issue += '／時刻未確定：終日候補'
        elif not end:
            issue += '／終了時刻なし：仮に1時間'
        records.append(dict(selected=False, date=days[cell].isoformat(), end_date=days[cell].isoformat(), title=title, start=start, end=end, text=text, kind='uncertain', issue=issue, cell=cell))
    return records


def extract(crops, days, month, progress=None, detailed=True):
    if progress:
        progress('YomiTokuを準備中（初回はモデルをダウンロードします）')
    # A single padded grid retains context and avoids 31 separate model calls.
    width, height = max(c.width for c in crops), max(c.height for c in crops)
    sheet = Image.new('RGB', (width * 7, height * (len(crops) // 7)), 'white')
    for cell, crop in enumerate(crops):
        sheet.paste(crop, ((cell % 7) * width, (cell // 7) * height))
    with _LOCK:
        ocr = engine()
        if progress:
            progress('月全体をMac上で文字認識中。画像は外部へ送信しません。')
        result, _ = ocr(np.asarray(sheet)[:, :, ::-1].copy())
        words, alternatives = detail_words(ocr, crops, days, month, result.words, progress) if detailed else (result.words, {})
    records = records_from_words(words, crops, days, month)
    for row in records:
        if row['cell'] in alternatives:
            row['ocr_alternatives'] = alternatives[row['cell']]
            row['issue'] += '／認識方法により読みが異なります：下の拡大表示で比較'
    return records


def reading_quality(words):
    """Heuristic model score, not an accuracy probability; exclude printed dates."""
    useful = [w for w in words if w.content.strip() and not w.content.strip().isdigit()]
    total = sum(len(w.content) for w in useful)
    return sum(float(getattr(w, 'rec_score', 0)) * len(w.content) for w in useful) / total if total else 0


def detail_words(ocr, crops, days, month, baseline, progress=None):
    from types import SimpleNamespace
    width, height = max(c.width for c in crops), max(c.height for c in crops)
    grouped = {}
    for word in baseline:
        x, y = np.asarray(word.points).mean(axis=0)
        cell = int(y // height) * 7 + int(x // width)
        grouped.setdefault(cell, []).append(word)
    final, alternatives = [], {}
    targets = [i for i,d in enumerate(days) if d.isoformat().startswith(month)]
    for number, cell in enumerate(targets, 1):
        original = grouped.get(cell, [])
        if original and reading_quality(original) >= .85:
            final.extend(original)
            continue
        if progress:
            progress(f'拡大して再認識：{days[cell]}（{number}/{len(targets)}日）')
        crop = crops[cell]
        enlarged = crop.resize((crop.width * 3, crop.height * 3), Image.Resampling.LANCZOS)
        result, _ = ocr(np.asarray(enlarged)[:, :, ::-1].copy())
        detailed = [SimpleNamespace(content=w.content, rec_score=w.rec_score,
                     points=(np.asarray(w.points) / 3 + [cell % 7 * width, cell // 7 * height]).tolist()) for w in result.words]
        def content(ws):
            return '\n'.join(w.content for w in sorted(ws, key=lambda w: tuple(np.asarray(w.points).mean(axis=0)[::-1])) if not w.content.strip().isdigit())
        old, new = content(original), content(detailed)
        # Avoid replacing a complete reading with a short confident fragment.
        choose_detail = bool(new) and (not old or (reading_quality(detailed) > reading_quality(original) + .05 and len(new) >= len(old) * .8))
        final.extend(detailed if choose_detail else original)
        if old != new and (old or new):
            alternatives[cell] = {'月全体の読み': old or '検出なし', '拡大した読み': new or '検出なし'}
    return final, alternatives
