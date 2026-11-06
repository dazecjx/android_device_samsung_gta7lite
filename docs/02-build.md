# 编译与刷机

## 一、环境要求

| 项 | 建议 |
|---|---|
| 系统 | Ubuntu 22.04 / 24.04 x86_64 |
| 内存 | 16GB 起（`mka` 并发高时 32GB 更稳） |
| 磁盘 | 源码 + out 约 250GB |
| JDK | 用 `prebuilts/jdk/jdk21`，不要用系统 JDK |

**不要**在 `ulimit -v` 受限（如 4GB）或 `no_new_privs` 生效的容器里编译：
soong 是 Go 程序，会因 `pthread_create failed` 直接 SIGABRT。这不是配置问题，换环境即可。

## 二、拉源码

```bash
mkdir -p ~/android/lineage && cd ~/android/lineage

# 国内建议用镜像
repo init -u https://mirrors.bfsu.edu.cn/git/lineageOS/LineageOS/android.git -b lineage-22.2
repo sync -c -j8 --force-sync --no-clone-bundle --no-tags
```

## 三、放入设备树

```bash
mkdir -p device/samsung
git clone <本仓库地址> device/samsung/gta7lite
```

依赖的 common / kernel / vendor 仓库：

| 仓库 | 路径 |
|---|---|
| `android_device_samsung_mt6765-common` | `device/samsung/mt6765-common` |
| `android_kernel_samsung_mt6765` | `kernel/samsung/mt6765` |
| `android_vendor_samsung_gta7litewifi` | `vendor/samsung/gta7litewifi`（TEE blob，与 T220 共用） |

`repo sync` 不会自动拉这三个，写进 `.repo/local_manifests/gta7lite.xml`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<manifest>
  <project name="android_device_samsung_mt6765-common"
           path="device/samsung/mt6765-common" remote="github" revision="lineage-22.2" />
  <project name="android_kernel_samsung_mt6765"
           path="kernel/samsung/mt6765" remote="github" revision="lineage-22.2" />
  <project name="android_vendor_samsung_gta7litewifi"
           path="vendor/samsung/gta7litewifi" remote="github" revision="lineage-22.2" />
</manifest>
```

## 四、编译

```bash
source build/envsetup.sh
lunch lineage_gta7lite-userdebug
mka bacon -j$(nproc)
```

产物在 `out/target/product/gta7lite/`：

- `lineage-22.2-*-gta7lite.zip` —— recovery 用的整包
- `boot.img` / `vendor.img` / `product.img` —— 可单刷
- `recovery.img`

## 五、刷机

A-only 分区 + 动态分区（super），两种方式：

### 方式 A：recovery sideload（推荐）

```bash
adb reboot bootloader
fastboot flash boot out/target/product/gta7lite/boot.img
fastboot reboot recovery
# 进 recovery 后
adb sideload out/target/product/gta7lite/lineage-22.2-*-gta7lite.zip
```

### 方式 B：单分区 fastboot

```bash
fastboot flash boot    boot.img
fastboot flash vendor  vendor.img
fastboot flash product product.img
```

**首次从官方系统迁移必须清 data**：`fastboot -w`，否则 FBE 密钥不匹配，卡开机动画。

## 六、刷完必做的两件事

1. **改 `/vendor/build.prop` 的两行 RAT 属性**，否则 modem 永远起不来：
   见 [`03-modem-lte.md`](03-modem-lte.md)。
2. **补 5 条 `umts_*` 设备 SELinux 标签**，否则 modem 起来了 rild 会死循环：
   见 [`04-selinux.md`](04-selinux.md)。

这两步目前必须手工做，因为都改的是 `/vendor` 分区里的文件，而不是本仓库编译出的内容。
**后续方向**：把 RAT 属性写进 `vendor.prop`（`ro.vendor.mtk_ps1_rat` 等如果被
`/vendor/build.prop` 覆盖则无效，需确认加载顺序），或做一个 vendor 侧的 overlay；
`file_contexts` 补丁可以放进本仓库 `sepolicy/vendor/` 目录里的 `file_contexts` 文件。

## 七、回滚

保留官方固件与分区 dump 是唯一可靠的回滚手段。刷坏 boot 时：

```bash
fastboot flash boot <原厂 boot.img>
# 或者用备份的整分区 dump
```

本机做过 33 个分区的完整 dump（含 GPT），落在归档目录，不在本仓库内。
