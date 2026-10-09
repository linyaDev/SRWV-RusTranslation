import json, os, re, collections
E = r"D:\games\SUPER ROBOT WARS V\_extracted"
G = r"D:\games\SUPER ROBOT WARS V"

# кто говорит в миссиях 001-010
smap = json.load(open(G + r"\_build\stage_map.json"))
cur = None
st = {}
for r in smap:
    m = re.match(r"stage(\w+?)(preset)?\.lua$", r["lua"])
    if m:
        cur = m.group(1)
    if cur:
        st.setdefault(cur, []).append(r["id"])

cast = collections.Counter()
for name, ids in st.items():
    if not re.fullmatch(r"0(0\d|10)[a-z]?", name):
        continue
    for fid in ids:
        for d in ("dialogs_ru", "dialogs_en_v3", "dialogs_en"):
            p = os.path.join(E, d, "%08d.json" % fid)
            if os.path.exists(p):
                for x in json.load(open(p, encoding="utf-8-sig")).get("blocks", []):
                    s = x.get("speaker", "").strip()
                    if s:
                        cast[s] += 1
                break
print("говорящих в миссиях 001-010:", len(cast))

# статьи энциклопедии о персонажах
idx = json.load(open(os.path.join(E, "zkan_index.json"), encoding="utf-8"))["entries"]
chars = [e for e in idx if e.get("type") == "CHAR"]
done = {a["file"] for a in json.load(open(os.path.join(E, "zkan_all_ru.json"),
                                          encoding="utf-8"))["articles"]}
print("статей о персонажах всего:", len(chars), "| переведено:",
      sum(1 for c in chars if c["file"] in done))

# сопоставление по имени/короткому имени и по русскому глоссарию
sp = json.load(open(os.path.join(E, "dialogs_en", "_speakers_ru.json"), encoding="utf-8-sig"))
ru2en = {}
for en, ru in sp.items():
    ru2en.setdefault(ru, en)
need = []
for c in chars:
    if c["file"] in done:
        continue
    short, full = c.get("short_name", ""), c.get("name", "")
    for speaker in cast:
        en = ru2en.get(speaker, speaker)
        if en and (en == short or en == full or (" " in full and en == full.split()[0])):
            need.append((cast[speaker], speaker, full, c["file"], c["dir"], c["text_chars"]))
            break
need.sort(reverse=True)
print("\nне переведены, а в миссиях 1-10 говорят:", len(need))
for n, speaker, full, f, d, ch in need:
    print("  %-16s %-26s %s  %5d симв., реплик %d" % (speaker, full, f, ch, n))
json.dump({"files": [x[3] for x in need]},
          open(os.path.join(E, "zkan_need_ch1.json"), "w", encoding="utf-8"), ensure_ascii=False)
