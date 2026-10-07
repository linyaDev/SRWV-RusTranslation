#!/usr/bin/env python
"""Merge translated chunks back into a full BLTU JSON and validate against the original.

Usage: ru_merge.py original.json chunks_dir chunk_basename output.json
Validates per entry: key unchanged, value count unchanged, extra preserved,
\\cN control-code multiset per string unchanged, placeholders (%s/%d) preserved,
key-reference values (ALL_CAPS_WITH_UNDERSCORES) and "\\n" strings unchanged.
"""
import json, os, sys, re, glob

orig_path, chunks_dir, base, out_path = sys.argv[1:5]
orig = json.load(open(orig_path, encoding="utf-8"))

chunk_files = sorted(glob.glob(os.path.join(chunks_dir, base + "_chunk*.json")))
merged = []
for cf in chunk_files:
    merged.extend(json.load(open(cf, encoding="utf-8"))["entries"])

errors = []
KEYREF = re.compile(r"^[A-Z0-9_]+$")
CTRL = re.compile(r"\\c\d|\\n|\\[a-zA-Z]")
PLACE = re.compile(r"%[sdxu]|%\d+d")

if len(merged) != len(orig["entries"]):
    errors.append(f"entry count {len(merged)} != {len(orig['entries'])}")

for i, (o, t) in enumerate(zip(orig["entries"], merged)):
    if o["key"] != t.get("key"):
        errors.append(f"[{i}] key mismatch: {o['key']} != {t.get('key')}")
        continue
    if len(o["values"]) != len(t["values"]):
        errors.append(f"[{i}] {o['key']}: value count {len(t['values'])} != {len(o['values'])}")
        continue
    if o.get("extra") != t.get("extra"):
        errors.append(f"[{i}] {o['key']}: extra changed")
    for j, (ov, tv) in enumerate(zip(o["values"], t["values"])):
        if (KEYREF.match(ov) and len(ov) > 2) or ov == "\n":
            if ov != tv:
                errors.append(f"[{i}] {o['key']}[{j}]: key-ref/newline altered: {ov!r} -> {tv!r}")
            continue
        if sorted(CTRL.findall(ov)) != sorted(CTRL.findall(tv)):
            errors.append(f"[{i}] {o['key']}[{j}]: control codes differ: {CTRL.findall(ov)} -> {CTRL.findall(tv)}")
        if sorted(PLACE.findall(ov)) != sorted(PLACE.findall(tv)):
            errors.append(f"[{i}] {o['key']}[{j}]: placeholders differ: {PLACE.findall(ov)} -> {PLACE.findall(tv)}")

out = dict(orig)
out["entries"] = merged
json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"Merged {len(merged)} entries from {len(chunk_files)} chunks -> {out_path}")
if errors:
    print(f"\n{len(errors)} VALIDATION ERRORS:")
    for e in errors[:60]:
        print("  " + e)
    sys.exit(1)
print("Validation OK")
