"""why: build docs/img/demo.gif from window captures of the plugin running in Hermes Desktop, the same way every time.

Usage: uv run --with pillow python -I scripts/make-desktop-demo-gif.py <frames-dir> [<out.gif>]

<frames-dir> holds 1.png .. 6.png: captures of the Hermes window alone (`screencapture -x -o -l <window id>`), one per
step. Each frame is cropped to the part that shows the step, so the README never shows the session list, other chats
or a file path; the one row that names a model file is covered. Dim command output is brightened so it reads small.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CANVAS = (1200, 760)
LABEL_HEIGHT = 44
BACKGROUND = (15, 17, 21)
LABEL_BG = (17, 21, 28)
LABEL_FG = (230, 233, 238)
DIM_TEXT = (83, 88, 92)  # why: colour of Desktop's command-output text, the covered row reuses it
LIFT_KNEE = 50  # why: v + v*v/knee lifts Desktop's dim output (~85) to ~220 and leaves the dark ground near black
LIFT_TABLE = [min(255, value + value * value // LIFT_KNEE) for value in range(256)]  # why: 1 channel, RGB uses it 3x
LOCAL_ROW = (744, 570, 1430, 609)  # why: the `local` model row of step 2 prints a file path with a home folder
LOCAL_CELLS = ((752, "local"), (844, "a local model on this Mac"))  # why: (x in the capture, text), as the rows above
LOCAL_CENTER = 579  # why: y of the row's first line in the capture
PAGE = (540, 100, 1920, 1030)  # why: the Quick Eval page without its chat-list rail
STEPS = [  # why: (label, crop box in the 1920x1050 window capture, brighten, cover)
    ("1  In a Hermes Desktop chat, ask a question", (262, 0, 1920, 400), False, None),
    ("2  /quick-eval lists the models you can compare", (700, 400, 1460, 820), True, LOCAL_ROW),
    ("3  /quick-eval sonnet qwen2.5:0.5b asks two more models", (730, 434, 1440, 900), True, None),
    ("4  /quick-eval open shows the Quick Eval page in Desktop, every answer side by side", PAGE, False, None),
    ("5  Click the good answers to mark them", PAGE, False, None),
    ("6  Save: the picks stay on your machine", PAGE, False, None),
]
HOLD_MS = [3000, 3000, 3500, 3500, 3000, 3500]
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "docs" / "img" / "demo.gif"


def cover_row(image, box, crop_box):
    """why: box and crop_box are in capture coordinates; the cover must follow the crop."""
    left, top = crop_box[0], crop_box[1]
    draw = ImageDraw.Draw(image)
    draw.rectangle((box[0] - left, box[1] - top, box[2] - left, box[3] - top), fill=BACKGROUND)
    font = ImageFont.load_default(size=11)
    for x, text in LOCAL_CELLS:
        draw.text((x - left, LOCAL_CENTER - top), text, fill=DIM_TEXT, font=font, anchor="lm")


def brighten(image):
    return image.point(LIFT_TABLE * 3)


def fit(image):
    scale = min(CANVAS[0] / image.width, CANVAS[1] / image.height)
    size = (round(image.width * scale), round(image.height * scale))
    canvas = Image.new("RGB", CANVAS, BACKGROUND)
    canvas.paste(image.resize(size, Image.Resampling.LANCZOS), ((CANVAS[0] - size[0]) // 2, 0))
    return canvas


def label_bar(text):
    bar = Image.new("RGB", (CANVAS[0], LABEL_HEIGHT), LABEL_BG)
    font = ImageFont.load_default(size=20)
    ImageDraw.Draw(bar).text((16, LABEL_HEIGHT // 2), text, fill=LABEL_FG, font=font, anchor="lm")
    return bar


def step_image(frames, number, step):
    label, crop_box, bright, cover = step
    image = Image.open(frames / f"{number}.png").convert("RGB").crop(crop_box)
    if cover:
        cover_row(image, cover, crop_box)
    page = Image.new("RGB", (CANVAS[0], CANVAS[1] + LABEL_HEIGHT))
    page.paste(label_bar(label), (0, 0))
    page.paste(brighten(fit(image)) if bright else fit(image), (0, LABEL_HEIGHT))
    return page


def save_gif(images, out):
    palette = [image.quantize(colors=128, method=Image.Quantize.MEDIANCUT) for image in images]
    palette[0].save(out, save_all=True, append_images=palette[1:], duration=HOLD_MS, loop=0, optimize=True)


def main(argv):
    frames = Path(argv[1])
    out = Path(argv[2]) if len(argv) > 2 else DEFAULT_OUT
    save_gif([step_image(frames, number, step) for number, step in enumerate(STEPS, 1)], out)
    print(f"{out} ({out.stat().st_size // 1024} KB, {len(STEPS)} steps)")


if __name__ == "__main__":
    main(sys.argv)
