"""Check the geometry checker against deliberately broken outlines."""
import importlib.util
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import qa


@unittest.skipUnless(shutil.which('rsvg-convert') and importlib.util.find_spec('PIL'), 'requires librsvg and Pillow')
class GeometryTests(unittest.TestCase):
    def test_blank_geometry_is_rejected(self):
        self.assertTrue(qa.measure('<path d="M3 3"/>')['empty'])

    def test_canvas_overflow_is_visible_to_the_checker(self):
        result = qa.measure('<path d="M-1 3H25V21H-1Z"/>')
        self.assertTrue(result['clipped'])
        self.assertEqual(result['bounds'], [-1, 3, 25, 21])

    def test_valid_icon_has_real_ink_and_fits(self):
        result = qa.measure('<path d="M3 3H21V21H3Z"/>')
        self.assertFalse(result['empty'])
        self.assertFalse(result['clipped'])
        self.assertEqual(result['inkArea'], 324)

    def test_different_path_syntax_can_render_identically(self):
        a = qa.measure('<path d="M3 3H21V21H3Z"/>')
        b = qa.measure('<path d="M3 3L21 3L21 21L3 21Z"/>')
        self.assertEqual(a['rasterHash'], b['rasterHash'])
