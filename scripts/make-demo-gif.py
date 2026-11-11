"""why: build docs/img/demo.gif from the screen recording of the demo, the same way every time.

Usage: uv run --with pillow python -I scripts/make-demo-gif.py <video> [<out.gif>]

Keeps only the app window: the recording's webcam overlay (people) and burned-in captions are cropped or covered, so
the README shows the plugin and nobody's face. Each step is one still frame with a label bar above it.
"""
import io
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

APP_WINDOW = (60, 45, 900, 485)  # why: left, top, right, bottom of the app in the 960x600 recording, above the captions
WEBCAM = (628, 344, 840, 440)  # why: webcam overlay inside the cropped window (left, top, right, bottom)
FILL_AT = (740, 330)  # why: a pixel just above the webcam; its colour hides the overlay without a visible box
LABEL_HEIGHT = 44
LABEL_BG = (17, 21, 28)
LABEL_FG = (230, 233, 238)
HOLD_MS = 3200
KEYFRAMES = [  # why: (seconds into the recording, label); each is the first moment its step is fully on screen
    (26, "1  Hermes answers your question (here DeepSeek-R1 1.5B)"),
    (46, "2  /quick-eval lists the models you can compare"),
    (70, "3  /quick-eval qwen36 qwen2.5:0.5b asks two more models"),
    (84, "4  /quick-eval open shows every answer side by side"),
    (97, "5  Click the good answers to mark them; picks stay on your machine"),
]
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "docs" / "img" / "demo.gif"


def grab_frame(video, seconds):
    png = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(seconds), "-i", str(video), "-frames:v", "1",
                          "-f", "image2pipe", "-vcodec", "png", "-"], check=True, capture_output=True).stdout
    return Image.open(io.BytesIO(png)).convert("RGB")


def cover_webcam(image):
    image.paste(image.getpixel(FILL_AT), WEBCAM)
    return image


def label_bar(width, text):
    bar = Image.new("RGB", (width, LABEL_HEIGHT), LABEL_BG)
    font = ImageFont.load_default(size=20)
    ImageDraw.Draw(bar).text((16, LABEL_HEIGHT // 2), text, fill=LABEL_FG, font=font, anchor="lm")
    return bar


def step_image(video, seconds, text):
    window = cover_webcam(grab_frame(video, seconds).crop(APP_WINDOW))
    page = Image.new("RGB", (window.width, window.height + LABEL_HEIGHT))
    page.paste(label_bar(window.width, text), (0, 0))
    page.paste(window, (0, LABEL_HEIGHT))
    return page


def save_gif(images, out):
    palette = [image.quantize(colors=128, method=Image.Quantize.MEDIANCUT) for image in images]
    palette[0].save(out, save_all=True, append_images=palette[1:], duration=HOLD_MS, loop=0, optimize=True)


def main(argv):
    video = Path(argv[1])
    out = Path(argv[2]) if len(argv) > 2 else DEFAULT_OUT
    save_gif([step_image(video, seconds, text) for seconds, text in KEYFRAMES], out)
    print(f"{out} ({out.stat().st_size // 1024} KB, {len(KEYFRAMES)} steps)")


if __name__ == "__main__":
    main(sys.argv)
