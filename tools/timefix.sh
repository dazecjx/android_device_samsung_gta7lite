#!/usr/bin/env bash
# 修复国行环境下 Android 时间/时区自动确定失效的问题。
#
# 症状：时间偏差十几小时，时区落在 Pacific/Midway（GMT-11），
#       界面时区显示 GMT-1 之类的奇怪值。
#
# 根因有两层，彼此独立：
#
# 1) NTP 服务器不可达
#    AOSP 默认 ntp_server 是 ntp://time.android.com，国内完全不通。
#    dumpsys network_time_update_service 会显示 mTimeResult=null、
#    refreshSuccessful=false、mTryAgainCounter 打满。
#    系统因此一直沿用 RTC 里那个陈旧时间。
#
# 2) 时区根本没有输入来源，只能停在兜底值
#    - telephony 检测：supported=true，但设备无 SIM 卡，拿不到 NITZ
#    - geo 检测：supported=false（没有 location time zone provider）
#    两条路径全废，TimeZoneDetectorService 的 suggestion history 一片 {Empty}，
#    于是时区停留在一个 AOSP 兜底 ID 上（本机是 Pacific/Midway = GMT-11）。
#    这种情况下开着"自动确定时区"永远不会自愈，只会一直错。
#
# 处理：NTP 换成境内服务器（自动时间继续开，因为这条路修好了），
#       自动时区关掉并钉在 Asia/Shanghai（因为这条路没法修）。
#       以后插了 SIM 卡、NITZ 可用时，可以再打开自动时区。
#
# 用法: timefix.sh [时区ID]
#   默认 Asia/Shanghai
set -euo pipefail

A=${ADB:-adb}
TZID=${1:-Asia/Shanghai}
# 阿里云 NTP 实测优于 cn.pool.ntp.org（后者偶尔轮询到境外节点）
NTP='ntp://ntp.aliyun.com'

$A wait-for-device

echo "[0/4] 获取 root"
$A root >/dev/null 2>&1 || true
sleep 3
$A kill-server >/dev/null 2>&1 || true
sleep 1
$A start-server >/dev/null 2>&1 || true
sleep 3
$A wait-for-device

echo "[1/4] 写入境内 NTP 服务器: $NTP"
# 必须带 ntp:// scheme，否则 Uri.getHost() 解析为空，同步必然失败
$A shell "settings put global ntp_server '$NTP'"

echo "[2/4] 立即强制同步一次"
# force_refresh 会打印 true/false，需要 root 才稳
RES=$($A shell "cmd network_time_update_service force_refresh" | tr -d '\r')
echo "      NTP 同步结果: $RES"
if [ "$RES" != "true" ]; then
  echo "      !! 同步失败。先确认网络可用，或换个服务器：" >&2
  echo "         ntp://cn.pool.ntp.org / ntp://time1.cloud.tencent.com" >&2
fi

echo "[3/4] 关闭自动时区并设定为 $TZID"
$A shell "cmd time_zone_detector set_auto_detection_enabled false"
$A shell "cmd alarm set-timezone '$TZID'"
sleep 2

echo "[4/4] 校验"
$A shell "
  echo '  时区     : '\$(getprop persist.sys.timezone)
  echo '  自动时区 : '\$(settings get global auto_time_zone)'  (0=关)'
  echo '  自动时间 : '\$(settings get global auto_time)'  (1=开)'
  echo '  NTP      : '\$(settings get global ntp_server)
  echo '  设备时间 : '\$(date)
"
echo "  主机时间 : $(date)"

echo
echo "如需恢复自动时区（插卡后 NITZ 可用时）:"
echo "  $A shell cmd time_zone_detector set_auto_detection_enabled true"
