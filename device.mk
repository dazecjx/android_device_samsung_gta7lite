#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#
# gta7lite —— Samsung Galaxy Tab A7 Lite LTE (SM-T225)
# 派生自 gta7litewifi (SM-T220)

# Inherit from mt6765-common
$(call inherit-product, device/samsung/mt6765-common/mt6765.mk)

# Dalvik Heap Configuration
$(call inherit-product, frameworks/native/build/tablet-10in-xhdpi-2048-dalvik-heap.mk)

# ★ LTE 与 WiFi 的第三个关键差异（最重要的一条）。
# mt6765.mk 里大量 telephony / radio HAL 都在 ifneq ($(TARGET_IS_WIFI-ONLY),true) 里，
# 这里设 true 会把整个 RIL 栈排除掉，编出来的包能开机但插卡无信号。
TARGET_IS_WIFI-ONLY := false

# Boot animation
TARGET_SCREEN_HEIGHT := 1340
TARGET_SCREEN_WIDTH := 800

# Shipping API Level
PRODUCT_SHIPPING_API_LEVEL := 30

# Tablet
PRODUCT_CHARACTERISTICS := tablet

# Soong namespaces
PRODUCT_SOONG_NAMESPACES += \
    $(LOCAL_PATH)

# Inherit from vendor blobs
# 注意：这里复用 WiFi 变体的 vendor 仓库，不要改成 vendor/samsung/gta7lite。
# 原因：gta7lite 目前没有独立 vendor 仓库，那 33 条 blob 全部是 TEE 分区文件
# (vendor/tee/00000000-*) ，属 MT6765 SoC 级通用件，T220 与 T225 共用。
# 若写成 vendor/samsung/gta7lite，inherit-product-if-exists 会静默跳过，
# 编出来的包不缺任何报错，但少了整个 TEE blob 集合——典型的无声失败。
# TODO(M4): 拿到 T225 官方固件后重新 extract-files.py，再拆出独立 vendor 仓库。
$(call inherit-product, vendor/samsung/gta7litewifi/gta7litewifi-vendor.mk)
