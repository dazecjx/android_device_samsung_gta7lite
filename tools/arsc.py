#!/usr/bin/env python3
"""Minimal resources.arsc parser/patcher for values-sw600dp dimen tuning."""
import struct, sys

class ARSC:
    def __init__(self, path):
        self.data = bytearray(open(path, 'rb').read())
        self.packages = []
        self._parse()

    def u16(self, o): return struct.unpack_from('<H', self.data, o)[0]
    def u32(self, o): return struct.unpack_from('<I', self.data, o)[0]

    def strpool(self, base):
        """Return list of strings in a ResStringPool at base."""
        assert self.u16(base) == 0x0001, "not a string pool"
        hsize = self.u16(base + 2)
        count = self.u32(base + 8)
        flags = self.u32(base + 16)
        strings_start = self.u32(base + 20)
        utf8 = bool(flags & 0x100)
        offs = [self.u32(base + hsize + 4 * i) for i in range(count)]
        out = []
        for off in offs:
            p = base + strings_start + off
            if utf8:
                # utf16 length (varint), then utf8 length (varint)
                n = self.data[p]; p += 1
                if n & 0x80: p += 1
                m = self.data[p]; p += 1
                if m & 0x80:
                    m = ((m & 0x7f) << 8) | self.data[p]; p += 1
                out.append(self.data[p:p+m].decode('utf-8', 'replace'))
            else:
                n = self.u16(p); p += 2
                if n & 0x8000:
                    n = ((n & 0x7fff) << 16) | self.u16(p); p += 2
                out.append(self.data[p:p+2*n].decode('utf-16-le', 'replace'))
        return out

    def _parse(self):
        assert self.u16(0) == 0x0002, "not a resource table"
        table_size = self.u32(4)
        pos = self.u16(2)
        while pos < table_size:
            ctype, hsize, csize = self.u16(pos), self.u16(pos + 2), self.u32(pos + 4)
            if csize == 0: break
            if ctype == 0x0200:
                self.packages.append(pos)
            pos += csize

    def cfg_desc(self, cbase):
        size = self.u32(cbase)
        def get16(o): return struct.unpack_from('<H', self.data, cbase + o)[0] if size >= o + 2 else 0
        parts = []
        mcc = get16(4)
        if mcc: parts.append(f"mcc{mcc}")
        mnc = get16(6)
        if mnc: parts.append(f"mnc{mnc}")
        lang = self.data[cbase+8:cbase+10]
        if lang[0]:
            parts.append(lang.decode('ascii', 'replace'))
        dens = get16(14)
        if dens: parts.append(f"{dens}dpi")
        sw = get16(30)
        if sw: parts.append(f"sw{sw}dp")
        w = get16(32)
        if w: parts.append(f"w{w}dp")
        h = get16(34)
        if h: parts.append(f"h{h}dp")
        return '+'.join(parts) or 'default'

    def dimen_entries(self):
        """Yield (cfg_base, cfg_desc, entry_offset_pos, value_data_pos, name, value)."""
        for pkg in self.packages:
            type_strings = pkg + self.u32(pkg + 268)
            key_strings = pkg + self.u32(pkg + 276)
            tnames = self.strpool(type_strings)
            knames = self.strpool(key_strings)
            pos = pkg + self.u16(pkg + 2)
            pkg_end = pkg + self.u32(pkg + 4)
            while pos < pkg_end:
                ctype, hsize, csize = self.u16(pos), self.u16(pos + 2), self.u32(pos + 4)
                if csize == 0: break
                if ctype == 0x0201:  # RES_TABLE_TYPE_TYPE
                    type_id = self.data[pos + 8]
                    flags = self.data[pos + 9]
                    entry_count = self.u32(pos + 12)
                    entries_start = self.u32(pos + 16)
                    cfg_base = pos + 20
                    if type_id - 1 < len(tnames) and tnames[type_id - 1] == 'dimen':
                        if flags & 0x01:
                            # sparse
                            ents = [(self.u16(pos+hsize+4*i), self.u16(pos+hsize+4*i+2))
                                    for i in range(entry_count)]
                        elif flags & 0x02:
                            # offset16
                            ents = [(i, struct.unpack_from('<H', self.data, pos+hsize+2*i)[0])
                                    for i in range(entry_count)]
                        else:
                            ents = [(i, self.u32(pos+hsize+4*i)) for i in range(entry_count)]
                        for idx, eoff in ents:
                            if eoff == 0xFFFFFFFF or eoff == 0xFFFF: continue
                            ebase = pos + entries_start + eoff
                            esize = self.u16(ebase)
                            eflags = self.u16(ebase + 2)
                            key = self.u32(ebase + 4)
                            if eflags & 0x0001: continue  # complex
                            vpos = ebase + esize
                            dtype = self.data[vpos + 3]
                            data = self.u32(vpos + 4)
                            if dtype == 0x05:  # TYPE_DIMENSION
                                val = struct.unpack('<f', struct.pack('<I', data))[0]
                                yield (self.cfg_desc(cfg_base), data, vpos + 4, knames[key], val)
                pos += csize

def main():
    path = sys.argv[1]
    a = ARSC(path)
    mode = sys.argv[2] if len(sys.argv) > 2 else 'dump'
    if mode == 'dump':
        cur = None
        for desc, raw, pos, name, val in a.dimen_entries():
            if desc != cur:
                print(f"\n--- config: {desc} ---")
                cur = desc
            print(f"  {name:32s} = {val:g}")
    else:
        # patch <name> <value> [config_substring]
        name, value = sys.argv[3], float(sys.argv[4])
        cfgs = sys.argv[5] if len(sys.argv) > 5 else 'sw600dp'
        n = 0
        for desc, raw, pos, kname, val in a.dimen_entries():
            if kname == name and cfgs in desc and abs(val - value) > 1e-6:
                struct.pack_into('<f', a.data, pos, value)
                print(f"patched {desc} {name}: {val:g} -> {value:g}")
                n += 1
        open(path, 'wb').write(a.data)
        print(f"done, {n} patch(es)")

if __name__ == '__main__':
    main()
