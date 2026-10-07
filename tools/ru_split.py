#!/usr/bin/env python
"""Split BLTU JSON into N chunks for parallel translation."""
import json, os, sys, math

src, outdir, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
d = json.load(open(src, encoding="utf-8"))
entries = d["entries"]
os.makedirs(outdir, exist_ok=True)
per = math.ceil(len(entries) / n)
base = os.path.splitext(os.path.basename(src))[0]
for i in range(n):
    chunk = entries[i * per:(i + 1) * per]
    if not chunk:
        break
    path = os.path.join(outdir, f"{base}_chunk{i:02d}.json")
    json.dump({"entries": chunk}, open(path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"{path}: {len(chunk)} entries, {sum(len(e['values']) for e in chunk)} strings")
