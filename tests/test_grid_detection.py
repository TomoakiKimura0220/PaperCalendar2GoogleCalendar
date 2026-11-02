import unittest
from PIL import Image, ImageDraw
from grid_detection import detect_grid

class GridDetectionTests(unittest.TestCase):
    def test_regular_grids(self):
        for rows in (4,5,6):
            im=Image.new('RGB',(1000,900),'white'); d=ImageDraw.Draw(im)
            for col in range(8):
                x=80+col*120;d.line((x,100,x,800),fill='black',width=3)
            for row in range(rows+1):
                y=100+row*700/rows;d.line((80,y,920,y),fill='black',width=3)
            corners=detect_grid(im,rows)
            for actual, expected in zip(corners,[(.08,.111),(.92,.111),(.92,.889),(.08,.889)]):
                self.assertAlmostEqual(actual[0],expected[0],delta=.015)
                self.assertAlmostEqual(actual[1],expected[1],delta=.015)

    def test_blank_rejected(self):
        with self.assertRaises(ValueError): detect_grid(Image.new('RGB',(1000,900),'white'),5)

    def test_border_only_is_not_calendar(self):
        im=Image.new('RGB',(1000,900),'white');ImageDraw.Draw(im).rectangle((80,100,920,800),outline='black',width=3)
        with self.assertRaises(ValueError): detect_grid(im,5)
