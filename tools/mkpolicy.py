#!/usr/bin/env python3
"""生成 gta7lite 的 rild 策略补丁。

用法: mkpolicy.py <enumerate|final>

enumerate: 把 rild 域设为 permissive，用于一次性枚举全部拒绝记录
final    : 移除 permissive，改为精确的 allow 规则
"""
import sys, os

BASE = os.path.dirname(os.path.abspath(__file__))
CIL_ORIG = os.path.join(BASE, 'vendor_sepolicy.cil.orig')
FC_ORIG = os.path.join(BASE, 'vendor_file_contexts.orig')
CIL_OUT = os.path.join(BASE, 'vendor_sepolicy.cil')
FC_OUT = os.path.join(BASE, 'vendor_file_contexts')

# rild 需要的精确授权（依据实际 avc 拒绝记录）
FINAL_RULES = [
    # 属性读取：SELinux 无法区分单个属性，只能按属性文件类型授权
    '(allow rild default_prop_202404 (file (read open getattr map)))',
    '(allow rild system_prop_202404 (file (read open getattr map)))',
    # libsec-ril 通过 toybox 执行外部命令
    '(allow rild toolbox_exec_202404 (file (read open getattr map execute execute_no_trans entrypoint)))',
    '(allow rild vendor_toolbox_exec (file (read open getattr map execute execute_no_trans entrypoint)))',
]

BEGIN = ';;===AID-RILD-BEGIN==='
END = ';;===AID-RILD-END==='

# /dev/umts_boot0 在 Lineage 的 file_contexts 中完全缺失，落到了通用 device 类型
# 原厂用的是 radio_device，rild 对该类型已有完整 chr_file 权限
FC_EXTRA = [
    '/dev/umts_boot0\t\tu:object_r:radio_device:s0',
]


def build_cil(mode):
    with open(CIL_ORIG) as f:
        body = f.read()
    lines = [BEGIN, ';; gta7lite: 恢复 rild 在 enforcing 下的运行能力']
    if mode == 'enumerate':
        lines.append(';; 诊断阶段：仅让 rild 域宽容，其余域仍强制')
        lines.append('(typepermissive rild)')
    elif mode == 'final':
        lines.append(';; 依据实际 avc 记录逐条放行')
        lines.extend(FINAL_RULES)
    else:
        raise SystemExit('mode 必须是 enumerate 或 final')
    lines.append(END)
    with open(CIL_OUT, 'w') as f:
        f.write(body)
        if not body.endswith('\n'):
            f.write('\n')
        f.write('\n'.join(lines) + '\n')


def build_fc():
    with open(FC_ORIG) as f:
        body = f.read()
    with open(FC_OUT, 'w') as f:
        f.write(body)
        if not body.endswith('\n'):
            f.write('\n')
        f.write('# gta7lite: missing context for umts_boot0\n')
        f.write('\n'.join(FC_EXTRA) + '\n')


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'enumerate'
    build_cil(mode)
    build_fc()
    print(f'mode={mode}')
    print(f'  {CIL_OUT}: +{len(FINAL_RULES) if mode=="final" else 1} 条语句')
    print(f'  {FC_OUT}: +{len(FC_EXTRA)} 条上下文')
