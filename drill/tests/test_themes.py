"""Theme registry + palette contract.

Adding a theme is one entry in themes.py and one CSS file, and nothing checks
either at import time — so these tests do. The colour rules exist because the
×/÷ models paint the marks a student has to *count* with
`color-mix(... var(--accent-2) 60%, var(--text))`: --text is the contrast
anchor, so a theme whose --text sits mid-way between light and dark weakens
every one of those marks at once.
"""
import pathlib
import re

from django.conf import settings
from django.test import SimpleTestCase

from drill.themes import DEFAULT_THEME, THEMES, get_theme

THEME_DIR = pathlib.Path(settings.BASE_DIR) / 'static' / 'drill' / 'themes'
JS_DIR = pathlib.Path(settings.BASE_DIR) / 'static' / 'drill' / 'js'

REGISTRY_KEYS = {
    'name', 'greeting', 'icon', 'mascot', 'points_name', 'point_icon',
    'cheers', 'oops', 'goal_met', 'practice_label', 'instructions_title',
    'instructions_intro',
}
CSS_VARS = ['--bg', '--panel', '--panel-soft', '--text', '--text-soft',
            '--accent', '--accent-2', '--good', '--soft-bad', '--btn-bg',
            '--btn-border']


def _hex(value):
    value = value.strip().lstrip('#')
    if len(value) == 3:
        value = ''.join(c * 2 for c in value)
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _vars(key):
    """The flat colour variables declared in one theme's CSS. Comments are
    stripped first — prose in a theme file may well mention a variable name
    followed by a colon, and that must not be read as a declaration."""
    css = (THEME_DIR / f'{key}.css').read_text()
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    found = {}
    for name in CSS_VARS:
        m = re.search(re.escape(name) + r':\s*([^;]+);', css)
        if m:
            found[name] = m.group(1).strip()
    return found


def _luminance(rgb):
    def channel(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _mix(c1, c2, weight):
    """color-mix(in srgb, c1 weight%, c2) — sRGB is interpolated in the
    gamma-encoded space, so this is a plain lerp of the byte values."""
    return tuple(round(a * weight + b * (1 - weight)) for a, b in zip(c1, c2))


# The mixes app.css uses for the countable marks in the x / div models.
def _dot_colour(v):      # .gp-dot fill, .sl-hop stroke
    return _mix(_hex(v['--accent-2']), _hex(v['--text']), 0.60)


def _ring_colour(v):     # .gp-ring stroke
    return _mix(_hex(v['--accent']), _hex(v['--text']), 0.72)


class RegistryTests(SimpleTestCase):
    def test_every_theme_has_the_full_registry_entry(self):
        for key, theme in THEMES.items():
            self.assertEqual(set(theme), REGISTRY_KEYS, key)

    def test_intro_text_takes_the_goal(self):
        for key, theme in THEMES.items():
            self.assertIn('{goal}', theme['instructions_intro'], key)
            # and formats without blowing up
            self.assertIn('150', theme['instructions_intro'].format(goal=150))

    def test_phrase_pools_are_non_trivial(self):
        for key, theme in THEMES.items():
            self.assertGreaterEqual(len(theme['cheers']), 3, key)
            self.assertGreaterEqual(len(theme['oops']), 2, key)

    def test_names_and_keys_are_distinct(self):
        names = [t['name'] for t in THEMES.values()]
        self.assertEqual(len(names), len(set(names)))
        mascots = [t['mascot'] for t in THEMES.values()]
        self.assertEqual(len(mascots), len(set(mascots)), 'duplicate mascot')

    def test_default_theme_exists_and_unknown_keys_fall_back(self):
        self.assertIn(DEFAULT_THEME, THEMES)
        self.assertEqual(get_theme('no-such-theme'), THEMES[DEFAULT_THEME])
        self.assertEqual(get_theme(''), THEMES[DEFAULT_THEME])
        for key in THEMES:
            self.assertEqual(get_theme(key), THEMES[key], key)


class StylesheetTests(SimpleTestCase):
    def test_every_theme_ships_a_stylesheet_scoped_to_its_body_class(self):
        for key in THEMES:
            path = THEME_DIR / f'{key}.css'
            self.assertTrue(path.exists(), f'missing {path.name}')
            self.assertIn(f'body.theme-{key}', path.read_text(), key)

    def test_every_stylesheet_declares_the_whole_variable_contract(self):
        for key in THEMES:
            found = _vars(key)
            self.assertEqual(sorted(found), sorted(CSS_VARS),
                             f'{key} is missing {set(CSS_VARS) - set(found)}')

    def test_no_orphan_stylesheets(self):
        on_disk = {p.stem for p in THEME_DIR.glob('*.css')}
        self.assertEqual(on_disk, set(THEMES),
                         'a .css file with no registry entry, or vice versa')

    def test_every_css_url_reference_resolves_to_a_real_file(self):
        """The deploy blocker this guards: production uses
        CompressedManifestStaticFilesStorage, and `collectstatic` *fails* —
        MissingFileError, no static files at all — if a CSS url() points at a
        file that isn't there. Every theme references an "optional"
        <key>/background.webp, which makes it not optional; a transparent
        placeholder keeps the reference valid while the slot is empty.
        """
        static = pathlib.Path(settings.BASE_DIR) / 'static'
        css_files = [pathlib.Path(settings.BASE_DIR) / 'static' / 'drill' / 'css' / 'app.css']
        css_files += sorted(THEME_DIR.glob('*.css'))
        checked = 0
        for css in css_files:
            body = re.sub(r'/\*.*?\*/', '', css.read_text(), flags=re.S)
            for ref in re.findall(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""", body):
                if ref.startswith(('http:', 'https:', 'data:', '//', '#')):
                    continue
                target = (css.parent / ref).resolve()
                self.assertTrue(
                    target.exists(),
                    f'{css.name} references {ref}, which does not exist — '
                    f'collectstatic will fail on this in production')
                self.assertTrue(str(target).startswith(str(static.resolve())))
                checked += 1
        self.assertEqual(checked, len(THEMES),
                         'expected one background-image reference per theme')

    def test_every_theme_has_an_art_slot_file(self):
        for key in THEMES:
            art = THEME_DIR / key / 'background.webp'
            self.assertTrue(art.exists(), f'no art slot for {key}')

    def test_every_theme_has_a_chip_colour_on_the_picker(self):
        # the "Pick your world" chips preview each palette; without a rule a
        # new theme's chip renders in the *current* theme's colours
        css = (pathlib.Path(settings.BASE_DIR) / 'static' / 'drill' / 'css'
               / 'app.css').read_text()
        for key in THEMES:
            self.assertIn(f'.chip-{key}', css,
                          f'no .chip-{key} rule for the theme picker')

    def test_every_theme_has_its_own_answer_sounds(self):
        js = (JS_DIR / 'sound.js').read_text()
        for key in THEMES:
            m = re.search(r'^    ' + key + r': \{(.*?)^    \},',
                          js, re.S | re.M)
            self.assertIsNotNone(m, f'{key} has no entry in sound.js SPECS')
            for kind in ('correct', 'wrong', 'goal'):
                self.assertIn(f'{kind}:', m.group(1), f'{key}.{kind}')


class PaletteContrastTests(SimpleTestCase):
    """The rules that keep the visual models legible on every theme."""

    def test_text_is_firmly_on_one_side_of_the_panel(self):
        # a mid-tone --text would weaken every countable mark at once, since
        # the model colours are mixed toward it
        for key in THEMES:
            v = _vars(key)
            ratio = _contrast(_hex(v['--text']), _hex(v['--panel']))
            self.assertGreaterEqual(
                round(ratio, 2), 7.0,
                f'{key}: --text vs --panel is only {ratio:.2f}:1 — pick a '
                f'clearly dark-on-light or light-on-dark pair')

    def test_countable_marks_stand_out_on_the_panel(self):
        # .gp-dot / .sl-hop against the model area's --panel background
        for key in THEMES:
            v = _vars(key)
            ratio = _contrast(_dot_colour(v), _hex(v['--panel']))
            self.assertGreaterEqual(
                round(ratio, 2), 3.0,
                f'{key}: group dots / hop arcs are {ratio:.2f}:1 on the panel')

    def test_countable_marks_stand_out_inside_a_group_ring(self):
        # the dots sit on --panel-soft (the ring's fill), not bare --panel
        for key in THEMES:
            v = _vars(key)
            ratio = _contrast(_dot_colour(v), _hex(v['--panel-soft']))
            self.assertGreaterEqual(
                round(ratio, 2), 3.0,
                f'{key}: group dots are {ratio:.2f}:1 inside the ring')

    def test_group_rings_stand_out(self):
        for key in THEMES:
            v = _vars(key)
            ratio = _contrast(_ring_colour(v), _hex(v['--panel']))
            self.assertGreaterEqual(
                round(ratio, 2), 3.0,
                f'{key}: group rings are {ratio:.2f}:1 on the panel')

    def test_the_two_halves_of_a_broken_apart_array_are_different_colours(self):
        # Deliberately a channel-distance check, not a contrast-ratio one: the
        # halves are told apart by hue (plus a 12px gap and their own labels),
        # and every shipped theme sits at a luminance ratio of only 1.2-1.9
        # while being perfectly readable. What would actually break the picture
        # is two accents that resolve to near-identical fills.
        for key in THEMES:
            v = _vars(key)
            a = _mix(_hex(v['--accent']), (255, 255, 255), 0.70)
            b = _mix(_hex(v['--accent-2']), (255, 255, 255), 0.80)
            apart = max(abs(x - y) for x, y in zip(a, b))
            self.assertGreaterEqual(
                apart, 40,
                f'{key}: the two halves of a broken-apart array differ by only '
                f'{apart}/255 in their strongest channel — pick accents that '
                f'are not near-identical once tinted')

    def test_soft_bad_reads_against_the_panel(self):
        # the strike line on a nines array, and the crossed-out dots
        for key in THEMES:
            v = _vars(key)
            ratio = _contrast(_hex(v['--soft-bad']), _hex(v['--panel']))
            self.assertGreaterEqual(round(ratio, 2), 2.2, f'{key}: --soft-bad')
