# Theme art slots

Each `<key>/background.webp` here is a **1×1 transparent placeholder**, not
art. Drop a real image in over the top (roughly 1536×1024 works well) and it
appears behind that theme; the theme's `--bg` gradient shows through wherever
the image is transparent, so a partly-transparent image layers over it.

Why a placeholder instead of no file: production uses
`CompressedManifestStaticFilesStorage`, and `collectstatic` **fails outright**
if a CSS `url()` points at a file that does not exist —

    whitenoise.storage.MissingFileError: The file
    'drill/themes/space/background.webp' could not be found

so an "optional" file referenced from `<key>.css` is not optional at all. The
placeholder keeps the reference valid while the slot is still empty.
`drill/tests/test_themes.py` fails if any CSS `url()` has no file behind it.
