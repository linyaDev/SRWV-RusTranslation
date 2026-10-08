#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ru_mt_jstr.py -- parser / rebuilder for the '<mt>' container of Super Robot Wars V.

The '<mt>' container holds the in-game glossary / encyclopedia data
(rpw_jstr.cpk, lega_zkn.cpk ...). It is a flat list of named chunks; some
chunks are pools of NUL-terminated UTF-8 strings, others are index tables
that store *byte offsets* into those pools.

Sub-commands
------------
  probe   <file|dir> [...]              identify container type of file(s)
  info    <in.dat>                      dump chunk layout of an <mt> file
  extract <in.dat> <out.json>           dump translatable strings
  rebuild <in.dat> <tr.json> <out.dat> [--force]
                                        write a new container with new strings
  verify  <in.dat> [...]                extract+rebuild in memory, assert identity

The JSON produced by `extract` has a "strings" array of
    {"idx": n, "text": "...", "ids": [...], "is_key": bool, "slots": [...]}
Edit the "text" fields (or add "text_ru"), keep "idx"/"slots" intact, then
feed the file to `rebuild`. New strings may have any length: every pool
offset stored anywhere in the container is recomputed.

Read-only with respect to the game: nothing under the game data folders is
ever written; `rebuild` only writes the explicit <out.dat> path.
"""

import json
import os
import re
import struct
import sys

# ---------------------------------------------------------------- constants

MT_MAGIC = b"<mt>\0\0\0\0"
HEADER_SIZE = 0x28

TAG_CHUNK_HEAD = b"<chunk-head>"   # 12
TAG_CHUNK_FOOT = b"<chunk-foot>"   # 12
TAG_END_CHUNK = b"<endofchunk>"    # 12
TAG_FILE_FOOT = b"<file--foot>"    # 12
TAG_END_OF_MT = b"****<end-of-mt>."  # 16 ('****' is just padding)
TAG_END_OF_MT_CORE = b"<end-of-mt>."  # 12

PAD_BYTE = 0x2A  # '*'
FOOT_ALIGN = 8

# key-like strings (rid_*/pid_* identifiers) are never translated
KEY_RE = re.compile(r"^[a-z]+_[A-Za-z0-9_]+$")

# chunk names that are string pools even if the heuristic is unsure
POOL_NAME_RE = re.compile(r"^(j-?string|jstr[-_].*)$", re.I)


class MtError(Exception):
    pass


# ---------------------------------------------------------------- utilities

def _align(v, a):
    return (v + a - 1) & ~(a - 1)


def u32(buf, off):
    return struct.unpack_from("<I", buf, off)[0]


def split_pool(payload):
    """Split a string-pool payload into (offset, bytes) slots.

    The pool is a sequence of NUL-terminated records and always ends with a
    NUL, so `payload.split(b'\\x00')[:-1]` reproduces it exactly.
    """
    slots = []
    off = 0
    for raw in payload.split(b"\x00")[:-1]:
        slots.append((off, raw))
        off += len(raw) + 1
    return slots


def join_pool(records):
    out = bytearray()
    for raw in records:
        out += raw
        out.append(0)
    return bytes(out)


def looks_like_pool(name, payload):
    if not payload or payload[-1] != 0:
        return False
    nuls = payload.count(0)
    if nuls < 8:
        return False
    printable = sum(
        1 for c in payload
        if c == 0 or c >= 0x80 or 0x20 <= c < 0x7F or c in (9, 10, 13)
    )
    if printable / len(payload) < 0.98:
        return False
    for raw in payload.split(b"\x00")[:-1]:
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            return False
    # average record length must be sane for text
    return (len(payload) / nuls) < 512


# ---------------------------------------------------------------- container

class Chunk(object):
    __slots__ = ("name", "raw_name", "head_off", "payload", "rec_size",
                 "kind", "lanes")

    def __init__(self, raw_name, head_off, payload, rec_size):
        self.raw_name = raw_name
        self.name = raw_name.rstrip(b"\0").decode("ascii", "replace")
        self.head_off = head_off
        self.payload = payload
        self.rec_size = rec_size
        self.kind = "opaque"
        self.lanes = []      # list of Lane


class Lane(object):
    """A regular sequence of slots inside a chunk payload holding pool offsets.

    Slot i lives at byte  phase + i*stride  and is `width` bytes wide.
    `key_phase` (optional) is a companion lane at the same stride whose values
    are the numeric ids of the referenced strings.
    """
    __slots__ = ("width", "stride", "phase", "count", "pool", "key_phase")

    def __init__(self, width, stride, phase, count, pool, key_phase=None):
        self.width = width
        self.stride = stride
        self.phase = phase
        self.count = count
        self.pool = pool          # chunk name of the pool it points into
        self.key_phase = key_phase

    @property
    def fmt(self):
        return "<I" if self.width == 4 else "<Q"

    def read(self, payload):
        f = self.fmt
        return [struct.unpack_from(f, payload, self.phase + i * self.stride)[0]
                for i in range(self.count)]

    def read_keys(self, payload):
        if self.key_phase is None:
            return None
        f = self.fmt
        return [struct.unpack_from(f, payload, self.key_phase + i * self.stride)[0]
                for i in range(self.count)]

    def write(self, payload, values):
        f = self.fmt
        for i, v in enumerate(values):
            struct.pack_into(f, payload, self.phase + i * self.stride, v)

    def to_json(self):
        return {"width": self.width, "stride": self.stride, "phase": self.phase,
                "count": self.count, "pool": self.pool, "key_phase": self.key_phase}


class MtFile(object):
    def __init__(self, data, path=None):
        self.path = path
        self.size = len(data)
        if data[:8] != MT_MAGIC:
            raise MtError("not an <mt> container (magic %r)" % data[:8])
        self.prod = data[8:16]
        self.data_tag = data[16:24]
        self.version = data[24:32]
        self.hdr_a, self.hdr_b = struct.unpack_from("<II", data, 0x20)

        self.chunks = []
        off = HEADER_SIZE
        while data[off:off + 12] == TAG_CHUNK_HEAD:
            if data[off + 12:off + 16] != b"\0\0\0\0":
                raise MtError("chunk @%#x: unexpected bytes after head tag" % off)
            raw_name = data[off + 16:off + 24]
            c, d = struct.unpack_from("<II", data, off + 24)
            pstart = off + 32
            payload = data[pstart:pstart + d]
            foot = pstart + d
            if data[foot:foot + 12] != TAG_CHUNK_FOOT:
                raise MtError("chunk %r: missing <chunk-foot> @%#x" % (raw_name, foot))
            rec = u32(data, foot + 16)
            pad = _align(foot + 24, FOOT_ALIGN) - (foot + 24)
            eoc = foot + 24 + pad
            if data[eoc:eoc + 12] != TAG_END_CHUNK:
                raise MtError("chunk %r: missing <endofchunk> @%#x" % (raw_name, eoc))
            if rec != 12 + 12 + pad + 16:
                raise MtError("chunk %r: footer size %#x != %#x"
                              % (raw_name, rec, 12 + 12 + pad + 16))
            if off + c != foot + rec:
                raise MtError("chunk %r: C %#x inconsistent with footer" % (raw_name, c))
            self.chunks.append(Chunk(raw_name, off, payload, rec))
            off += c

        self.file_foot_off = off
        if data[off:off + 12] != TAG_FILE_FOOT:
            raise MtError("missing <file--foot> @%#x" % off)
        self.file_rec = u32(data, off + 16)
        # The file footer record is variable length: after the three u32 fields
        # some producers store a build-info string, then '*' padding, then the
        # '<end-of-mt>.' marker. Keep the whole trailer verbatim.
        self.trailer = data[off:]
        if TAG_END_OF_MT_CORE not in self.trailer:
            raise MtError("missing end-of-mt marker after <file--foot> @%#x" % off)

        # cross-checks on the two header words
        exp_b = self.file_foot_off - HEADER_SIZE
        exp_a = self.file_foot_off + self.file_rec
        self.hdr_ok = (self.hdr_b == exp_b and self.hdr_a == exp_a)

        self._classify()

    # ------------------------------------------------------------ analysis

    def _classify(self):
        pools = {}
        for ch in self.chunks:
            if looks_like_pool(ch.name, ch.payload):
                ch.kind = "pool"
                pools[ch.name] = set(o for o, _ in split_pool(ch.payload))
        self.pool_names = list(pools)
        for ch in self.chunks:
            if ch.kind == "pool":
                continue
            lanes = self._find_lanes(ch, pools)
            if lanes:
                ch.kind = "index"
                ch.lanes = lanes

    @staticmethod
    def _find_lanes(ch, pools):
        """Locate offset lanes in `ch`.

        Search order: wide slots first (u64 before u32), tight strides first.
        A lane is accepted only when *every* slot holds a valid string start
        and the lane is non-degenerate, which keeps id/handle tables (whose
        values merely happen to collide with a few string starts) opaque.
        """
        n = len(ch.payload)
        if n < 8:
            return []
        for width in (8, 4):
            if n % width:
                continue
            for stride in (width, 2 * width, 3 * width, 4 * width):
                if n % stride:
                    continue
                count = n // stride
                if count < 2:
                    continue
                hits = []
                for phase in range(0, stride, width):
                    vals = Lane(width, stride, phase, count, None).read(ch.payload)
                    nonzero = sum(1 for v in vals if v)
                    if nonzero * 2 < count:          # mostly zeros -> no evidence
                        continue
                    if len(set(v for v in vals if v)) < 4:
                        continue
                    for pname, starts in pools.items():
                        if all(v in starts for v in vals):
                            hits.append((phase, pname))
                            break
                if not hits:
                    continue
                lanes = []
                for phase, pname in hits:
                    key_phase = None
                    if stride == 2 * width and len(hits) == 1:
                        kp = 0 if phase else width
                        kvals = Lane(width, stride, kp, count, None).read(ch.payload)
                        if len(set(kvals)) == count and all(
                                v < (1 << (8 * width - 1)) for v in kvals):
                            key_phase = kp
                    lanes.append(Lane(width, stride, phase, count, pname, key_phase))
                return lanes
        return []

    # ------------------------------------------------------------ building

    def serialise(self, payloads=None):
        """Rebuild the whole container. `payloads` maps chunk index -> bytes."""
        payloads = payloads or {}
        out = bytearray()
        out += MT_MAGIC + self.prod + self.data_tag + self.version
        out += b"\0" * 8                       # A / B, patched at the end

        for i, ch in enumerate(self.chunks):
            payload = payloads.get(i, ch.payload)
            head = len(out)
            d = len(payload)
            foot = head + 32 + d
            pad = _align(foot + 24, FOOT_ALIGN) - (foot + 24)
            rec = 12 + 12 + pad + 16
            out += TAG_CHUNK_HEAD + b"\0" * 4 + ch.raw_name
            out += struct.pack("<II", (foot + rec) - head, d)
            out += payload
            out += TAG_CHUNK_FOOT
            out += struct.pack("<III", 0, rec, 0)
            out += bytes([PAD_BYTE]) * pad
            out += TAG_END_CHUNK + b"\0" * 4

        foot_off = len(out)
        out += self.trailer                    # opaque, variable length
        struct.pack_into("<II", out, 0x20,
                         foot_off + self.file_rec, foot_off - HEADER_SIZE)
        return bytes(out)

    # ------------------------------------------------------------ reporting

    def describe(self):
        cov = coverage(self)
        lines = ["%s  (%d bytes)" % (self.path or "<mem>", self.size),
                 "  prod=%r data=%r ver=%r" % (self.prod, self.data_tag, self.version),
                 "  A=%#x B=%#x  header consistent: %s" % (self.hdr_a, self.hdr_b, self.hdr_ok),
                 "  %d chunks:" % len(self.chunks)]
        for ch in self.chunks:
            extra = ""
            if ch.kind == "pool":
                extra = "  slots=%d  coverage=%.1f%%" % (
                    len(split_pool(ch.payload)), 100 * cov.get(ch.name, 0.0))
            for ln in ch.lanes:
                extra += "  lane(w=%d stride=%d phase=%d n=%d -> %s%s)" % (
                    ln.width, ln.stride, ln.phase, ln.count, ln.pool,
                    "" if ln.key_phase is None else " keys@%d" % ln.key_phase)
            lines.append("    %-10s D=%#-8x %-7s%s" % (ch.name, len(ch.payload), ch.kind, extra))
        return "\n".join(lines)


# ---------------------------------------------------------------- extract

def extract(mt):
    pool_chunks = [ch for ch in mt.chunks if ch.kind == "pool"]

    # references: (pool, offset) -> list of ids
    refs = {}
    for ch in mt.chunks:
        for ln in ch.lanes:
            vals = ln.read(ch.payload)
            keys = ln.read_keys(ch.payload)
            for i, v in enumerate(vals):
                rid = keys[i] if keys is not None else "%s[%d]" % (ch.name, i)
                refs.setdefault((ln.pool, v), []).append(rid)

    strings = []
    pools_meta = []
    for ch in pool_chunks:
        slots = split_pool(ch.payload)
        texts = set()
        for _, raw in slots:
            texts.add(raw)
        refd = set(o for (pn, o) in refs if pn == ch.name)
        refd_texts = set(raw for off, raw in slots if off in refd)
        pools_meta.append({
            "chunk": ch.name, "slots": len(slots), "bytes": len(ch.payload),
            "unique": len(texts),
            "referenced_slots": len(refd),
            "referenced_unique": len(refd_texts),
            # fraction of distinct strings reachable through a detected lane;
            # must be ~1.0 before it is safe to change string lengths
            "coverage": round(len(refd_texts) / max(1, len(texts)), 4),
        })
        groups = {}          # text -> record
        for si, (off, raw) in enumerate(slots):
            text = raw.decode("utf-8")
            rec = groups.get(text)
            if rec is None:
                rec = {"idx": len(strings), "pool": ch.name, "text": text,
                       "ids": [], "is_key": bool(KEY_RE.match(text)),
                       "slots": []}
                groups[text] = rec
                strings.append(rec)
            rec["slots"].append(si)
            rec["ids"].extend(refs.get((ch.name, off), []))

    meta = {
        "format": "srwv-mt/1",
        "source": os.path.basename(mt.path or ""),
        "size": mt.size,
        "pools": pools_meta,
        "chunks": [{"name": ch.name, "bytes": len(ch.payload), "kind": ch.kind,
                    "lanes": [ln.to_json() for ln in ch.lanes]}
                   for ch in mt.chunks],
        "translatable": sum(1 for s in strings if not s["is_key"] and s["text"]),
    }
    if not pool_chunks:
        meta["note"] = "no string pool in this container; nothing to translate"
    return {"meta": meta, "strings": strings}


def coverage(mt):
    """Per-pool fraction of distinct strings reachable through a detected lane."""
    out = {}
    for ch in mt.chunks:
        if ch.kind != "pool":
            continue
        slots = split_pool(ch.payload)
        refd = set()
        for other in mt.chunks:
            for ln in other.lanes:
                if ln.pool == ch.name:
                    refd.update(ln.read(other.payload))
        texts = set(raw for _, raw in slots)
        hit = set(raw for off, raw in slots if off in refd)
        out[ch.name] = len(hit) / max(1, len(texts))
    return out


def rebuild(mt, doc, force=False):
    strings = doc["strings"] if isinstance(doc, dict) else doc
    by_pool = {}
    for rec in strings:
        pool = rec.get("pool")
        if pool is None:
            pool = mt.pool_names[0]
        text = rec.get("text_ru") or rec.get("ru") or rec["text"]
        for si in rec["slots"]:
            by_pool.setdefault(pool, {})[si] = text.encode("utf-8")

    payloads = {}
    offmaps = {}
    for i, ch in enumerate(mt.chunks):
        if ch.kind != "pool":
            continue
        slots = split_pool(ch.payload)
        repl = by_pool.get(ch.name, {})
        missing = [si for si in range(len(slots)) if si not in repl]
        if missing and len(repl) != 0:
            # strings the JSON does not mention keep their original bytes
            pass
        records = [repl.get(si, raw) for si, (_, raw) in enumerate(slots)]
        new = join_pool(records)
        if new != ch.payload and not force:
            cov = coverage(mt).get(ch.name, 0.0)
            if cov < 0.95:
                raise MtError(
                    "refusing to resize pool %r: only %.1f%% of its strings are "
                    "reachable through a detected offset lane, so some table in "
                    "this container references them in a way this tool does not "
                    "understand and would be left stale. Re-run with force=True "
                    "only if you know the references are index-based."
                    % (ch.name, 100.0 * cov))
        payloads[i] = new
        omap = {}
        noff = 0
        for (ooff, _), raw in zip(slots, records):
            omap[ooff] = noff
            noff += len(raw) + 1
        offmaps[ch.name] = omap

    for i, ch in enumerate(mt.chunks):
        if not ch.lanes:
            continue
        buf = bytearray(ch.payload)
        for ln in ch.lanes:
            omap = offmaps[ln.pool]
            vals = ln.read(ch.payload)
            ln.write(buf, [omap[v] for v in vals])
        payloads[i] = bytes(buf)

    return mt.serialise(payloads)


# ---------------------------------------------------------------- probe

def probe_one(path):
    with open(path, "rb") as fh:
        head = fh.read(64)
        size = fh.seek(0, 2)
    if head[:8] == MT_MAGIC:
        return "mt", "<mt> container"
    if head[:8] == b"MTFLz2_2":
        return "mtfl", "MTFL binary table (ver %r)" % head[12:16]
    x = bytes(c ^ 0x5E for c in head[:8])
    if x == b"ZKANPDNM":
        return "zkan", "ZKANPDNM record, XOR 0x5E (DSIZ/DATA/DSCR tags)"
    if head[:4] in (b"CPK ",):
        return "cpk", "CRI CPK archive (extract first)"
    return "unknown", "unrecognised, first 8 bytes %r (%d bytes)" % (head[:8], size)


def cmd_probe(args):
    targets = []
    for a in args:
        if os.path.isdir(a):
            for root, _, files in os.walk(a):
                for f in sorted(files):
                    targets.append(os.path.join(root, f))
        else:
            targets.append(a)
    tally = {}
    for t in targets:
        kind, desc = probe_one(t)
        tally.setdefault(kind, []).append(t)
    for kind, files in sorted(tally.items()):
        print("%-8s %4d file(s)  %s" % (kind, len(files), probe_one(files[0])[1]))
        for f in files[:3]:
            print("           %s" % f)
        if len(files) > 3:
            print("           ... +%d more" % (len(files) - 3))
    return 0


# ---------------------------------------------------------------- cli

def load(path):
    with open(path, "rb") as fh:
        return MtFile(fh.read(), path)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]

    if cmd == "probe":
        return cmd_probe(argv[2:])

    if cmd == "info":
        print(load(argv[2]).describe())
        return 0

    if cmd == "extract":
        mt = load(argv[2])
        doc = extract(mt)
        with open(argv[3], "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=1)
        m = doc["meta"]
        print("%s: %d unique strings (%d translatable, %d key-like) -> %s"
              % (m["source"], len(doc["strings"]), m["translatable"],
                 sum(1 for s in doc["strings"] if s["is_key"]), argv[3]))
        for pm in m["pools"]:
            print("  pool %-10s slots=%-6d unique=%-6d lane coverage=%.1f%%%s"
                  % (pm["chunk"], pm["slots"], pm["unique"], 100 * pm["coverage"],
                     "" if pm["coverage"] >= 0.95 else "   <-- NOT SAFE TO RESIZE"))
        return 0

    if cmd == "rebuild":
        args = [a for a in argv[2:] if a != "--force"]
        force = "--force" in argv[2:]
        mt = load(args[0])
        with open(args[1], "r", encoding="utf-8") as fh:
            doc = json.load(fh)
        out = rebuild(mt, doc, force=force)
        with open(args[2], "wb") as fh:
            fh.write(out)
        print("wrote %s (%d bytes, was %d)" % (args[2], len(out), mt.size))
        return 0

    if cmd == "verify":
        ok = True
        for path in argv[2:]:
            with open(path, "rb") as fh:
                orig = fh.read()
            mt = MtFile(orig, path)
            same_raw = mt.serialise() == orig
            same_rt = rebuild(mt, extract(mt)) == orig
            ok = ok and same_raw and same_rt and mt.hdr_ok
            print("%-60s header=%s reserialise=%s roundtrip=%s"
                  % (os.path.basename(path), mt.hdr_ok, same_raw, same_rt))
        return 0 if ok else 1

    print("unknown command %r" % cmd)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except MtError as exc:
        sys.stderr.write("ru_mt_jstr: %s\n" % exc)
        sys.exit(1)
