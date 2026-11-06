# tools

移植过程中写的排障 / 修复脚本。都是**真机现场用过**的，不是示意代码。
默认通过 PATH 里的 `adb` 操作设备，可用环境变量 `ADB=/path/to/adb` 覆盖。

## 一键修复类

| 脚本 | 作用 | 用法 |
|---|---|---|
| `netfix.sh` | 修「网络连接受限」：换境内 captive portal 探针并重建网络 | `./netfix.sh [SSID]` |
| `timefix.sh` | 修时间/时区：换境内 NTP + 关自动时区并钉死 `Asia/Shanghai` | `./timefix.sh [时区ID]` |
| `restore.sh` | 回滚 rild 的 SELinux 相关改动（需先有 `/data/local/tmp/sepolicy-backup`）| `./restore.sh` |

前两个是幂等的，重复跑无害。

## 资源 / 字节码补丁

| 脚本 | 作用 |
|---|---|
| `arsc.py` | 极简 `resources.arsc` 解析器（包 / 类型 / 配置 / 条目遍历）。可单独当库用 |
| `patch_dimen.py` | 改计算器竖屏 `values-sw600dp` 的 11 个尺寸；依赖 `unpack/resources.arsc` |
| `dexdec.py` | DEX 指令宽度解码器。含完整 opcode 宽度表与 35c 格式参数位置修正 |
| `patch_ril.py` | 对 `telephony-common.jar` 的 `classes.dex` 打三处 RIL 版本回退补丁 |
| `mkpolicy.py` | 生成 rild 的 CIL 规则与 `umts_boot0` 上下文（`enumerate` / `final` 两模式）|

### 关于 `patch_dimen.py`

`resources.arsc` 里的 dimen **不是 IEEE float**，是定点数 `(value << 8) | unit`
（unit 1=dp 2=sp）。脚本按这个规则读写，并且处理了 Android 14+ 的 8 字节 compact entry
与 `FLAG_OFFSET16`（偏移需 ×4）。完整说明见 [`../docs/05-display-fix.md`](../docs/05-display-fix.md)。

### 关于 `patch_ril.py` / `dexdec.py`

这两个是**没有编译能力时的应急手段**：直接改 framework jar 里的 dex，
让框架从 `radio@1.6` 回退到 `radio@1.5`。属于绕过而非修复，OTA 会丢。
推荐的正解（改 VINTF manifest）见 [`../docs/03-modem-lte.md`](../docs/03-modem-lte.md)。

`dexdec.py` 之所以存在：受限环境里跑不起 baksmali 之类工具，只能自己实现指令解码。
如果换成正常环境，直接用 `baksmali` / `smali` 更省事。

## 构建辅助

| 文件 | 作用 |
|---|---|
| `build-release.sh` | 完整出包脚本：设定 `OUT_DIR` / 目标变量、绕开 `lunch`、直接调 `soong_ui.bash --make-mode bacon` |
| `shim/touch` | `touch` 的 python 替代（见下） |
| `shim/cp` | `cp` 的替代，剥掉 `-p` / `-a` / `--preserve=*` |

### 这两个 shim 是给「受限环境」用的

某些容器/沙箱的 seccomp 策略会拒绝 `utimensat` 携带非 NULL `timespec` 的调用，
表现是 GNU `touch`、`cp -p`、`install -p` 全部报 `不允许的操作`，
而 `utimensat(NULL)`（即 python 的 `os.utime(path, None)`）是放行的。

AOSP 构建大量依赖 `touch` 建 stamp 文件、`cp -p` 复制产物，被拒后 make 立刻失败。
`build-release.sh` 把 `shim/` 前置进 `PATH` 来绕开。

**在正常机器上不要用这两个 shim**——它们会丢掉时间戳语义，增量编译的判定会不准。

### 用法

```bash
# 正常机器（推荐）：删掉脚本里 PATH / OUT_DIR / GOGC 三行，然后
./tools/build-release.sh
JOBS=16 ./tools/build-release.sh     # 指定并发
```

脚本默认 `TARGET_RELEASE=bp1a`（LineageOS 22.2 / Android 15）。换分支时改这一行。

## 依赖

- Python 3.8+（无第三方库）
- `bash`
- 设备端需要有 `root`（脚本会自己 `adb root`）
