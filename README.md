# android_device_samsung_gta7lite

Samsung Galaxy Tab A7 Lite **LTE (SM-T225)** 的 LineageOS 22.2 设备树，从同代的
Wi-Fi 版 `gta7litewifi` (SM-T220) 派生，并把「有 modem、有 SIM」这条线完整打通。

本仓库除设备树本身，还附带移植过程中的**排障记录与工具脚本**（`docs/`、`tools/`）——
这台机器的坑集中在 MTK 的 CCCI/modem 层与 SELinux 标签上，记录下来比只留代码更有用。

## 设备规格

| 项 | 值 |
|---|---|
| 型号 | SM-T225（Galaxy Tab A7 Lite LTE） |
| SoC | MediaTek MT6765 (Helio P22T) |
| 屏幕 | 8.7" 1340×800，密度 213 |
| 出厂系统 | Android 11（`UP1A.231005.007` / `T225XXU…`） |
| 目标系统 | LineageOS 22.2（Android 15） |
| 分区 | A-only，动态分区（super），`system`/`vendor`/`product` 均为 ext4 |
| 加密 | FBE（file-based encryption） |

## 当前状态

| 功能 | 状态 | 备注 |
|---|---|---|
| 编译 / 刷机 / 开机 | ✅ | 可正常进桌面 |
| 触摸 | ✅ | `sec_touchscreen`，多点触控 |
| Wi-Fi | ✅ | 2.4G/5G 均可，11ac 握手正常 |
| 蓝牙 | ✅ | BLE + 经典蓝牙，可扫描配对 |
| 音频输出 | ✅ | 扬声器 / 耳机切换正常 |
| 相机 | ✅ | 前后摄，3264×2448 JPEG |
| SD 卡 | ✅ | exFAT 自动挂载，写入 ~190MB/s |
| 充电 / 电量 | ✅ | USB / AC 均识别 |
| 亮度 / 息屏唤醒 | ✅ | |
| **modem / RIL** | ✅ | `md1:4`，rild 稳定运行，可读到真实 MCC/LAC/CID；**插卡实测未做（无 SIM 卡）** |
| 指纹 / 虹膜 | — | 本机型无此硬件 |
| VoLTE / 通话 | ⏸ | 依赖插卡验证 |

## 与 Wi-Fi 版（gta7litewifi）的关键差异

移植 LTE 版最容易踩的坑，就是直接套用 Wi-Fi 版设备树——包能编、能开机，但插卡毫无信号，
且**没有任何报错**。四处必须改：

| # | 位置 | Wi-Fi 版 | LTE 版 | 后果 |
|---|---|---|---|---|
| 1 | `lineage_gta7lite.mk` | `common_full_tablet_wifionly.mk` | `common_full_tablet.mk` | 无电话 UI |
| 2 | `device.mk` | `TARGET_IS_WIFI-ONLY := true` | `false` | `mt6765.mk` 用 `ifneq` 把整个 RIL 栈排除 |
| 3 | `BoardConfig.mk` | `gta7litewifi_defconfig` | `gta7lite_defconfig` | 内核缺 modem/CCCI 配置 |
| 4 | `vendor.prop` | `ro.carrier=wifi-only`<br>`ro.vendor.radio.noril=yes` | 删除这两行 | 系统直接禁用 RIL |

第 2 条最隐蔽：`mt6765.mk` 里大量 telephony / radio HAL 包在 `ifneq ($(TARGET_IS_WIFI-ONLY),true)`
里，设成 `true` 编出来的包"看起来什么也不缺"。

## 仓库结构

```
.
├── Android.bp / Android.mk / AndroidProducts.mk
├── BoardConfig.mk              # 屏幕密度、内核 defconfig、sepolicy 目录
├── device.mk                   # TARGET_IS_WIFI-ONLY := false 在这里
├── lineage_gta7lite.mk         # 产品定义
├── lineage.dependencies        # common / kernel 依赖
├── proprietary-files.txt       # 仅本变体专属 blob（TEE）
├── extract-files.py
├── setup-makefiles.py
├── vendor.prop                 # 已移除 wifi-only / noril 两行
├── sepolicy/vendor/            # LTE 专属 sepolicy 挂载点
├── docs/                       # 排障与修复记录（见下）
└── tools/                      # 可重放的修复脚本
```

MT6765 平台的大头 blob（含 `ccci_mdinit`、`volte_*`、`ecc_list` 等）在
`device/samsung/mt6765-common/proprietary-files.txt`，由 common 仓库提供，此处不重复。

## 编译

```bash
repo init -u https://github.com/LineageOS/android.git -b lineage-22.2
repo sync -c -j8 --force-sync --no-clone-bundle --no-tags

# 把本仓库放到 device/samsung/gta7lite
mkdir -p device/samsung
git clone <本仓库地址> device/samsung/gta7lite

source build/envsetup.sh
breakfast lineage_gta7lite        # 或 lunch lineage_gta7lite-userdebug
mka bacon -j$(nproc)
```

依赖仓库：`android_device_samsung_mt6765-common`、`android_kernel_samsung_mt6765`、
`vendor/samsung/gta7litewifi`（TEE blob，MT6765 通用件，与 T220 共用）。

## 刷机

A-only + 动态分区，走标准 `recovery` 流程或直接 `fastboot flash` 单个分区：

```bash
adb reboot bootloader
fastboot flash boot   out/target/product/gta7lite/boot.img
fastboot reboot recovery      # 进 recovery 后 adb sideload 整包
adb sideload out/target/product/gta7lite/lineage-22.2-*-gta7lite.zip
```

首次从官方系统迁过来需要 `fastboot -w`（清 data）。**务必先备份**：本机 33 个分区的
完整 dump 保存在本机（非仓库内容），GPT 表也在其中。

## 已知问题

1. **插卡未实测**。modem 协议栈已启动、射频能读到真实 MCC/LAC/CID，但手头没有 SIM 卡，
   通话 / 短信 / 移动数据 / VoLTE 均未验证。
2. **RAT 属性需手工修正**。仓库代码无法覆盖 `/vendor/build.prop`，刷完必须按
   [`docs/03-modem-lte.md`](docs/03-modem-lte.md) 改两行，否则 modem 永远 `md1:0`。
3. **radio HAL 版本 1.6 vs 1.5**。框架要 `@1.6::IRadio`，三星的 `libsec-ril` 最高只注册 1.5，
   HIDL 回退链因 `getStubIfNeeded=true` 失效。见 [`docs/03-modem-lte.md`](docs/03-modem-lte.md)。
4. **计算器竖屏文字被裁切**。213dpi 让逻辑宽度正好 601dp，跨过 600dp 断点命中大平板字号。
   见 [`docs/05-display-fix.md`](docs/05-display-fix.md)。
5. **国内网络显示"连接受限"、时间时区错乱**。可用脚本一键修：
   [`docs/06-network.md`](docs/06-network.md)、[`docs/07-time.md`](docs/07-time.md)。

## 文档索引

| 文档 | 内容 |
|---|---|
| [`docs/01-device-notes.md`](docs/01-device-notes.md) | 移植差异、编译链踩坑 |
| [`docs/02-build.md`](docs/02-build.md) | 详细编译与刷机步骤、回滚 |
| [`docs/03-modem-lte.md`](docs/03-modem-lte.md) | **LTE 打通全过程**：RAT 配置、CCCI、RIL 版本回退 |
| [`docs/04-selinux.md`](docs/04-selinux.md) | SELinux：`umts_*` 设备标签、precompiled_sepolicy 陷阱 |
| [`docs/05-display-fix.md`](docs/05-display-fix.md) | 计算器 sw600dp 裁切：arsc 定点编码与重签 |
| [`docs/06-network.md`](docs/06-network.md) | captive portal 探针改境内地址 |
| [`docs/07-time.md`](docs/07-time.md) | NTP 服务器与时区兜底值 |
| [`docs/08-smoke-test.md`](docs/08-smoke-test.md) | 12 项功能验收记录 |
| [`docs/09-known-issues.md`](docs/09-known-issues.md) | 未解决问题与后续方向 |

## 致谢

初始设备树来自 LineageOS 官方的 `gta7litewifi` (SM-T220) 维护者；
MTK CCCI / modem 部分参考了 `device/mediatek` 与 MT6765 平台通用实现。

## License

各源码文件遵循其文件头声明的许可证（主要为 Apache-2.0）。
`tools/` 下为调试脚本，按原样提供，不附带任何担保。
