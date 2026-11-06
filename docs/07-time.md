# 时间与时区自动确定失效

## 现象

- 时间偏差十几个小时；
- 时区落在 `Pacific/Midway`（GMT-11），界面显示成 `GMT-1` 之类的奇怪值；
- 开着「自动确定时间」「自动确定时区」，但永远不会自愈。

## 根因（两层，彼此独立）

### 1. NTP 服务器不可达

AOSP 默认 `ntp_server` 是 `ntp://time.android.com`，国内完全不通。
`dumpsys network_time_update_service` 会显示：

```
mTimeResult = null
refreshSuccessful = false
mTryAgainCounter = 3       ← 重试次数打满
```

系统因此一直沿用 RTC 里那个陈旧时间。同时 `ntp_server` 这个 setting **默认是空的**，
框架 fallback 到硬编码的 `time.android.com`——看起来"配了"，其实没配。

### 2. 时区根本没有输入来源

`TimeZoneDetectorService` 只有两条检测路径：

| 路径 | 状态 |
|---|---|
| telephony（NITZ） | `supported = true`，但无 SIM 卡，拿不到 NITZ |
| geo（位置） | `supported = false`，没有 location time zone provider |

两条全废 → suggestion history 全是 `{Empty}` → 时区停在一个 AOSP 兜底 ID 上
（本机落到 `Pacific/Midway`）。**这种情况下开着自动时区永远不会自愈。**

## 处理

```bash
# 1. NTP 换成境内服务器（必须带 ntp:// scheme）
adb shell "settings put global ntp_server 'ntp://ntp.aliyun.com'"
adb shell "cmd network_time_update_service force_refresh"     # 应打印 true

# 2. 关掉自动时区，钉死在 Asia/Shanghai
adb shell "cmd time_zone_detector set_auto_detection_enabled false"
adb shell "cmd alarm set-timezone 'Asia/Shanghai'"
```

脚本：[`tools/timefix.sh`](../tools/timefix.sh)（默认 `Asia/Shanghai`，可传参）。

### 两个必须知道的细节

1. **`ntp_server` 必须带 `ntp://` 前缀。** 只写 `ntp.aliyun.com` 会让 `Uri.getHost()`
   解析为空，同步必然失败，而且日志里看不出原因。

2. **改时区不能用 `setprop persist.sys.timezone`。** Java 层有缓存，
   `AlarmManager` 不会感知到变化。必须用 `cmd alarm set-timezone`。

3. `ntp.aliyun.com` 实测优于 `cn.pool.ntp.org`（后者偶尔轮询到境外节点）。

## 验证

```bash
adb shell "
  echo 时区     : \$(getprop persist.sys.timezone)
  echo 自动时区 : \$(settings get global auto_time_zone)   # 0
  echo 自动时间 : \$(settings get global auto_time)        # 1
  echo NTP      : \$(settings get global ntp_server)
  echo 设备时间 : \$(date)
"
date
```

本机重启后 **57 秒**完成 NTP 同步，时间与主机一致（`+0800`）。

`auto_time`（自动时间）保持开启——这条路修好了，该开着。
`auto_time_zone`（自动时区）关掉——这条路没有输入源，开着只会一直是错的。

## 恢复自动时区

插卡后 NITZ 可用，可以再打开：

```bash
adb shell cmd time_zone_detector set_auto_detection_enabled true
```
