#!/usr/bin/env python3
"""
Fix Cyrillic glyph metrics in SRW V proportional font table (FontInfo id 3).

File layout: 40-byte header (atlasW, atlasH, cellW, cellH, 4, 4,
default_advance f32, line_height f32, scale f32, pad), then records of
36 bytes: uint32 codepoint + 8 floats [u, v, w, h, left_bearing,
advance, const_33.85, ink_width], sorted by codepoint descending.

Cyrillic glyphs ship with left_bearing 6-12 and advance 41 (full-width).
Latin uses left_bearing 1-3 and advance = bearing + ink_width + 0..3.
This script sets for U+0400..U+04FF: left_bearing = 2, advance = ink + 4.

Usage: ru_font_metrics.py input.dat output.dat
"""
import struct
import sys

HDR = 40
REC = 36

src, dst = sys.argv[1], sys.argv[2]
data = bytearray(open(src, 'rb').read())
n = (len(data) - HDR) // REC
assert (len(data) - HDR) % REC == 0, 'unexpected size'

patched = 0
for i in range(n):
    p = HDR + i * REC
    cp, = struct.unpack_from('<I', data, p)
    if 0x0400 <= cp <= 0x04FF:
        u, v, w, h, bearing, adv, c7, ink = struct.unpack_from('<8f', data, p + 4)
        new_bearing = 2.0
        new_adv = ink + 4.0
        struct.pack_into('<8f', data, p + 4, u, v, w, h, new_bearing, new_adv, c7, ink)
        patched += 1
        if patched <= 3 or cp in (0x0416, 0x0438):
            print(f'U+{cp:04X} {chr(cp)}: bearing {bearing:g}->!{new_bearing:g}, adv {adv:g}->{new_adv:g} (ink {ink:g})')

open(dst, 'wb').write(data)
print(f'Patched {patched} Cyrillic glyphs -> {dst}')
