import json, os
E = r"D:\games\SUPER ROBOT WARS V\_extracted"
bl = next(s for s in json.load(open(os.path.join(E, "cmn_subs_EN.json"), encoding="utf-8"))["sections"]
          if s["name"] == "battle_lines")["strings"]
tm = json.load(open(os.path.join(E, "cmn_tm.json"), encoding="utf-8"))
real = [t for t in bl if t.strip() and t not in ("-", "...", "\u2026", "dummy")]
uniq = set(real)
done_u = sum(1 for t in uniq if t in tm)
done_i = sum(1 for t in real if t in tm)
print("вхождений всего: %d | переведено %d | осталось %d (%d%%)" %
      (len(real), done_i, len(real) - done_i, done_i * 100 // len(real)))
print("уникальных:      %d | переведено %d | осталось %d (%d%%)" %
      (len(uniq), done_u, len(uniq) - done_u, done_u * 100 // len(uniq)))
print("символов в непереведённых:", sum(len(t) for t in uniq if t not in tm))

# где именно осталось: по тысячам позиций
print("\nкарта непереведённого (по 2000 строк файла):")
for a in range(0, len(bl), 2000):
    seg = [t for t in bl[a:a + 2000] if t.strip() and t not in ("-", "...", "dummy")]
    if not seg:
        continue
    un = sum(1 for t in seg if t not in tm)
    bar = "#" * int(un / len(seg) * 40)
    print("  %5d-%5d  %4d/%4d  %s" % (a, a + 1999, un, len(seg), bar))
