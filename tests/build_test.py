"""SVG import regressions: never silently discard rendering instructions."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('build', Path(__file__).resolve().parents[1] / 'scripts/build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

class ImportTests(unittest.TestCase):
    def check_svg(self, attrs='', content='<path d="M3 3H21V21H3Z"/>'):
        build.errors.clear()
        with tempfile.TemporaryDirectory(dir=build.ROOT) as folder:
            path = Path(folder) / 'fixture.svg'
            path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" {attrs}>{content}</svg>')
            result = build.read_icon(path)
        return result, list(build.errors)

    def test_inline_style_cannot_silently_turn_a_stroke_into_a_fill(self):
        _, errors = self.check_svg(content='<path style="fill:none;stroke:black;stroke-width:2" d="M3 3H21V21"/>')
        self.assertTrue(errors, 'Inline styles must be rejected before normalization')

    def test_inherited_fill_none_does_not_create_visible_geometry(self):
        _, errors = self.check_svg(content='<g fill="none"><path d="M3 3H21V21Z"/></g>')
        self.assertTrue(errors, 'Invisible paths must not become filled icons')

    def test_explicit_fill_overrides_inherited_none(self):
        result, errors = self.check_svg(attrs='fill="none"', content='<g fill="none"><path fill="black" d="M3 3H21V21Z"/></g>')
        self.assertFalse(errors)
        self.assertIn('currentColor', result[0])

    def test_invalid_fill_rule_rejected(self):
        _, errors = self.check_svg(content='<path fill-rule="nonsense" d="M3 3H21V21Z"/>')
        self.assertTrue(errors)

    def test_default_fill_is_visible(self):
        result, errors = self.check_svg()
        self.assertFalse(errors)
        self.assertIsNotNone(result)

if __name__ == '__main__':
    unittest.main()
