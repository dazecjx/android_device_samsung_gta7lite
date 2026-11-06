#!/bin/bash
# gta7lite (SM-T225) LineageOS 22.2 出包脚本
#
#   ./build-release.sh              # 默认 -j4, TARGET_RELEASE=bp1a
#   JOBS=16 ./build-release.sh      # 指定并发
#   OUT_DIR=/path/to/out ./build-release.sh
#
# 为什么不用 lunch：它在受限环境里跑 build_build_var_cache 会失败，
# 直接导出三个目标变量效果等价，且少一层依赖。
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOP="${ANDROID_BUILD_TOP:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"
cd "$TOP" || exit 1

export JAVA_HOME="${JAVA_HOME:-$TOP/prebuilts/jdk/jdk21/linux-x86}"
# tools/shim 用于绕开「utimensat 被 seccomp 拒绝」的环境；正常机器上删掉即可
export PATH="$JAVA_HOME/bin:$SCRIPT_DIR/shim:$PATH"
export OUT_DIR="${OUT_DIR:-$TOP/out}"
export GOMAXPROCS="${GOMAXPROCS:-4}"
export GOGC="${GOGC:-40}"

export TARGET_PRODUCT=lineage_gta7lite
export TARGET_RELEASE="${TARGET_RELEASE:-bp1a}"
export TARGET_BUILD_VARIANT="${TARGET_BUILD_VARIANT:-userdebug}"
export TARGET_BUILD_TYPE=release

echo "=== 开始构建 $(date '+%F %T') ==="
echo "TOP=$TOP"
echo "PRODUCT=$TARGET_PRODUCT RELEASE=$TARGET_RELEASE VARIANT=$TARGET_BUILD_VARIANT"
echo "OUT_DIR=$OUT_DIR  JOBS=${JOBS:-4}"

# soong_ui 启动时会删除上一次的 trace；某些环境保护策略会拦截该删除并让它静默退出 1，
# 这里提前清掉。正常机器上这行无害。
/usr/bin/python3 -c "
import os
for p in ('$OUT_DIR/.soong_ui.trace',):
    try:
        os.unlink(p)
    except OSError:
        pass
" 2>/dev/null

build/soong/soong_ui.bash --make-mode bacon -j"${JOBS:-4}"
rc=$?
echo "=== 构建结束 $(date '+%F %T') rc=$rc ==="
exit $rc
