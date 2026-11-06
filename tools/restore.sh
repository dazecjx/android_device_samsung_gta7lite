#!/usr/bin/env bash
# 回滚 gta7lite 的 rild SELinux 策略改动。
# 用法: restore.sh    （设备需已连接且 adb root 可用）
set -euo pipefail

A=${ADB:-adb}
BK=/data/local/tmp/sepolicy-backup

echo "[1/4] 检查设备"
$A wait-for-device
$A root >/dev/null 2>&1 || true
sleep 4
$A kill-server >/dev/null 2>&1 || true
sleep 1
$A start-server >/dev/null 2>&1 || true
sleep 3

echo "[2/4] 恢复预编译策略"
$A shell "mount -o remount,rw /odm; \
  if [ -f $BK/precompiled_sepolicy ]; then \
    mv -f /odm/etc/selinux/precompiled_sepolicy.disabled \
          /odm/etc/selinux/precompiled_sepolicy.disabled.bak 2>/dev/null || true; \
    cp -f $BK/precompiled_sepolicy /odm/etc/selinux/precompiled_sepolicy; \
    echo '  已恢复 precompiled_sepolicy'; \
  else echo '  !! 备份缺失'; fi"

echo "[3/4] 恢复 vendor 策略与上下文"
$A shell "mount -o remount,rw /vendor; \
  cp -f $BK/vendor_sepolicy.cil /vendor/etc/selinux/vendor_sepolicy.cil; \
  cp -f $BK/vendor_file_contexts /vendor/etc/selinux/vendor_file_contexts; \
  restorecon /vendor/etc/selinux/vendor_sepolicy.cil /vendor/etc/selinux/vendor_file_contexts; \
  sync"

echo "[4/4] 重启"
$A reboot
echo "完成，请等待设备重启。"
