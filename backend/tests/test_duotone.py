from io import BytesIO

from PIL import Image

from app.providers.duotone import apply_duotone, generate_placeholder_hero

WISDOM_PRIMARY = "#4B3A6E"
WISDOM_SECONDARY = "#F3EEF9"


def _sample_source_image() -> bytes:
    im = Image.new("RGB", (40, 40))
    pixels = im.load()
    for y in range(40):
        for x in range(40):
            v = int(255 * (x / 39))
            pixels[x, y] = (v, v, v)
    buf = BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_apply_duotone_maps_shadows_and_highlights():
    result = apply_duotone(_sample_source_image(), WISDOM_PRIMARY, WISDOM_SECONDARY)
    im = Image.open(BytesIO(result)).convert("RGB")

    darkest_pixel = im.getpixel((0, 0))
    lightest_pixel = im.getpixel((39, 0))

    assert darkest_pixel == (0x4B, 0x3A, 0x6E)
    assert lightest_pixel == (0xF3, 0xEE, 0xF9)


def test_apply_duotone_is_deterministic():
    src = _sample_source_image()
    first = apply_duotone(src, WISDOM_PRIMARY, WISDOM_SECONDARY)
    second = apply_duotone(src, WISDOM_PRIMARY, WISDOM_SECONDARY)
    assert first == second


def test_generate_placeholder_hero_is_cached(tmp_path, monkeypatch):
    import app.providers.duotone as duotone_module

    monkeypatch.setattr(duotone_module, "CACHE_DIR", tmp_path)

    first = generate_placeholder_hero("pause", WISDOM_PRIMARY, WISDOM_SECONDARY, size=(20, 20))
    cached_files = list(tmp_path.glob("*.png"))
    assert len(cached_files) == 1

    second = generate_placeholder_hero("pause", WISDOM_PRIMARY, WISDOM_SECONDARY, size=(20, 20))
    assert first == second
    # still exactly one cache file — second call was a cache hit, not a new render
    assert len(list(tmp_path.glob("*.png"))) == 1


def test_generate_placeholder_hero_gradient_endpoints():
    data = generate_placeholder_hero("pause", WISDOM_PRIMARY, WISDOM_SECONDARY, size=(10, 10))
    im = Image.open(BytesIO(data)).convert("RGB")
    assert im.getpixel((0, 0)) == (0x4B, 0x3A, 0x6E)
    assert im.getpixel((0, 9)) == (0xF3, 0xEE, 0xF9)
