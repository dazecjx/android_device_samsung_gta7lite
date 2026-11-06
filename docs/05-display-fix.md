# 计算器竖屏文字被裁切（sw600dp 资源过大）

## 现象

计算器竖屏下，公式行与结果行的文字被垂直裁切、字形压扁。短算式（如 `1+2`）尤其严重，
只露出文字中间一小条。桌面、设置、时钟等界面正常。

## 根因

1. 设备 `ro.sf.lcd_density=213`，逻辑宽度 = 800 ÷ (213/160) = **601dp**，
   刚好跨过 600dp 断点 → 命中 `res/values-sw600dp/dimens.xml`。
2. 该资源是给 10 寸大平板准备的，字号是手机的 2~4 倍：

   | 资源 | values | values-sw600dp |
   |---|---|---|
   | `formula_max_textsize` | 48dip | **128dip** |
   | `formula_min_textsize` | 32dip | 48dip |
   | `result_textsize` | 32dip | **72dip** |
   | `result_padding_bottom` | 32dip | 64dip |

3. `CalculatorFormula.getVariableTextSize()` **只按宽度递增字号**，没有高度约束；
   `activity_calculator.xml` 里 display 区高度是固定百分比（`layout_display_ratio`），
   竖屏下 formula / result 各只有 123px（92dp），装不下 128dip 的字 → 裁切。

横屏走 `values-land`（56dip），所以只有竖屏复现。

## 修复

把竖屏 `values-sw600dp` 的字号 / 内边距降到可容纳的值（default 与 land 一个字节都没动）：

| 资源 | 原值 | 新值 |
|---|---|---|
| `formula_max_textsize` | 128 | 48 |
| `formula_min_textsize` | 48 | 32 |
| `formula_padding_top/bottom/start/end` | 32/22/44/44 | 16/8/16/16 |
| `result_textsize` | 72 | 36 |
| `result_padding_top/bottom/start/end` | 22/64/44/44 | 8/16/16/16 |

## 三个技术要点（可直接复用）

### 1. `resources.arsc` 里的 dimen 不是 IEEE float

是定点数：

```
data  = (value << 8) | unit      unit: 1 = dp(px), 2 = sp
value = data >> 8
```

所以 `struct.pack('<f', 128.0)` 在 arsc 里**搜不到**目标值——本项目前期在这个思路上
浪费了不少时间。

### 2. Android 14+ 的 compact entry

```
offset 0-1: key      (uint16, index into keyStrings)
offset 2  : size     (uint8, = 8)
offset 3  : dataType (uint8, 5 = TYPE_DIMENSION)
offset 4-7: data     (uint32)
```

且 `ResTable_type.flags & 0x02`（`FLAG_OFFSET16`）时，offset 数组是 uint16，
**实际字节偏移 = offset × 4**（不是 ×1）。这条踩错会得到一堆乱码条目。

### 3. 签名必须用同一把 key

`/product/app/ExactCalculator/ExactCalculator.apk` 用的是 AOSP testkey，
证书指纹 `a40da80a59d170caa950cf15c18c454d47a39b26989d8b640ecd745ba71bf5dc`，
与 `build/target/product/security/testkey.{pk8,x509.pem}` 一致。
用同一密钥重签后签名不变，可**原地替换**，不会触发 signature mismatch。

## 重做步骤（OTA / 重刷后）

```bash
export JAVA_HOME=/android/lineage/prebuilts/jdk/jdk21/linux-x86
export PATH=$JAVA_HOME/bin:$PATH
AAPT2=/android/lineage/out/host/linux-x86/bin/aapt2
ZA=/android/lineage/prebuilts/build-tools/linux-x86/bin/zipalign
SIGNER=/android/lineage/prebuilts/sdk/tools/linux/lib/apksigner.jar
KEYS=/android/lineage/build/target/product/security

# 1. 取 APK
adb pull /product/app/ExactCalculator/ExactCalculator.apk
# 2. 解包，改 arsc
mkdir -p unpack && cd unpack && unzip -q ../ExactCalculator.apk && cd ..
python3 tools/patch_dimen.py        # 内部固定读写 unpack/resources.arsc
# 3. 重打包（丢掉 META-INF/*.SF|RSA|MF，用 patch 后的 arsc 覆盖同名条目）-> unsigned.apk
# 4. 对齐 + 签名
$ZA -f -p 4 unsigned.apk aligned.apk
java -jar $SIGNER sign --key $KEYS/testkey.pk8 --cert $KEYS/testkey.x509.pem \
  --v1-signing-enabled true --v2-signing-enabled true --v3-signing-enabled true \
  --out signed.apk aligned.apk
java -jar $SIGNER verify --print-certs signed.apk     # 指纹须为 a40da80a...
# 5. 校验资源
$AAPT2 dump resources signed.apk | grep -A3 dimen/formula_max_textsize
# 6. 推送
adb root && adb remount
adb push signed.apk /data/local/tmp/ExactCalculator.apk.new
adb shell "cp /data/local/tmp/ExactCalculator.apk.new /product/app/ExactCalculator/ExactCalculator.apk"
adb shell "chmod 644 /product/app/ExactCalculator/ExactCalculator.apk"
adb shell restorecon -v /product/app/ExactCalculator/ExactCalculator.apk
adb shell am force-stop com.android.calculator2
```

第 3 步的重打包要点：用 Python `zipfile` 逐条复制原 APK 条目，**唯独**
`resources.arsc` 换成补丁后的版本，并跳过旧签名文件。顺序与 `compress_type` 必须保持一致。

## 验证结果

| 场景 | 结果 |
|---|---|
| `1+2` → `3` | ✅ 完整（修复前几乎只剩一条横线） |
| `π` → `3.1415926535897932384626433` | ✅ |
| `π1,415,926` → `4,448,262.7196267815809634567` | ✅ |
| 横屏 | ✅ 未受影响 |
| 崩溃 / 残留 overlay | ✅ 无 |

## 回滚

```bash
adb shell "cp /data/local/tmp/ExactCalculator.apk.orig /product/app/ExactCalculator/ExactCalculator.apk"
adb shell restorecon -v /product/app/ExactCalculator/ExactCalculator.apk
adb shell am force-stop com.android.calculator2
```

## 备选方案（均未采用）

- **把 density 改成 216**（逻辑宽 592dp，跨过断点）：一条命令全局绕过，
  但会让所有 app 失去平板布局，得不偿失。
- **RRO overlay**：`cmd overlay fabricate` 只接受整数 dataType（16~31），dimen 是浮点，
  不可用；且计算器未声明 `<overlayable>`，常规 RRO 也覆盖不了。
- **重新编译 APK**：编译链在本机不可用（见 `01-device-notes.md`）。

## 若要固化进源码树

把改后的 `dimens.xml` 放到设备 overlay：

```
device/samsung/gta7lite/overlay/packages/apps/ExactCalculator/res/values-sw600dp/dimens.xml
```

并在 `device.mk` 加：

```make
PRODUCT_PACKAGE_OVERLAYS += device/samsung/gta7lite/overlay
```

（本机未验证编译，因为编译链不可用。理论上这是最干净的修法。）
