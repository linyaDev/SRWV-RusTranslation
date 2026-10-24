# -*- coding: utf-8 -*-
"""Собрать и установить русифицированный DLC-архив.

  build_dlc.py <номер> [<номер> ...]

Для каждого номера: инжект переводов в Lua, шифрование, пересборка CPK,
обратное чтение для проверки, установка (если файл не занят игрой).
"""
import glob
import json
import os
import re
import subprocess
import sys

G = r"D:\games\SUPER ROBOT WARS V"
T, E, B = os.path.join(G, "_tools"), os.path.join(G, "_extracted"), os.path.join(G, "_build", "dlc")


def run(args):
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    if r.returncode:
        print(r.stdout[-600:], r.stderr[-600:])
        raise SystemExit("ошибка: " + " ".join(os.path.basename(a) for a in args[:2]))
    return r.stdout


for num in sys.argv[1:]:
    src = os.path.join(E, "dlc" + num + "_en")
    dec = os.path.join(B, num + "_dec")
    repl = []
    for p in sorted(glob.glob(os.path.join(src, "ru_000000??.json"))):
        fid = re.search(r"ru_(\d{8})\.json$", p).group(1)
        d = json.load(open(p, encoding="utf-8-sig"))
        if "blocks" not in d:
            # файл условий победы: диалогов нет, инжектим qstrings поверх оригинала
            d = {"blocks": [], "qstrings": d.get("qstrings", [])}
            tmp = p[:-5] + "_full.json"
            json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            p = tmp
        lua = os.path.join(dec, fid + ".dat")
        out = os.path.join(B, "%s_ru_%s.dat" % (num, fid))
        print(run([os.path.join(T, "ru_lua_dialog.py"), "inject", lua, p, out]).strip())
        enc = out[:-4] + "_enc.dat"
        run([os.path.join(T, "srwv_encrypt.py"), out, enc])
        repl.append("%d=%s" % (int(fid), enc))

    cpk = os.path.join(G, "Data", "DLCDIRE", "EN", "dlc%s_en.cpk" % num)
    base = cpk + ".bak" if os.path.exists(cpk + ".bak") else cpk
    out_cpk = os.path.join(B, "dlc%s_RU.cpk" % num)
    print(run([os.path.join(T, "ru_cpk_patch.py"), base, out_cpk] + repl).strip())

    # проверка: прочитать собранный архив обратно
    chk = os.path.join(B, num + "_chk")
    for d in (chk, chk + "_dec"):
        if os.path.isdir(d):
            for f in os.listdir(d):
                os.remove(os.path.join(d, f))
    run([os.path.join(T, "cpk_extract.py"), out_cpk, chk])
    run([os.path.join(T, "srwv_decrypt.py"), chk, chk + "_dec"])
    dlg = [p for p in sorted(glob.glob(os.path.join(src, "ru_000000??.json")))
           if "blocks" in json.load(open(p, encoding="utf-8-sig"))]
    fid = re.search(r"ru_(\d{8})\.json$", dlg[0]).group(1)
    js = os.path.join(chk + "_dec", fid + ".json")
    run([os.path.join(T, "ru_lua_dialog.py"), "extract",
         os.path.join(chk + "_dec", fid + ".dat"), js])
    blocks = json.load(open(js, encoding="utf-8"))["blocks"]
    print("  проверка: прочитано %d блоков, первая реплика: %s" %
          (len(blocks), blocks[0]["text"].replace("\n", " / ")[:60]))

    try:
        with open(cpk, "r+b"):
            pass
    except OSError:
        print("  файл занят игрой — не ставлю")
        continue
    if not os.path.exists(cpk + ".bak"):
        import shutil
        shutil.copy(cpk, cpk + ".bak")
        print("  backup создан")
    import shutil
    shutil.copy(out_cpk, cpk)
    print("  установлено: dlc%s_en.cpk (%d байт)" % (num, os.path.getsize(cpk)))
