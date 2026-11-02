import io
from PIL import Image, ImageDraw, ImageOps
from core import grid_dates

DEFAULT_LAYOUT = {'left': 0.032, 'top': 0.081, 'right': 0.969, 'bottom': 0.965, 'rows': 5}


def prepare(raw, layout, month, corners=None):
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB')
    if image.width * image.height > 40_000_000:
        raise ValueError('画像は4000万画素以下にしてください')
    if corners is not None:
        from perspective import rectify
        image = rectify(image, corners)
        layout = dict(layout, left=0, top=0, right=1, bottom=1)
    l, t, r, b = [float(layout[k]) for k in ('left', 'top', 'right', 'bottom')]
    if not (0 <= l < r <= 1 and 0 <= t < b <= 1):
        raise ValueError('マス領域の座標が不正です')
    rows = int(layout['rows'])
    if rows not in (4, 5, 6):
        raise ValueError('行数は4〜6です')
    days = grid_dates(month, rows)
    x0, y0, x1, y1 = l * image.width, t * image.height, r * image.width, b * image.height
    crops = []
    preview = image.copy()
    draw = ImageDraw.Draw(preview)
    for i, day in enumerate(days):
        row, col = divmod(i, 7)
        box = (round(x0 + col * (x1-x0)/7), round(y0 + row * (y1-y0)/rows), round(x0 + (col+1)*(x1-x0)/7), round(y0 + (row+1)*(y1-y0)/rows))
        crop = image.crop(box)
        crops.append(crop)
        draw.rectangle(box, outline='red', width=2)
        draw.text((box[0]+5, box[1]+20), f'{i}: {day}', fill='red')
    return preview, crops, days


def week_image(crops, offset, days):
    """Reassemble adjacent cells at original resolution, without gaps or scaling."""
    week = crops[offset:offset + 7]
    if len(week) != 7:
        raise ValueError('週の画像には7マス必要です')
    sheet = Image.new('RGB', (sum(c.width for c in week), max(c.height for c in week) + 30), 'white')
    draw = ImageDraw.Draw(sheet)
    x = 0
    for j, crop in enumerate(week):
        sheet.paste(crop, (x, 30))
        draw.text((x + 4, 5), f'cell={offset+j} {days[offset+j]}', fill='black')
        x += crop.width
    return sheet
