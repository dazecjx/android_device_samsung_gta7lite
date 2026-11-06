#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#
# gta7lite —— Samsung Galaxy Tab A7 Lite LTE (SM-T225)
# 派生自 gta7litewifi (SM-T220)

DEVICE_PATH := device/samsung/gta7lite

# Inherit from mt6765-common
include device/samsung/mt6765-common/BoardConfigCommon.mk

# SELinux：本机型挂载点。当前没有规则，只留目录以便真机排障时就地补 avc 规则。
# 注意：radio 的 hwservice 上下文本机型【不需要】另补 ——
#   manifest 声明的 android.hardware.radio* / tetheroffload* 由 AOSP private 覆盖，
#   vendor.mediatek.hardware.mtkradioex 由 device/mediatek/sepolicy_vndr 覆盖（已被
#   mt6765-common/BoardConfigCommon.mk:113 引入）。详见 sepolicy/vendor/hwservice_contexts。
BOARD_VENDOR_SEPOLICY_DIRS += $(DEVICE_PATH)/sepolicy/vendor

# Display
TARGET_SCREEN_DENSITY := 213

# Kernel
# ★ LTE 与 WiFi 的第二个关键差异：内核用 gta7lite_defconfig（带 modem/RIL 相关配置），
#   不是 gta7litewifi_defconfig。两个 defconfig 在同一内核仓库里都已存在。
TARGET_KERNEL_CONFIG := gta7lite_defconfig

# Properties
TARGET_VENDOR_PROP += $(DEVICE_PATH)/vendor.prop

# Inherit from the proprietary version
include vendor/samsung/mt6765-common/BoardConfigVendor.mk
# 设备级 vendor 同 device.mk：复用 gta7litewifi 仓库（TEE blob 为 MT6765 通用件）。
# 不用 -include，缺失时要立刻报错，不能静默跳过。
include vendor/samsung/gta7litewifi/BoardConfigVendor.mk
