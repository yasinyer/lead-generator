"""Tekent packaging/icon.png (1024x1024). PyInstaller maakt er een .icns van."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

S = 1024
OUT = Path(__file__).with_name("icon.png")


def main():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # macOS-icoonraster: vorm van ~824px met zachte schaduw
    pad, r = 100, 185
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((pad, pad + 14, S - pad, S - pad + 14), r, fill=(0, 0, 0, 90))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))

    # verloop van blauw naar indigo
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    top, bottom = (47, 107, 255), (88, 56, 214)
    for y in range(S):
        t = y / S
        gd.line([(0, y), (S, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((pad, pad, S - pad, S - pad), r, fill=255)
    img.paste(grad, (0, 0), mask)

    def layer(draw_fn):
        lay = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        draw_fn(ImageDraw.Draw(lay))
        img.alpha_composite(lay)

    # stadje (lokale zaken) onderaan, half doorschijnend
    def city(d):
        base = 800
        for x0, w, h in [(190, 105, 150), (305, 120, 225), (435, 95, 170), (540, 140, 260), (690, 95, 185),
                         (795, 40, 110)]:
            d.rounded_rectangle((x0, base - h, x0 + w, base), 16, fill=(255, 255, 255, 70))
        d.rounded_rectangle((170, base, 854, base + 20), 10, fill=(255, 255, 255, 110))
    layer(city)

    # vergrootglas met ster (= goede reviews) erin
    cx, cy, rad, ring = 455, 410, 190, 56

    def lens(d):
        d.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=(30, 40, 120, 120))
    layer(lens)

    def glass(d):
        white = (255, 255, 255, 255)
        d.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), outline=white, width=ring)
        hx, hy = cx + int(rad * 0.72), cy + int(rad * 0.72)
        d.line((hx, hy, hx + 170, hy + 170), fill=white, width=84)
        d.ellipse((hx + 170 - 42, hy + 170 - 42, hx + 170 + 42, hy + 170 + 42), fill=white)
        import math
        pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            rr = 92 if i % 2 == 0 else 38
            pts.append((cx + rr * math.cos(ang), cy + 8 + rr * math.sin(ang)))
        d.polygon(pts, fill=(255, 196, 61, 255))
    layer(glass)
    img.save(OUT)
    print(f"geschreven: {OUT}")


if __name__ == "__main__":
    main()
