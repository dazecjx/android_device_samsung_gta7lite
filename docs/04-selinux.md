# SELinux：从「到处都是拒绝」到零拒绝

## 一、结论先行

整台机器上**真正致命**的拒绝只有一条：

```
avc: denied { read write } for name="umts_boot0"
     scontext=u:r:rild:s0 tcontext=u:object_r:device:s0 tclass=chr_file
```

外加 5 个同类节点（`umts_ipc0/1`、`umts_csd`、`umts_router`、`drb`）。
其余几百条 `default_prop` / `system_prop` 拒绝都是噪声，不影响功能。

## 二、为什么全是 `device` 类型

Lineage 的 `vendor_file_contexts` 里**根本没有**这些节点的条目：

```bash
grep umts /vendor/etc/selinux/vendor_file_contexts   # 空
```

没有匹配规则的设备节点会落到最通用的 `u:object_r:device:s0`，而 rild 对
`device` 没有 `chr_file` 权限——策略里给 rild 的是 `ccci_device`：

```
(allow rild ccci_device (chr_file (ioctl read write getattr lock append map open watch watch_reads)))
```

MTK 原厂本来就把 `ccci_umts_ipc0` / `ccci_bip` / `ccci_ccb_meta` 等标成 `ccci_device`，
新补的这几个属于同一体系。

## 三、修复

`/vendor/etc/selinux/vendor_file_contexts` 追加：

```
/dev/umts_boot0     u:object_r:radio_device:s0
/dev/umts_ipc0      u:object_r:ccci_device:s0
/dev/umts_ipc1      u:object_r:ccci_device:s0
/dev/umts_csd       u:object_r:ccci_device:s0
/dev/umts_router    u:object_r:ccci_device:s0
/dev/drb            u:object_r:ccci_device:s0
```

`umts_boot0` 用的是 `radio_device`（rild 对该类型也有完整权限），之后没再动它，
避免引入无谓变化；后 5 个统一用 `ccci_device`。

**改完必须重启。** `restorecon -v /dev/umts_ipc0` 在这里完全无效——上下文规则在开机时
已被 ueventd 缓存，`restorecon` 只是把文件重新标一遍，不会重新解析 `file_contexts`。

## 四、`precompiled_sepolicy` 陷阱（本项目最大的弯路）

改 `.cil` 源码 → `secilc` 编译 → 替换 `/vendor/etc/selinux/*.cil`，
**完全不生效**。原因是 init 根本不看这些 `.cil`：

```
/odm/etc/selinux/precompiled_sepolicy      ← 实际加载的就是这个（1,265,657 字节）
```

`/odm` 在动态分区里，内容来自原厂。只要它存在且校验通过，init 就直接加载它，
`/vendor/etc/selinux/` 下那些 `plat_*.cil` / `vendor_*.cil` 全被忽略。

### 试过但放弃的做法

把 `precompiled_sepolicy` 改名 `.disabled`，逼迫 init 在开机时现场编译 CIL。
**能用**，代价是开机多约 4 秒，但有个更麻烦的问题：

- 设备自带的 `secilc` 只支持 `-c 33`（Android 14 策略版本），加 `-G` 也只能产出
  1,220,143 字节，**无法复现**原文件的大小与内容；
- 也就是说一旦现场编译失败，机器就起不来，且没有等价文件可回滚。

所以最终没有自编替换，只改 `vendor_file_contexts` 这一个纯文本文件——它由 ueventd 读取，
不参与策略编译，改错最多是某个节点标签不对，可回滚。

### 教训

判断"策略到底从哪加载"，别看文档，看 init 的实际行为：

```bash
ls -l /odm/etc/selinux/ /vendor/etc/selinux/
# 哪个 precompiled_sepolicy 存在且非空，就是它在生效
```

## 五、几条无害但刷屏的拒绝

| 拒绝 | 次数 | 处理 |
|---|---|---|
| `init -> default_prop` | 153 | 补 3 条 allow |
| `init -> system_prop` | 39 | 同上 |
| `toybox -> entrypoint` | — | 补 allow |

这些不影响功能，但会把 `logcat` 刷满，导致真正的拒绝被淹没。补掉之后 rild 的拒绝
就能一眼看到。

## 六、排障要点

1. **avc 不写 dmesg。** `dmesg | grep avc` 是空的，必须
   `logcat -b all | grep "avc:"`。

2. **本机 `auditctl` 是裁剪版**，`ausearch` 之类不可用，只能靠 logcat。

3. **统计高频拒绝的姿势**：

   ```bash
   adb logcat -d -b all | grep "avc:" | sed 's/.*avc: //' | sort | uniq -c | sort -rn | head -20
   ```

4. **先修能挡住功能的，再修噪声。** 顺序错了会浪费大量时间在 `default_prop` 上，
   而真正的问题（`umts_*` 标签）还藏在后面。

## 七、回滚

```bash
cp /data/local/tmp/vendor_file_contexts.bak2 /vendor/etc/selinux/vendor_file_contexts
reboot
```

若曾改名 `precompiled_sepolicy`，直接改回来即可（本仓库最终方案未采用该做法）。
