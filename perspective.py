"""Perspective correction of the calendar grid, excluding paper margins."""
import math
import numpy as np
from PIL import Image, ImageDraw

# Starting points measured from the example photo; always review against the uploaded image.
EXAMPLE_CORNERS = [[0.0875, 0.1211], [0.8725, 0.1267], [0.9100, 0.9156], [0.0600, 0.9300]]


def validate_corners(corners):
    points = np.asarray(corners, dtype=float)
    if points.shape != (4, 2) or not np.isfinite(points).all() or (points < 0).any() or (points > 1).any():
        raise ValueError('四隅は画像内の座標（0〜1）で指定してください')
    edges = np.roll(points, -1, axis=0) - points
    cross = edges[:, 0] * np.roll(edges[:, 1], -1) - edges[:, 1] * np.roll(edges[:, 0], -1)
    if (cross <= 1e-6).any():
        raise ValueError('四隅を左上・右上・右下・左下の順に指定してください。交差・重なりは使えません')
    area = abs(sum(points[i, 0]*points[(i+1)%4, 1] - points[(i+1)%4, 0]*points[i, 1] for i in range(4))) / 2
    if area < 0.01:
        raise ValueError('指定範囲が小さすぎます')
    return points


def marked_corners(image, corners):
    points = validate_corners(corners) * [image.width-1, image.height-1]
    result = image.copy()
    draw = ImageDraw.Draw(result)
    xy = [tuple(p) for p in points]
    draw.line(xy+[xy[0]], fill='red', width=4)
    for i, (x, y) in enumerate(xy):
        draw.ellipse((x-8, y-8, x+8, y+8), fill='red')
        draw.text((x+10, y+10), str(i+1), fill='red', stroke_width=1)
    return result


def rectify(image, corners):
    src = validate_corners(corners) * [image.width-1, image.height-1]
    width = round(max(math.dist(src[0], src[1]), math.dist(src[3], src[2])))+1
    height = round(max(math.dist(src[0], src[3]), math.dist(src[1], src[2])))+1
    if min(width, height) < 20 or width * height > 40_000_000:
        raise ValueError('補正後の画像サイズが範囲外です')
    dst = [(0, 0), (width-1, 0), (width-1, height-1), (0, height-1)]
    matrix, target = [], []
    for (x, y), (u, v) in zip(dst, src):
        matrix.extend([[x, y, 1, 0, 0, 0, -u*x, -u*y], [0, 0, 0, x, y, 1, -v*x, -v*y]])
        target.extend([u, v])
    coefficients = np.linalg.solve(np.array(matrix), np.array(target))
    return image.transform((width, height), Image.Transform.PERSPECTIVE, coefficients, Image.Resampling.BICUBIC)
