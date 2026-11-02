import io
import unittest
import numpy as np
from PIL import Image
from perspective import rectify, validate_corners
from recognition import prepare, DEFAULT_LAYOUT

class PerspectiveTests(unittest.TestCase):
    def test_identity(self):
        data = np.random.default_rng(1).integers(0,256,(100,150,3),dtype=np.uint8)
        result = rectify(Image.fromarray(data), [[0,0],[1,0],[1,1],[0,1]])
        self.assertEqual(result.size,(150,100))
        self.assertLess(np.abs(np.array(result).astype(float)-data).mean(), 1)

    def test_bad_points(self):
        for p in [[[0,0],[1,1],[1,0],[0,1]], [[0,0],[0,0],[1,1],[0,1]], [[-1,0],[1,0],[1,1],[0,1]], [[0,0],[1,0],[float('nan'),1],[0,1]]]:
            with self.assertRaises(ValueError): validate_corners(p)

    def test_crop_excludes_margins(self):
        im = Image.new('RGB',(201,201),'red')
        from PIL import ImageDraw
        ImageDraw.Draw(im).rectangle((40,40,160,160),fill='white')
        raw=io.BytesIO(); im.save(raw,format='PNG')
        _,crops,days=prepare(raw.getvalue(),DEFAULT_LAYOUT,'2026-11',corners=[[.2,.2],[.8,.2],[.8,.8],[.2,.8]])
        self.assertEqual(len(crops),35)
        self.assertEqual(crops[0].getpixel((5,5)),(255,255,255))

    def test_trapezoid_mapping(self):
        # A source trapezoid's center maps inside the corrected grid.
        im=Image.new('RGB',(301,201),'black')
        from PIL import ImageDraw
        ImageDraw.Draw(im).polygon([(60,20),(240,20),(280,180),(20,180)],fill='white')
        out=rectify(im,[[.2,.1],[.8,.1],[280/300,.9],[20/300,.9]])
        self.assertEqual(out.getpixel((out.width//2,out.height//2)),(255,255,255))
        self.assertEqual(out.getpixel((10,10)),(255,255,255))
