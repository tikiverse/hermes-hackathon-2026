"""why: the README GIF is built from Hermes Desktop captures; it must keep 6 steps, one size and a small file."""
import importlib.util
from pathlib import Path

import pytest

Image = pytest.importorskip("PIL.Image")

ROOT = Path(__file__).resolve().parent.parent
BUILDER = ROOT / "scripts" / "make-desktop-demo-gif.py"
COMMITTED = ROOT / "docs" / "img" / "demo.gif"
CAPTURE = (1920, 1050)  # why: size of the Hermes window capture the builder crops
MAX_BYTES = 2 * 1024 * 1024  # why: the README and catalog page load it inline


def load_builder():
    spec = importlib.util.spec_from_file_location("make_desktop_demo_gif", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_builder_makes_one_frame_per_step_at_one_size(tmp_path):
    builder = load_builder()
    for number in range(1, len(builder.STEPS) + 1):
        Image.new("RGB", CAPTURE, (30 + number, 40, 50)).save(tmp_path / f"{number}.png")
    out = tmp_path / "demo.gif"
    builder.main(["builder", str(tmp_path), str(out)])
    gif = Image.open(out)
    assert gif.n_frames == len(builder.STEPS)
    assert gif.size == (builder.CANVAS[0], builder.CANVAS[1] + builder.LABEL_HEIGHT)


def test_every_step_has_a_hold_time():
    builder = load_builder()
    assert len(builder.HOLD_MS) == len(builder.STEPS)


def test_every_crop_stays_inside_the_capture():
    builder = load_builder()
    boxes = [crop for _label, crop, _bright, _cover in builder.STEPS]
    inside = [0 <= left < right <= CAPTURE[0] and 0 <= top < bottom <= CAPTURE[1] for left, top, right, bottom in boxes]
    assert all(inside)
    assert all(box[0] >= 262 for box in boxes), "crop starts left of the chat: the session list would show"


def test_committed_gif_matches_the_builder():
    builder = load_builder()
    gif = Image.open(COMMITTED)
    assert gif.n_frames == len(builder.STEPS)
    assert COMMITTED.stat().st_size < MAX_BYTES
