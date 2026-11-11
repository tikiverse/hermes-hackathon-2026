"""why: README GIFs come from Desktop captures: they keep their steps and size, stay small, and hide private rows."""
import importlib.util
from pathlib import Path

import pytest

Image = pytest.importorskip("PIL.Image")

ROOT = Path(__file__).resolve().parent.parent
BUILDER = ROOT / "scripts" / "make-desktop-gifs.py"
IMAGES = ROOT / "docs" / "img"
CAPTURE = (1920, 1050)  # why: size of the Hermes window capture the builder crops
MAX_BYTES = 2 * 1024 * 1024  # why: the READMEs and the catalog page load the GIFs inline


def load_builder():
    spec = importlib.util.spec_from_file_location("make_desktop_gifs", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_captures(tmp_path, builder):
    for gif in builder.GIFS:
        for number in range(1, len(gif.steps) + 1):
            Image.new("RGB", CAPTURE, (200, 200, 200)).save(tmp_path / f"{Path(gif.name).stem}-{number}.png")


def all_steps(builder):
    return [(gif, step) for gif in builder.GIFS for step in gif.steps]


def test_builder_makes_one_frame_per_step_at_one_size(tmp_path):
    builder = load_builder()
    make_captures(tmp_path, builder)
    out = tmp_path / "out"
    out.mkdir()
    builder.main(["builder", str(tmp_path), str(out)])
    for gif in builder.GIFS:
        made = Image.open(out / gif.name)
        assert made.n_frames == len(gif.steps)
        assert made.size == (gif.canvas[0], gif.canvas[1] + builder.LABEL_HEIGHT)


def test_every_crop_stays_inside_the_capture():
    builder = load_builder()
    for _gif, step in all_steps(builder):
        left, top, right, bottom = step.crop
        assert 0 <= left < right <= CAPTURE[0] and 0 <= top < bottom <= CAPTURE[1], step.label


def test_no_crop_shows_the_session_list():
    builder = load_builder()
    for _gif, step in all_steps(builder):
        left, _top, _right, bottom = step.crop
        assert left >= builder.SIDEBAR_RIGHT or bottom <= builder.SESSION_LIST_TOP, step.label


def test_covers_sit_inside_the_crop_that_shows_them():
    builder = load_builder()
    for _gif, step in all_steps(builder):
        for cover in step.covers:
            box = cover.box
            assert step.crop[0] <= box[0] and box[2] <= step.crop[2], step.label
            assert step.crop[1] <= box[1] and box[3] <= step.crop[3], step.label


def test_committed_gifs_match_the_builder():
    builder = load_builder()
    for gif in builder.GIFS:
        path = IMAGES / gif.name
        assert Image.open(path).n_frames == len(gif.steps)
        assert path.stat().st_size < MAX_BYTES
