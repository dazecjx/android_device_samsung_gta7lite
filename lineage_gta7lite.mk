#
# Copyright (C) 2025 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#
# gta7lite —— Samsung Galaxy Tab A7 Lite LTE (SM-T225)
# 派生自 gta7litewifi (SM-T220)，差异全部集中在「有 modem / 有 SIM」这一条线上。

# Inherit from those products. Most specific first.
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit.mk)
TARGET_SUPPORTS_OMX_SERVICE := false
$(call inherit-product, $(SRC_TARGET_DIR)/product/full_base.mk)

# Inherit from gta7lite device
$(call inherit-product, device/samsung/gta7lite/device.mk)

# Inherit some common Lineage stuff.
# ★ LTE 与 WiFi 的第一个关键差异：带电话的 tablet 配置（WiFi 版是 ..._wifionly.mk）
$(call inherit-product, vendor/lineage/config/common_full_tablet.mk)

PRODUCT_NAME := lineage_gta7lite
PRODUCT_DEVICE := gta7lite
PRODUCT_MANUFACTURER := samsung
PRODUCT_BRAND := samsung
PRODUCT_MODEL := SM-T225
PRODUCT_CHARACTERISTICS := tablet

PRODUCT_GMS_CLIENTID_BASE := android-samsung

# TODO(M2): 拿到 T225 官方固件后填入真实指纹。
# 这里刻意不写占位值 —— 写错的指纹比不写更糟（会让 OTA 的 pre-build 断言与实际不符）。
# 拿到固件后按下面格式补齐，xx 为 CSC 区域码（如 DBT / XSA / CHN），版本号取自 AP 字段：
#
# PRODUCT_BUILD_PROP_OVERRIDES += \
#     BuildDesc="gta7litexx-user 14 UP1A.231005.007 T225XXU6DWL9 release-keys" \
#     BuildFingerprint=samsung/gta7litexx/gta7lite:14/UP1A.231005.007/T225XXU6DWL9:user/release-keys \
#     DeviceProduct=gta7litexx \
#     SystemName=gta7litexx
