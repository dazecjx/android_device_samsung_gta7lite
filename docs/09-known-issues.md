# 已知问题与后续方向

## 阻塞项

### 1. 插卡未实测

手头没有 SIM 卡，通话 / 短信 / 移动数据 / VoLTE 全部未验证。
可确认的间接证据：modem 协议栈已启动、射频读到真实 MCC/LAC/CID、RIL 请求-响应双向通畅、
零 SELinux 拒绝。

插卡后需要看的第一批东西：

```bash
adb shell getprop | grep -iE "gsm.sim.state|gsm.operator|gsm.network.type"
adb logcat -b radio | grep -iE "SETUP_DATA_CALL|REGISTRATION|VOICE_CALL"
```

### 2. 双卡 / 副卡 RAT

`ro.vendor.mtk_ps2_rat`（副卡）当前是 `L/W/G`，不含 `Lf`。单卡无影响；
若要双卡且副卡需要 LTE，可能要改成 `Lf/Lt/W/G`。

## 需要手工处理的部署项

这两项改的是 `/vendor` 分区里的文件，设备树编译覆盖不到：

1. `/vendor/build.prop` 两行 RAT（见 `03-modem-lte.md`）；
2. `/vendor/etc/selinux/vendor_file_contexts` 5 条 `umts_*` 标签（见 `04-selinux.md`）。

**后续方向**：确认 `ro.vendor.mtk_ps1_rat` 是否会被 `/vendor/build.prop` 覆盖——
如果 `PRODUCT_VENDOR_PROPERTIES` 生成的 `/vendor/build.prop` 片段能晚于原厂内容加载，
就可以把这两行搬进 `vendor.prop`，彻底免掉手工步骤。
`file_contexts` 则可以直接放进本仓库的 `sepolicy/vendor/file_contexts`。

## radio HAL 版本（1.6 vs 1.5）

当前靠改 `telephony-common.jar` 的 dex 绕过（见 `03-modem-lte.md`），
OTA / 重刷即丢失。正解是改 `device/samsung/mt6765-common/manifest_ril.xml`
把 `@1.6::IRadio/*` 换成 `@1.5::IRadio/*`，未验证编译。

## 计算器显示

`/product` 里的 APK 已替换，OTA 会覆盖。正解是设备 overlay 里的 `values-sw600dp/dimens.xml`
（见 `05-display-fix.md`），未验证编译。

## 国内环境适配

captive portal 与 NTP 都是「用脚本改 settings」解决的，属于每台机器刷完都要跑一次的步骤，
不适合塞进 ROM 默认值（换到境外网络反而更糟）。已提供 `tools/netfix.sh`、`tools/timefix.sh`。

## 上游化 / 升级到 LineageOS 24.0

早期评估过直接上 24.0（Android 16），放弃的原因有两条：

1. 源码体积与拉取流量受限（约 50GB 级别的流量预算）；
2. `radio@1.6` 在 24.0 里**依然存在**，而本机的 `libsec-ril` 最高只到 1.5——
   也就是说 HAL 版本问题在 24.0 上不会消失，反而更硬（HIDL 接口逐步移除但未删净）。

如果要做，建议顺序：先在 22.2 上用 manifest 方式解决 1.5/1.6，再考虑升分支。

## 长期待办

- [ ] 拿到 T225 官方固件后重新 `extract-files.py`，替换当前借用的 T220 TEE blob
- [ ] 补齐 `PRODUCT_BUILD_PROP_OVERRIDES` 的指纹（当前刻意留空，写错比不写更糟）
- [ ] 把 RAT 属性与 file_contexts 固化进设备树，去掉手工步骤
- [ ] 验证 manifest 方案替代 dex 补丁
- [ ] 计算器 overlay 固化并验证编译
- [ ] 插卡实测 + VoLTE
