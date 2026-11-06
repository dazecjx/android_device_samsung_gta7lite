# 功能验收记录（12 项）

全部在真机 SM-T225 上实测，系统 `lineage_gta7lite 22.2 userdebug`，SELinux Enforcing。

| # | 项目 | 结果 | 证据 |
|---|---|---|---|
| 1 | 开机到桌面 | ✅ | `sys.boot_completed=1`，正常进入 Launcher |
| 2 | 触摸 | ✅ | `sec_touchscreen` 多点触控在位，`ABS_MT_POSITION` 范围 0-799 × 0-1339，与分辨率匹配 |
| 3 | Wi-Fi | ✅ | `VALIDATED`，11ac 5GHz / 390Mbps / RSSI -58 |
| 4 | 蓝牙 | ✅ | 扫描到 12+ 设备（BLE + 经典），固件加载正常，MAC 有效 |
| 5 | 扬声器 | ✅ | 铃声预览 `MediaPlayer state:started`，输出 `deviceIds:[2]` = SPEAKER |
| 6 | SD 卡 | ✅ | exFAT 自动挂载（`7ACF-0D0D`），32MB 写 189MB/s，md5 校验通过 |
| 7 | 充电 / 电量 | ✅ | 79%，USB powered，温度 28℃ |
| 8 | 息屏 / 唤醒 | ✅ | `Asleep` → `Awake` |
| 9 | 亮度调节 | ✅ | 102 → 20 → 128 均生效 |
| 10 | 相机 | ✅ | 前后摄 metadata 123 项完整，实拍 3.1MB / 3264×2448 JPEG |
| 11 | 插卡 / 通话 | ⏸ | **无 SIM 卡，无法验证** |
| 12 | 重启后状态 | ⚠️ | 见下 |

## 补充验证

| 项 | 结果 |
|---|---|
| modem 自动启动 | ✅ `md1:4`，两次冷启动均无需手动干预 |
| rild 稳定性 | ✅ `running`，pid 连续 50 秒不变 |
| rild SELinux 拒绝 | ✅ 0 条 |
| RIL 真实数据 | ✅ `OPERATOR {, , 46000}`、`cellIdentity={gsm:{mcc=460,lac=9729,cid=503}}` |
| 计算器竖屏显示 | ✅ 修复后长短算式、横竖屏均正常 |
| 时间 / 时区 | ✅ `+0800`，重启后 57 秒 NTP 同步成功 |

## 第 12 项：重启验证的说明

一次自动化重启测试中，设备重启后停在 bootloader 的 **download 模式**
（USB `04e8:685d`，Vendor Specific 接口），adb 不可用，需要物理长按电源键强制断电。

两个怀疑方向：

1. **音量下键被保护壳卡住**——重启瞬间检测到 VOL_DOWN 会进 download 模式，这是最常见原因；
2. 该轮测试前曾 `adb remount` 把 `/product` 挂成 rw 并覆盖了计算器 APK。
   但 `adb remount` 当时明确提示 `AVB verification is disabled`，dm-verity 本就没开，
   理论上不影响启动。

冷启动（完全断电再开机）本身多次验证正常，未复现该问题。这一项待复测后更新。

## 排查中的两个假警报（值得记住）

### 截图全黑 ≠ 相机坏

真正原因是设备停在**锁屏**（`uiautomator` 里 `content-desc="锁定的屏幕"`）。
测完息屏唤醒后没解锁，`screencap` 自然是黑的。
**以后截图前先确认 `isKeyguardShowing`。**

### `Access Denial: can't use the camera from an idle UID`

adb 直接 `am start` 拉起的 app 会被 App Standby 判成 idle，CameraService 拒绝。
解法：`adb shell cmd deviceidle whitelist +org.lineageos.aperture`。

另外 `camera_metadata: metadata is null!` 是关 session 时的无害日志，别看它误判 HAL。
判断 HAL 好坏要看 `dumpsys media.camera` 里 `API2 camera characteristics` 的条目数。
