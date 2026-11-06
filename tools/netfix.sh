#!/usr/bin/env bash
# 修复国行环境下 Android 提示"网络连接受限"的问题。
#
# 原理：AOSP 默认探针是
#   http  -> http://connectivitycheck.gstatic.com/generate_204
#   https -> https://www.google.com/generate_204
# 国内 http 那个常常能通（DNS 被解析到境内节点并返回 204），但 https 的 443 不通，
# 于是 NetworkMonitor 判定 isPartialConnectivity=true，网络被标记为
# PARTIAL_CONNECTIVITY，界面显示"连接受限"。
# 解决要点：两个探针都必须换成境内可达、且都能返回 204 的地址。
#
# 实测注意：这两个 URL 在 NetworkMonitor 构造时读入并缓存，
#   只改 settings 不生效；重启 com.android.networkstack.process 也不够，
#   必须让网络本身重建（断开重连）才会用新地址去验证。
#
# 用法: netfix.sh [SSID]
set -euo pipefail

A=${ADB:-adb}
HTTP='http://connectivitycheck.platform.hicloud.com/generate_204'
HTTPS='https://connectivitycheck.platform.hicloud.com/generate_204'
FALLBACK='http://connect.rom.miui.com/generate_204'
OTHER='http://wifi.vivo.com.cn/generate_204'
CFG=/data/misc/apexdata/com.android.wifi/WifiConfigStore.xml

$A wait-for-device

echo "[1/4] 写入境内验证地址"
$A shell "settings put global captive_portal_http_url '$HTTP'
          settings put global captive_portal_https_url '$HTTPS'
          settings put global captive_portal_fallback_url '$FALLBACK'
          settings put global captive_portal_other_fallback_urls '$OTHER'"

echo "[2/4] 检查探针可达性（都应为 204）"
$A shell "for u in '$HTTP' '$HTTPS'; do printf '%-58s ' \"\$u\"; curl -s -o /dev/null -w '%{http_code}\n' --max-time 6 \"\$u\"; done"

echo "[3/4] 重建网络以触发重新验证"
SSID=${1:-$($A shell "cmd wifi status 2>/dev/null | grep -o '\"[^\"]*\"' | head -1" | tr -d '\r"')}
if [ -z "$SSID" ]; then
  echo "  !! 读不到当前 SSID，请在手机上手动画一下 Wi-Fi"
  exit 1
fi
echo "  目标网络: $SSID"

PSK=$($A shell "grep -o '<string name=\"PreSharedKey\">[^<]*' $CFG | head -1 | sed 's/.*>//; s/&quot;/\"/g; s/^\"//; s/\"\$//'" | tr -d '\r')
if [ -n "$PSK" ]; then
  $A shell "cmd wifi connect-network '$SSID' wpa2 '$PSK' -p" >/dev/null
else
  $A shell "cmd wifi connect-network '$SSID' open" >/dev/null
fi

echo "[4/4] 等待验证"
for i in $(seq 1 12); do
  sleep 5
  if $A shell "dumpsys connectivity 2>/dev/null | grep -q 'Capabilities:.*VALIDATED'" 2>/dev/null; then
    echo "  -> 已 VALIDATED（不再提示连接受限）"
    break
  fi
  echo "  等待中 $i/12 ..."
done
$A shell "logcat -d 2>/dev/null | grep 'isCaptivePortal' | tail -2 | cut -c1-160"
