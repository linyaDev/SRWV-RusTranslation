# -*- coding: utf-8 -*-
"""
Render Russian series titles for the SRW V opening into DDS textures
(same format as originals: 1280x64 uncompressed 32bpp, header copied),
encrypt them and emit files ready for CPK patching.

Usage: ru_op_titles.py <orig_dds_dir> <out_dir>
"""
import os
import struct
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

TOOLS = os.path.dirname(os.path.abspath(__file__))

TITLES = {
    'ID00000_PTR00000050_000': 'Мобильный воин Кроссбоун Гандам: Скалл Харт',
    'ID00000_PTR00000050_001': 'Крейсер «Надэсико»: Принц Тьмы',
    'ID00000_PTR00000050_002': 'Мобильный воин Гандам: Контратака Чара',
    'ID00000_PTR00000050_003': 'Непобедимый Дайтарн 3',
    'ID00000_PTR00000050_004': 'Мобильный воин Гандам 00: Пробуждение Первопроходца',
    'ID00000_PTR00000050_005': 'КОСМИЧЕСКИЙ ЛИНКОР ЯМАТО 2199',
    'ID00001_PTR00000050_000': 'Отважный экспресс Майтгайн',
    'ID00001_PTR00000050_001': 'Мобильный воин Гандам: Вспышка Хэтэуэя',
    'ID00001_PTR00000050_002': 'Супермашина Замбот 3',
    'ID00001_PTR00000050_003': 'Мобильный воин Зета Гандам',
    'ID00001_PTR00000050_004': 'Истинный Мазингер: Удар! Глава Z',
    'ID00001_PTR00000050_005': 'Мобильный воин Гандам Юникорн',
    'ID00001_PTR00000050_006': 'ЕВАНГЕЛИОН 2.0: ТЫ (НЕ) ПРОЙДЁШЬ.',
    'ID00002_PTR00000050_000': 'Кросс Анж: Рондо ангелов и драконов',
    'ID00002_PTR00000050_001': 'Мобильный воин Гандам ZZ',
    'ID00002_PTR00000050_002': 'Стальная тревога!',
    'ID00002_PTR00000050_003': 'Мобильный воин Гандам SEED Destiny',
    'ID00002_PTR00000050_004': 'Геттер Робо: Армагеддон',
    'ID00002_PTR00000050_005': 'Истинный Мазингер ZERO против Великого Генерала Тьмы',
}

FONT = r'C:\Windows\Fonts\arialbd.ttf'


def render(title: str, w: int, h: int) -> Image.Image:
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    size = 42
    while size > 16:
        font = ImageFont.truetype(FONT, size)
        bbox = draw.textbbox((0, 0), title, font=font, stroke_width=4)
        if bbox[2] - bbox[0] <= w - 24 and bbox[3] - bbox[1] <= h - 4:
            break
        size -= 2
    bbox = draw.textbbox((0, 0), title, font=font, stroke_width=4)
    x = (w - (bbox[2] - bbox[0])) // 2 - bbox[0]
    y = (h - (bbox[3] - bbox[1])) // 2 - bbox[1]
    draw.text((x, y), title, font=font, fill=(255, 255, 255, 255),
              stroke_width=4, stroke_fill=(0, 0, 0, 255))
    return img


def write_dds(orig_path: str, img: Image.Image, out_path: str):
    orig = open(orig_path, 'rb').read()
    header = orig[:128]
    rmask, gmask, bmask, amask = struct.unpack_from('<4I', orig, 92)
    order = {0x00FF0000: 2, 0x0000FF00: 1, 0x000000FF: 0, 0xFF000000: 3}
    idx = [order[m] for m in (rmask, gmask, bmask, amask)]  # byte pos of R,G,B,A
    px = img.tobytes()  # RGBA
    out = bytearray(len(px))
    for i in range(0, len(px), 4):
        r, g, b, a = px[i], px[i + 1], px[i + 2], px[i + 3]
        out[i + idx[0]], out[i + idx[1]], out[i + idx[2]], out[i + idx[3]] = r, g, b, a
    data = header + bytes(out)
    assert len(data) == len(orig), (len(data), len(orig))
    open(out_path, 'wb').write(data)


def main():
    src_dir, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    png_dir = os.path.join(out_dir, 'preview')
    os.makedirs(png_dir, exist_ok=True)
    for name, title in TITLES.items():
        orig = os.path.join(src_dir, name + '.DDS')
        im = Image.open(orig)
        new = render(title, im.width, im.height)
        plain = os.path.join(out_dir, name + '.DDS')
        write_dds(orig, new, plain)
        new.save(os.path.join(png_dir, name + '.png'))
        enc = os.path.join(out_dir, name + '.DDS.enc')
        subprocess.run([sys.executable, os.path.join(TOOLS, 'srwv_encrypt.py'),
                        plain, enc], check=True, capture_output=True)
        print(name, '->', title)


if __name__ == '__main__':
    main()
