# Wi-Fi 显示「网络连接受限」

## 现象

Wi-Fi 已连上、能正常上网（浏览器、下载都没问题），但状态栏与设置里持续提示
「网络连接受限」，下拉通知也一直在。

## 根因

AOSP 的网络验证靠 `NetworkMonitor` 打两个探针：

| 探针 | 默认地址 | 国内实际 |
|---|---|---|
| HTTP | `http://connectivitycheck.gstatic.com/generate_204` | 常能通（DNS 解析到境内节点，返回 204）|
| HTTPS | `https://www.google.com/generate_204` | **443 超时** |

`isPartialConnectivity()` 的判断是"HTTP 通、HTTPS 不通" → 判定为 `PARTIAL_CONNECTIVITY`
→ 界面显示「连接受限」。

所以这不是设备问题，是探针地址在境内不可达。

## 修复

四个 global settings 全部换成境内可达、且**能返回 204** 的地址：

```bash
adb shell "settings put global captive_portal_http_url  'http://connectivitycheck.platform.hicloud.com/generate_204'"
adb shell "settings put global captive_portal_https_url 'https://connectivitycheck.platform.hicloud.com/generate_204'"
adb shell "settings put global captive_portal_fallback_url 'http://connect.rom.miui.com/generate_204'"
adb shell "settings put global captive_portal_other_fallback_urls 'http://wifi.vivo.com.cn/generate_204'"
```

先确认探针本身可达（都应是 204）：

```bash
adb shell "curl -s -o /dev/null -w '%{http_code}\n' https://connectivitycheck.platform.hicloud.com/generate_204"
```

## 关键坑：改完设置不生效

**这两个 URL 在 `NetworkMonitor` 构造时读入并缓存**。只改 settings 不生效；
重启 `com.android.networkstack.process` 也不够。必须让**网络本身重建**才会用新地址去验证：

```bash
# 断开再连（不要只 toggle wifi，要真的 disconnect + connect）
adb shell "cmd wifi connect-network '<SSID>' wpa2 '<PSK>' -p"
```

脚本 [`tools/netfix.sh`](../tools/netfix.sh) 把这一整套做完了，包括从
`WifiConfigStore.xml` 里静默取 PSK（不打印明文）后重连、轮询 `VALIDATED`。

```bash
./tools/netfix.sh            # 自动读当前 SSID
./tools/netfix.sh MyWiFi     # 指定 SSID
```

## 结果

`dumpsys connectivity` 里该网络带 `VALIDATED`，提示消失：

```
NetworkAgentInfo{... WIFI ...}
  Capabilities: INTERNET&NOT_RESTRICTED&TRUSTED&NOT_VPN&VALIDATED ...
```

## 备注

- 本机 Wi-Fi **不会自动回连**（忘记网络后需手动连一次），脚本里已用
  `cmd wifi connect-network` 代劳。
- 想恢复 Google 探针（在能直连的环境下）：把四个 settings 删掉即可
  （`settings delete global captive_portal_https_url`），重启网络生效。
