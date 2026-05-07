[app]
title = DR-120R Calculator
package.name = dr120r
package.domain = com.dr120r

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0.0

requirements = python3,kivy==2.3.0,pillow

# Orientation
orientation = portrait

# Android
android.permissions = INTERNET
android.api = 33
android.minapi = 24
android.ndk = 25b
android.sdk = 33
android.ndk_api = 24
android.archs = arm64-v8a, armeabi-v7a

# Icons (ถ้ามีไฟล์ icon.png ขนาด 512x512)
# icon.filename = %(source.dir)s/icon.png
# presplash.filename = %(source.dir)s/presplash.png

android.presplash_color = #1a1a1a
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
