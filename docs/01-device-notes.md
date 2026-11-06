# 移植笔记：从 gta7litewifi (SM-T220) 到 gta7lite (SM-T225)

## 一、两机的关系

SM-T220（Wi-Fi）与 SM-T225（LTE）是同一块板子的两个 SKU：同 SoC（MT6765）、同屏幕、
同主板布局，差异只有 modem 子系统和 SIM 卡槽。所以设备树是 fork 关系，而不是重写关系。

但正因为"几乎一样"，直接套用 Wi-Fi 版设备树会得到一个**能开机、能过所有非通话测试、
插卡却毫无反应且不报错**的包——这是本项目最初两天的全部噩梦来源。

## 二、四处必改项

### 1. `lineage_gta7lite.mk`

```make
# Wi-Fi 版
$(call inherit-product, vendor/lineage/config/common_full_tablet_wifionly.mk)
# LTE 版
$(call inherit-product, vendor/lineage/config/common_full_tablet.mk)
```

选错的表现：系统设置里完全没有"移动网络"入口，`TelephonyManager` 认为设备无蜂窝能力。

### 2. `device.mk` —— 最隐蔽的一处

```make
TARGET_IS_WIFI-ONLY := false
```

`mt6765.mk` 里是这样的结构：

```make
ifneq ($(TARGET_IS_WIFI-ONLY),true)
PRODUCT_PACKAGES += \
    rild \
    libril \
    ...telephony / radio HAL 一堆...
endif
```

设成 `true` 时，整个 RIL 栈根本不会被打进镜像。编译日志干净、刷机正常、系统正常，
只有插卡时才发现 `/vendor/bin/hw/rild` 不存在。

**教训**：从 Wi-Fi 变体 fork 设备树时，先 `grep -rn "WIFI-ONLY" device/samsung/mt6765-common/`，
把所有条件编译点列出来逐个确认，不要只看 diff。

### 3. `BoardConfig.mk`

```make
TARGET_KERNEL_CONFIG := gta7lite_defconfig   # 不是 gta7litewifi_defconfig
```

两个 defconfig 在同一内核仓库 `android_kernel_samsung_mt6765` 里都已存在。
用错的表现：CCCI 字符设备（`/dev/ccci_*`、`/dev/umts_*`）在内核里就没编译进去，
用户态怎么修 SELinux 都没用。

### 4. `vendor.prop`

```diff
-ro.carrier=wifi-only
-ro.vendor.radio.noril=yes
```

`noril=yes` 会让 `init` 直接跳过 RIL 服务。这两行必须删掉而不是改成 `no`——
删掉即走默认值，改值容易被后续属性覆盖。

## 三、编译链的坑（本机环境相关）

### soong 在受限环境里起不来

`m` / `mka` 在 `ulimit -v` 被硬锁到 4GB、且 `no_new_privs` 生效的沙箱里必定失败：

```
runtime/cgo: pthread_create failed: Resource temporarily unavailable
SIGABRT
```

soong 是 Go 程序，启动时按 CPU 核数创建线程，每个线程预留栈空间，虚拟内存很快打满。
`GOMAXPROCS=1` 能稍微缓解但不够。**这不是代码问题，是环境限制**——换一台普通机器编译即可。

因此本项目的部分修复（见 `03`、`05`）是在**没有编译能力的前提下**，
用字节码 / 资源表级别的原地补丁完成的。这些补丁是临时手段，正确做法仍是在源码里改。

### 镜像源

国内拉 LineageOS 源码，`mirrors.bfsu.edu.cn`（BFSU）实测最快且不排队，
`/git/lineageOS/LineageOS/` 与 `/git/AOSP/` 两个端点都可用，commit 与官方一致。

## 四、vendor blob 的取舍

`proprietary-files.txt` 只列本变体专属的 **TEE 分区文件**（`vendor/tee/00000000-*`），
这批是 MT6765 SoC 级通用件，T220 与 T225 完全一致，所以 `device.mk` 里
`inherit-product` 直接复用 `vendor/samsung/gta7litewifi` 仓库。

两个注意点：

1. 不要写成 `vendor/samsung/gta7lite`——仓库不存在，`inherit-product-if-exists`
   会**静默跳过**，包能编出来但少整套 TEE blob，属于典型的无声失败。
   （本仓库用 `include` 而非 `-include`，缺文件时立刻报错。）
2. 拿到 T225 官方固件后应重新 `extract-files.py`，TEE 的 UUID 可能与 T220 不同。
   当前沿用 T220 的 TEE：能开机、能跑，但 Knox / DRM 相关功能可能异常。
