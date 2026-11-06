#!/usr/bin/env python3
"""Patch values-sw600dp dimens in resources.arsc (compact 8-byte entries)."""
import struct, sys

PATH = 'unpack/resources.arsc'
d = bytearray(open(PATH, 'rb').read())

def u16(o): return struct.unpack_from('<H', d, o)[0]
def u32(o): return struct.unpack_from('<I', d, o)[0]

# --- locate package ---
tbl_size = u32(4)
pos, pkg = u16(2), None
while pos < tbl_size:
    ct, hs, cs = u16(pos), u16(pos+2), u32(pos+4)
    if cs == 0: break
    if ct == 0x0200:
        pkg = pos; break
    pos += cs

# --- string pools ---
def pool(base):
    hs = u16(base+2); cnt = u32(base+8); flags = u32(base+16)
    ss = u32(base+20); utf8 = bool(flags & 0x100)
    out = []
    for i in range(cnt):
        p = base + ss + u32(base + hs + 4*i)
        if utf8:
            n = d[p]; p += 1
            if n & 0x80: p += 1
            m = d[p]; p += 1
            if m & 0x80: m = ((m & 0x7f) << 8) | d[p]; p += 1
            out.append(d[p:p+m].decode('utf-8', 'replace'))
        else:
            n = u16(p); p += 2
            if n & 0x8000: n = ((n & 0x7fff) << 16) | u16(p); p += 2
            out.append(d[p:p+2*n].decode('utf-16-le', 'replace'))
    return out

keys = pool(pkg + u32(pkg + 276))
types = pool(pkg + u32(pkg + 268))

def cfg(base):
    size = u32(base)
    ori = d[base+12] if size > 12 else 0
    sw = struct.unpack_from('<H', d, base+30)[0] if size >= 32 else 0
    return ori, sw

# --- find sw600dp portrait dimen chunks ---
pos = pkg + u16(pkg+2); end = pkg + u32(pkg+4)
targets = []
while pos < end:
    ct, hs, cs = u16(pos), u16(pos+2), u32(pos+4)
    if cs == 0: break
    if ct == 0x0201 and d[pos+8] == 6:  # dimen
        ori, sw = cfg(pos+20)
        targets.append((pos, hs, ori, sw, d[pos+9],
                        u32(pos+12), u32(pos+16)))
    pos += cs

print(f"dimen chunks: {[(hex(t[0]), 'ori=%d'%t[2], 'sw=%d'%t[3]) for t in targets]}")

# what we want (target value in dp)
WANT = {
    'formula_padding_top': 16, 'formula_padding_bottom': 8,
    'formula_padding_start': 16, 'formula_padding_end': 16,
    'formula_min_textsize': 32, 'formula_max_textsize': 48,
    'result_padding_top': 8, 'result_padding_bottom': 16,
    'result_padding_start': 16, 'result_padding_end': 16,
    'result_textsize': 36,
}

changed = 0
for base, hs, ori, sw, flags, ec, es in targets:
    if sw != 600 or ori == 2:
        continue
    print(f"\n== chunk {hex(base)} sw={sw} ori={ori} entries={ec} ==")
    for i in range(ec):
        if flags & 0x02:
            off = u16(base + hs + 2*i)
            if off == 0xffff: continue
            eoff = off * 4
        else:
            eoff = u32(base + hs + 4*i)
            if eoff == 0xffffffff: continue
        eb = base + es + eoff
        keyidx = u16(eb)
        if keyidx >= len(keys): continue
        name = keys[keyidx]
        data = u32(eb + 4)
        val = data >> 8
        unit = data & 0xff
        if name in WANT:
            newdata = (WANT[name] << 8) | (unit if unit in (1, 2) else 1)
            print(f"  {name:30s} {val:>4} -> {WANT[name]:<4} (unit {unit})")
            struct.pack_into('<I', d, eb + 4, newdata)
            changed += 1

print(f"\npatched {changed}")
open(PATH, 'wb').write(d)
