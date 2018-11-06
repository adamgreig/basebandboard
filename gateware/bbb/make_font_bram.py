from PIL import Image, ImageFont, ImageDraw
import numpy as np


def draw_letter(c):
    image = Image.new("1", (8, 16), 0)
    font = ImageFont.truetype("/home/adam/.fonts/Inconsolata.otf", 13)
    draw = ImageDraw.Draw(image)
    draw.fontmode = "1"
    draw.text((0, 1), c, 1, font=font)
    return list(image.getdata())


def make_font():
    font = []
    for x in range(128):
        font += draw_letter(chr(x))
    return font


if __name__ == "__main__":
    font = make_font()
    np.savez_compressed("font.npz", font=font)
