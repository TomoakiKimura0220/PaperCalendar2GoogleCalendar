import io
from PIL import ImageOps


def pasted_image_bytes(image):
    if image.width * image.height > 40_000_000:
        raise ValueError('画像は4000万画素以下にしてください')
    output = io.BytesIO()
    ImageOps.exif_transpose(image).convert('RGB').save(output, format='PNG')
    data = output.getvalue()
    if len(data) > 20 * 1024 * 1024:
        raise ValueError('画像は20MB以下にしてください')
    return data
