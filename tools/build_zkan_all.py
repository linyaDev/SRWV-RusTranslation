# -*- coding: utf-8 -*-
"""Собрать MtZkn_Pt.cpk и MtZkn_Rt.cpk со всеми переведёнными статьями."""
import json
import os
import subprocess
import sys
from collections import defaultdict

T = r"D:\games\SUPER ROBOT WARS V\_tools"
E = r"D:\games\SUPER ROBOT WARS V\_extracted"
B = r"D:\games\SUPER ROBOT WARS V\_build"
WORK = os.path.join(B, "zkan_work")
os.makedirs(WORK, exist_ok=True)

arts = json.load(open(os.path.join(E, "zkan_all_ru.json"), encoding="utf-8"))["articles"]
by_dir = defaultdict(list)
for a in arts:
    d = a.get("dir") or "MtZkn_Pt_dec"
    by_dir[d].append(a)

CPK = {"MtZkn_Pt_dec": ("MtZkn_Pt", "zkan_pt_json"),
       "MtZkn_Rt_dec": ("MtZkn_Rt", "zkan_rt_json")}

for dec_dir, group in by_dir.items():
    cpk_name, json_dir = CPK[dec_dir]
    patch = []
    for art in group:
        fname = art["file"]
        src_dat = os.path.join(E, dec_dir, fname)
        rec = json.load(open(os.path.join(E, json_dir, fname.replace(".dat", ".json")),
                             encoding="utf-8"))
        for fl in rec["fields"]:
            key = fl["tag"] + "_ru"
            if art.get(key):
                fl["text"] = art[key]
        tmp = os.path.join(WORK, f"{cpk_name}_{fname}.json")
        json.dump(rec, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        out_dat = os.path.join(WORK, f"{cpk_name}_{fname}")
        r = subprocess.run([sys.executable, os.path.join(T, "ru_zkan.py"), "rebuild",
                            src_dat, tmp, out_dat], capture_output=True, text=True)
        if r.returncode:
            print("ОШИБКА", fname, r.stdout[-200:], r.stderr[-200:])
            sys.exit(1)
        enc = out_dat.replace(".dat", "_enc.dat")
        subprocess.run([sys.executable, os.path.join(T, "srwv_encrypt.py"), out_dat, enc],
                       check=True, capture_output=True)
        patch.append(f"{int(fname[:8])}={enc}")

    orig = rf"D:\games\SUPER ROBOT WARS V\CommonData\MtData\EN\{cpk_name}.cpk"
    src = orig + ".bak" if os.path.exists(orig + ".bak") else orig
    out_cpk = os.path.join(B, f"{cpk_name}_RU.cpk")
    r = subprocess.run([sys.executable, os.path.join(T, "ru_cpk_patch.py"), src, out_cpk] + patch,
                       capture_output=True, text=True)
    if r.returncode:
        print(r.stdout[-300:], r.stderr[-300:])
        sys.exit(1)
    print(f"{cpk_name}: {len(group)} статей -> {out_cpk} ({os.path.getsize(out_cpk)} байт)")
