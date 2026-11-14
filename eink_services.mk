PRODUCT_PACKAGES += \
    eink_server \
    EinkSettings

PRODUCT_PROPERTY_OVERRIDES += \
    persist.accessibility.enabled_service=com.lmqr.eink_settings/com.lmqr.eink_settings.EinkAccessibilityService

BOARD_VENDOR_SEPOLICY_DIRS += vendor/eink_services/sepolicy/public
