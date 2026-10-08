# -*- coding: utf-8 -*-
"""Собрать MtZkn_Pt.cpk с переведёнными статьями энциклопедии."""
import json
import os
import subprocess
import sys

T = r"D:\games\SUPER ROBOT WARS V\_tools"
E = r"D:\games\SUPER ROBOT WARS V\_extracted"
B = r"D:\games\SUPER ROBOT WARS V\_build"
SRC = os.path.join(E, "MtZkn_Pt_dec")
WORK = os.path.join(B, "zkan_work")
os.makedirs(WORK, exist_ok=True)

tr = json.load(open(os.path.join(E, "zkan_tr.json"), encoding="utf-8-sig"))["articles"]
patch_args = []

for art in tr:
    fname = art["file"]
    src_dat = os.path.join(SRC, fname)
    json_in = os.path.join(E, "zkan_pt_json", fname.replace(".dat", ".json"))
    rec = json.load(open(json_in, encoding="utf-8"))

    changed = 0
    for fl in rec["fields"]:
        key = fl["tag"] + "_ru"
        if key in art and art[key]:
            fl["text"] = art[key]
            changed += 1
    tmp_json = os.path.join(WORK, fname.replace(".dat", "_ru.json"))
    json.dump(rec, open(tmp_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    out_dat = os.path.join(WORK, fname)
    r = subprocess.run([sys.executable, os.path.join(T, "ru_zkan.py"), "rebuild",
                        src_dat, tmp_json, out_dat], capture_output=True, text=True)
    if r.returncode:
        print("ОШИБКА rebuild", fname, r.stdout[-300:], r.stderr[-300:])
        sys.exit(1)

    enc = os.path.join(WORK, fname.replace(".dat", "_enc.dat"))
    subprocess.run([sys.executable, os.path.join(T, "srwv_encrypt.py"), out_dat, enc],
                   check=True, capture_output=True)
    fid = int(fname[:8])
    patch_args.append(f"{fid}={enc}")
    print(f"  {fname}: {changed} полей, {os.path.getsize(src_dat)} -> {os.path.getsize(out_dat)} байт")

orig = r"D:\games\SUPER ROBOT WARS V\CommonData\MtData\EN\MtZkn_Pt.cpk"
bak = orig + ".bak"
src_cpk = bak if os.path.exists(bak) else orig
out_cpk = os.path.join(B, "MtZkn_Pt_RU.cpk")
cmd = [sys.executable, os.path.join(T, "ru_cpk_patch.py"), src_cpk, out_cpk] + patch_args
r = subprocess.run(cmd, capture_output=True, text=True)
print(r.stdout[-400:])
if r.returncode:
    print(r.stderr[-400:])
    sys.exit(1)
print("готово:", out_cpk, os.path.getsize(out_cpk), "байт")
