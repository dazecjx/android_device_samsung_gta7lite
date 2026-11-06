# patches

本仓库只包含 `device/samsung/gta7lite`。有两处修复必须改 `device/samsung/mt6765-common`
（MT6765 平台共用仓库），因此以补丁形式提供。

```bash
# 在源码树根目录执行
cd device/samsung/mt6765-common
git apply ../../device/samsung/gta7lite/patches/0001-mt6765-common-lte-fixes.patch
# 或：patch -p1 < ../../device/samsung/gta7lite/patches/0001-mt6765-common-lte-fixes.patch
```

## 补丁内容

### 1. `vendor_ril.prop` —— RAT 配置（决定 modem 是否启动）

```diff
-ro.vendor.mtk_protocol1_rat_config=no
-ro.vendor.mtk_ps1_rat=no
+ro.vendor.mtk_protocol1_rat_config=Lf/Lt/W/G
+ro.vendor.mtk_ps1_rat=Lf/Lt/W/G
```

`no` 等于告诉 modem「没有任何可用 RAT」。内核日志会出现
`[ccci1/md]runtime rat setting abnormal, using default!!`，
`/sys/kernel/ccci/boot` 永远停在 `md1:0`。

这两个值来自 T225 原厂 `/vendor/build.prop`（用 `debugfs` 读原厂 vendor 镜像比对得出）。

> 该文件被 mt6765-common 共用，Wi-Fi 版机型不受影响（它们本来就不用 modem）。

### 2. `manifest_ril.xml` —— radio HAL 版本

```diff
-        <fqname>@1.6::IRadio/em1</fqname>
-        <fqname>@1.6::IRadio/imsAospSlot1</fqname>
-        <fqname>@1.6::IRadio/se1</fqname>
-        <fqname>@1.6::IRadio/slot1</fqname>
+        <fqname>@1.5::IRadio/em1</fqname>
+        <fqname>@1.5::IRadio/imsAospSlot1</fqname>
+        <fqname>@1.5::IRadio/se1</fqname>
+        <fqname>@1.5::IRadio/slot1</fqname>
```

三星的 `libsec-ril` 最高只注册到 1.5（原厂 manifest 声明的其实是 1.2）。
框架的 `RIL.java` 会先用 `getService(name, true)` 找 1.6 —— 这个 `true`
表示「等 lazy 服务出现」，于是一直等一个永不出现的服务，回退链成了死代码，
表现为 phone 进程 ANR。

不在 manifest 里声明 1.6，`getService` 会立刻返回空并继续走 1.5。

**状态**：这是比改 `telephony-common.jar` 的 dex 更正确的做法，但**尚未在真机验证**。
之前验证通过的是 dex 方案（详见 `../docs/03-modem-lte.md`）。
