#!/usr/bin/env python3
"""
在 telephony-common.jar 的 classes.dex 中修正 HIDL getService 的阻塞调用。

本机 libsec-ril 只注册到 radio@1.5 / radio.config@1.1，而框架默认用
getService(name, true)（无限等待）去取更高版本，导致 phone 进程永久阻塞。

策略：
  1) 能找到 const/4 vX, #1 的，直接改成 #0，让 HIDL 立即抛
     NoSuchElementException，走框架自带的版本回退链；
  2) 常量被 R8 优化掉找不到的，把调用目标重定向到低版本，并同步
     修正写入 mHalVersion 的版本字段，避免 setHidl 版本错位。
"""
import struct, sys, zipfile, hashlib, zlib

def uleb(data, off):
    result = 0; shift = 0
    while True:
        b = data[off]; off += 1
        result |= (b & 0x7f) << shift
        if not (b & 0x80): break
        shift += 7
    return result, off

class Dex:
    def __init__(self, buf):
        self.b = buf
        h = lambda o: struct.unpack_from('<I', buf, o)[0]
        self.string_ids_size = h(56); self.string_ids_off = h(60)
        self.type_ids_off   = h(68)
        self.method_ids_size = h(88); self.method_ids_off = h(92)
        self.field_ids_size = h(80);  self.field_ids_off = h(84)
        self.class_defs_size = h(96); self.class_defs_off = h(100)

    def string(self, idx):
        off = struct.unpack_from('<I', self.b, self.string_ids_off + idx*4)[0]
        n, p = uleb(self.b, off)
        end = self.b.index(b'\x00', p)
        return self.b[p:end].decode('utf-8', 'replace')

    def type(self, idx):
        return self.string(struct.unpack_from('<I', self.b, self.type_ids_off + idx*4)[0])

    def method(self, idx):
        cls, proto, name = struct.unpack_from('<HHI', self.b, self.method_ids_off + idx*8)
        return self.type(cls), self.string(name), proto

    def field(self, idx):
        cls, typ, name = struct.unpack_from('<HHI', self.b, self.field_ids_off + idx*8)
        return self.type(cls), self.type(typ), self.string(name)

    def methods_of_class(self, want_cls):
        out = []
        for ci in range(self.class_defs_size):
            base = self.class_defs_off + ci*32
            cls_idx = struct.unpack_from('<I', self.b, base)[0]
            if self.type(cls_idx) != want_cls:
                continue
            cdata = struct.unpack_from('<I', self.b, base+24)[0]
            if cdata == 0: continue
            p = cdata
            sf, p = uleb(self.b, p); inf, p = uleb(self.b, p)
            dm, p = uleb(self.b, p); vm, p = uleb(self.b, p)
            for _ in range(sf+inf):
                _, p = uleb(self.b, p); _, p = uleb(self.b, p)
            for count in (dm, vm):
                midx = 0
                for _ in range(count):
                    diff, p = uleb(self.b, p)
                    acc, p = uleb(self.b, p)
                    code, p = uleb(self.b, p)
                    midx += diff
                    _, name, _ = self.method(midx)
                    if code: out.append((midx, code, name))
        return out

def main():
    jar = sys.argv[1]
    z = zipfile.ZipFile(jar)
    dex = bytearray(z.read('classes.dex'))
    d = Dex(bytes(dex))

    RIL = 'Lcom/android/internal/telephony/RIL;'
    RC  = 'Lcom/android/internal/telephony/RadioConfig;'

    # 各目标的 HIDL getService method_idx
    def mids_of(descriptor, name='getService'):
        return {i for i in range(d.method_ids_size)
                if d.method(i)[0] == descriptor and d.method(i)[1] == name}

    v16 = mids_of('Landroid/hardware/radio/V1_6/IRadio;')
    v15 = mids_of('Landroid/hardware/radio/V1_5/IRadio;')
    cfg13 = mids_of('Landroid/hardware/radio/config/V1_3/IRadioConfig;')
    cfg11 = mids_of('Landroid/hardware/radio/config/V1_1/IRadioConfig;')
    print(f'[i] radio V1_6={sorted(v16)} V1_5={sorted(v15)} '
          f'config V1_3={sorted(cfg13)} V1_1={sorted(cfg11)}')

    # RIL.RADIO_HAL_VERSION_1_5 / _1_6 的 field_idx
    ver_field = {}
    for fi in range(d.field_ids_size):
        nm = d.field(fi)[2]
        if nm == 'RADIO_HAL_VERSION_1_5': ver_field['1.5'] = fi
        elif nm == 'RADIO_HAL_VERSION_1_6': ver_field['1.6'] = fi
    print(f'[i] 版本字段 1.5={ver_field.get("1.5")} 1.6={ver_field.get("1.6")}')

    # (类, 方法名, 待处理的 getService idx 集合, 可重定向到的替代 idx)
    PLAN = [
        (RIL, 'getRadioProxy',        v16,  sorted(v15)[0] if v15 else None),
        (RIL, 'getRadioServiceProxy', v16,  sorted(v15)[0] if v15 else None),
        (RC,  'updateRadioConfigProxy', cfg13, sorted(cfg11)[0] if cfg11 else None),
    ]

    patched = 0
    for cls, mname, mids, fallback in PLAN:
        for mid, code_off, name in d.methods_of_class(cls):
            if name != mname:
                continue
            dbg, insns_size = struct.unpack_from('<II', dex, code_off+8)
            base = code_off + 16
            print(f'[i] {cls.split("/")[-1]}.{name}: insns={insns_size}')
            i = 0
            while i < insns_size:
                unit = struct.unpack_from('<H', dex, base + i*2)[0]
                if (unit & 0xff) == 0x71 and i+1 < insns_size:
                    idx = struct.unpack_from('<H', dex, base + (i+1)*2)[0]
                    if idx in mids:
                        hit = None
                        for j in range(i-1, max(-1, i-20), -1):
                            u = struct.unpack_from('<H', dex, base + j*2)[0]
                            if (u & 0xff) == 0x12:
                                a = (u >> 8) & 0xf
                                bval = (u >> 12) & 0xf
                                if bval == 1:
                                    hit = (j, a, u)
                                break
                        if hit:
                            j, a, u = hit
                            newu = u & 0x0fff
                            struct.pack_into('<H', dex, base + j*2, newu)
                            print(f'    invoke@{i}: const/4 v{a},#1 @{j} '
                                  f'0x{u:04x} -> 0x{newu:04x}')
                            patched += 1
                        elif fallback is not None:
                            struct.pack_into('<H', dex, base + (i+1)*2, fallback)
                            print(f'    invoke@{i}: 实参不可改，重定向 {idx} -> {fallback}')
                            patched += 1
                            for j in range(i-1, max(-1, i-80), -1):
                                uj = struct.unpack_from('<H', dex, base + j*2)[0]
                                if (uj & 0xff) == 0x62:
                                    fidx = struct.unpack_from('<H', dex, base + (j+1)*2)[0]
                                    if fidx != ver_field.get('1.6'):
                                        continue
                                    struct.pack_into('<H', dex, base + (j+1)*2,
                                                     ver_field['1.5'])
                                    print(f'    sget-object@{j}: 版本 '
                                          f'{ver_field["1.6"]} -> {ver_field["1.5"]}')
                                    break
                        else:
                            print(f'    invoke@{i}: 无可改项（idx={idx}）')
                i += 1

    print(f'[=] 共修补 {patched} 处')

    if patched:
        sig = hashlib.sha1(bytes(dex[32:])).digest()
        dex[12:32] = sig
        csum = zlib.adler32(bytes(dex[12:])) & 0xffffffff
        struct.pack_into('<I', dex, 8, csum)
        out = jar.replace('.jar', '.patched.jar')
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zo:
            for item in z.infolist():
                data = bytes(dex) if item.filename == 'classes.dex' else z.read(item.filename)
                zo.writestr(item, data)
        print(f'[+] 输出 {out}  checksum=0x{csum:08x}')

if __name__ == '__main__':
    main()
