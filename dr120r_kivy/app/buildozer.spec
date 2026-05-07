[app]
title = DR-120R Calculator
package.name = dr120r
package.domain = com.dr120r

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0.0

requirements = python3,kivy==2.3.0,pillow

orientation = portrait

android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.sdk = 33
android.build_tools_version = 33.0.2
android.accept_sdk_license = True
android.archs = arm64-v8a
android.presplash_color = #1a1a1a
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
