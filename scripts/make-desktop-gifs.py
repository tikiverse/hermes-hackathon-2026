"""why: build the README GIFs (demo, Desktop install steps) from Hermes Desktop window captures, the same way.

Usage: uv run --with pillow python -I scripts/make-desktop-gifs.py <captures-dir> [<out-dir>]

<captures-dir> holds <gif name>-<step>.png for every step, for example demo-1.png .. demo-6.png and
desktop-install-1.png .. desktop-install-3.png: captures of the Hermes window alone
(`screencapture -x -o -l <window id> <file>.png`), one per step. Each step is cropped to the part it explains, so the
session list never shows. Rows that name a machine or a file path are rewritten. Brighten lifts Desktop's dim command
output so it reads small. Look at every frame before you commit a GIF.
"""
import sys
from pathlib import Path
from typing import NamedTuple

from PIL import Image, ImageDraw, ImageFont

LABEL_HEIGHT = 44
GROUND = (15, 17, 20)  # why: background of the Hermes panes in the captures
LABEL_BG = (17, 21, 28)
LABEL_FG = (230, 233, 238)
ACCENT = (255, 96, 64)
OUTLINE_PAD = 4
OUTLINE_WIDTH = 3
LIFT_KNEE = 50  # why: v + v*v/knee lifts Desktop's dim output (~85) to ~220 and leaves the dark ground near black
LIFT_TABLE = [min(255, value + value * value // LIFT_KNEE) for value in range(256)]  # why: 1 channel, RGB uses it 3x
SESSION_LIST_TOP = 255  # why: y in the capture where the sidebar's search box and chat list start; crops stay above
SIDEBAR_RIGHT = 260  # why: x in the capture where the sidebar ends; crops that reach lower start right of it
NO_LIMIT = float("inf")
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "docs" / "img"


class Cover(NamedTuple):
    """why: paints over a row of the capture and writes a safe row in its place; coordinates are in the capture."""

    box: tuple
    cells: tuple  # why: ((x, y of the text's middle, text), ...)
    fill: tuple
    size: int


class Step(NamedTuple):
    label: str
    crop: tuple  # why: (left, top, right, bottom) in the 1920x1050 window capture
    hold_ms: int = 3000
    bright: bool = False
    marks: tuple = ()  # why: boxes to outline, in capture coordinates
    covers: tuple = ()


class Gif(NamedTuple):
    name: str
    canvas: tuple  # why: size of one frame without its label bar
    max_scale: float  # why: install frames stay sharp (1.0); demo frames grow to fill the canvas
    steps: tuple


LOCAL_ROW = Cover(
    box=(744, 570, 1430, 609),  # why: the `local` model row of the model list prints a file path with a home folder
    cells=((752, 579, "local"), (844, 579, "a local model on this Mac")),
    fill=(83, 88, 92),
    size=11,
)
AGENT_ROW = Cover(
    box=(1120, 521, 1500, 546),  # why: the plugin detail row names this machine's host and port
    cells=((1126, 533, "Agent in default (current)"),),
    fill=(128, 133, 140),
    size=13,
)
PAGE = (540, 100, 1920, 1030)  # why: the Quick Eval page without its chat-list rail
GIFS = (
    Gif("demo.gif", (1200, 760), NO_LIMIT, (
        Step("1  In a Hermes Desktop chat, ask a question", (262, 0, 1920, 400)),
        Step("2  /quick-eval lists the models you can compare", (700, 400, 1460, 820), 3000, True, covers=(LOCAL_ROW,)),
        Step("3  /quick-eval sonnet qwen2.5:0.5b asks two more models", (730, 434, 1440, 900), 3500, True),
        Step("4  /quick-eval open shows the Quick Eval page in Desktop, every answer side by side", PAGE, 3500),
        Step("5  Click the good answers to mark them", PAGE),
        Step("6  Save: the picks stay on your machine", PAGE, 3500),
    )),
    Gif("desktop-install.gif", (1000, 345), 1.0, (
        Step("1  Open Capabilities, then the Plugins tab", (0, 40, 1000, 250),
             marks=((10, 97, 250, 126), (350, 60, 400, 84))),
        Step("2  Filters > Installed: Quick Eval is in the list", (1000, 110, 1700, 360),
             marks=((1655, 170, 1682, 198), (1374, 317, 1442, 341))),
        Step("3  Select Quick Eval, then turn on Desktop", (1100, 215, 1800, 560), 4000,
             marks=((1712, 479, 1768, 507),), covers=(AGENT_ROW,)),
    )),
)


def cover(draw, spec):
    draw.rectangle(spec.box, fill=GROUND)
    font = ImageFont.load_default(size=spec.size)
    for x, y, text in spec.cells:
        draw.text((x, y), text, fill=spec.fill, font=font, anchor="lm")


def outline(draw, box):
    pad = OUTLINE_PAD
    ring = (box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad)
    draw.rounded_rectangle(ring, radius=8, outline=ACCENT, width=OUTLINE_WIDTH)


def fit(image, canvas, max_scale):
    scale = min(canvas[0] / image.width, canvas[1] / image.height, max_scale)
    size = (round(image.width * scale), round(image.height * scale))
    body = Image.new("RGB", canvas, GROUND)
    body.paste(image.resize(size, Image.Resampling.LANCZOS), ((canvas[0] - size[0]) // 2, 0))
    return body


def label_bar(width, text):
    bar = Image.new("RGB", (width, LABEL_HEIGHT), LABEL_BG)
    font = ImageFont.load_default(size=20)
    ImageDraw.Draw(bar).text((16, LABEL_HEIGHT // 2), text, fill=LABEL_FG, font=font, anchor="lm")
    return bar


def frame(captures, gif, number, step):
    image = Image.open(captures / f"{Path(gif.name).stem}-{number}.png").convert("RGB")
    draw = ImageDraw.Draw(image)
    for spec in step.covers:
        cover(draw, spec)
    for box in step.marks:
        outline(draw, box)
    body = fit(image.crop(step.crop), gif.canvas, gif.max_scale)
    page = Image.new("RGB", (gif.canvas[0], gif.canvas[1] + LABEL_HEIGHT))
    page.paste(label_bar(gif.canvas[0], step.label), (0, 0))
    page.paste(body.point(LIFT_TABLE * 3) if step.bright else body, (0, LABEL_HEIGHT))
    return page


def save_gif(images, holds, out):
    palette = [image.quantize(colors=128, method=Image.Quantize.MEDIANCUT) for image in images]
    palette[0].save(out, save_all=True, append_images=palette[1:], duration=holds, loop=0, optimize=True)


def build(captures, gif, out_dir):
    images = [frame(captures, gif, number, step) for number, step in enumerate(gif.steps, 1)]
    out = out_dir / gif.name
    save_gif(images, [step.hold_ms for step in gif.steps], out)
    print(f"{out} ({out.stat().st_size // 1024} KB, {len(images)} steps)")


def main(argv):
    captures = Path(argv[1])
    out_dir = Path(argv[2]) if len(argv) > 2 else DEFAULT_OUT
    for gif in GIFS:
        build(captures, gif, out_dir)


if __name__ == "__main__":
    main(sys.argv)
