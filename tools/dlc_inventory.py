# -*- coding: utf-8 -*-
"""Инвентаризация DLC-архивов: сколько в каждом диалогов и условий."""
import glob
import json
import os
import re
import subprocess
import sys

G = r"D:\games\SUPER ROBOT WARS V"
T = G + r"\_tools"
B = G + r"\_build\dlc"
os.makedirs(B, exist_ok=True)

# названия миссий из таблицы KPACK_LN
tb = open(G + r"\_extracted\KPACK_LN_dec\00000004.dat", "rb").read()
strs = [(m.start(), m.group().decode("latin1"))
        for m in re.finditer(rb"[\x20-\x7e]{2,80}", tb)]
by_off = dict(strs)
titles = {}
for off, s in strs:
    if re.fullmatch(r"\d{3}[a-z]?", s):
        titles.setdefault(s, by_off.get(off + 64, ""))

rows = []
for cpk in sorted(glob.glob(os.path.join(G, "Data", "DLCDIRE", "EN", "dlc*_en.cpk"))):
    num = re.search(r"dlc(\d+)_en", cpk).group(1)
    work = os.path.join(B, num)
    dec = work + "_dec"
    if not os.path.isdir(dec):
        r = subprocess.run([sys.executable, os.path.join(T, "cpk_extract.py"), cpk, work],
                           capture_output=True, text=True)
        if r.returncode:
            rows.append((num, titles.get(num, ""), -1, -1, "не распаковался"))
            continue
        subprocess.run([sys.executable, os.path.join(T, "srwv_decrypt.py"), work, dec],
                       capture_output=True, text=True)
    blocks = qs = 0
    files = 0
    for dat in sorted(glob.glob(os.path.join(dec, "*.dat"))):
        out = dat[:-4] + ".json"
        r = subprocess.run([sys.executable, os.path.join(T, "ru_lua_dialog.py"), "extract", dat, out],
                           capture_output=True, text=True)
        if r.returncode or not os.path.exists(out):
            continue
        d = json.load(open(out, encoding="utf-8"))
        b, q = len(d.get("blocks", [])), len(d.get("qstrings", []))
        if b or q:
            files += 1
        blocks += b
        qs += q
    rows.append((num, titles.get(num, ""), blocks, qs, "%d файлов" % files))

print("%-5s %-34s %7s %7s  %s" % ("DLC", "название", "блоков", "условий", "текст в"))
tb_, tq = 0, 0
for num, title, b, q, note in rows:
    print("%-5s %-34s %7d %7d  %s" % (num, title[:34], b, q, note))
    if b > 0:
        tb_ += b
        tq += q
print("\nИТОГО: %d блоков диалога, %d условий" % (tb_, tq))
