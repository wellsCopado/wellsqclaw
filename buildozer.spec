# CryptoMind Pro Plus AI - Buildozer Android 配置

[app]

# 应用信息
title = CryptoMind Pro
package.name = cryptomindpro
package.domain = com.cryptomind
source.dir = .
version = 6.0.0

# 源码
# 包含TTF字体文件（Android用TTF格式，OTF会崩溃）
source.include_exts = py,png,jpg,kv,atlas,gguf,db,json,txt,md,ttf
source.include_patterns = fonts/*,core/*,config/*,data/* 

# 入口
main.pyfile = mobile_app.py

# 权限
android.permissions = INTERNET, ACCESS_NETWORK_STATE, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, VIBRATE

# Android 配置
android.archs = arm64-v8a, armeabi-v7a
android.minapi = 24
android.api = 34
android.accept_sdk_license = True

# 启动画面
android.manifest.applicationAttributes = android:icon="@mipmap/icon"
android.manifest.launchAttributes = android:screenOrientation="portrait"

# APK 元数据
fullscreen = False
orientation = portrait

# ==================== 依赖包 ====================

# 核心依赖（精简版 - 移除未使用的库以减小APK体积和避免构建问题）
# 注意：embedded_server.py 使用纯 Python 标准库 http.server，无需 fastapi/uvicorn
requirements = python3, kivy, kivymd, requests, urllib3, charset-normalizer, certifi, idna

# 本地 AI - llama.cpp (CUDA/GPU 支持可选)
# requirements = python3, kivy, loguru, llvmlite, llama-cpp-python

# P4A (Python for Android) 构建配置
p4a.branch = master

# Android NDK 版本
android.ndk_version = 25b

# Android SDK 版本
android.sdk_version = 33

# Buildozer log 级别
log_level = 2

# 显示构建进度
verbosity = 2

# ==================== 高级配置 ====================

# 忽略某些模块以减小 APK 大小
# android.whitelist = lib-dynload/_ctypes.so,lib-dynload/_struct.so,lib-dynload/math.so,lib-dynload/select.so

# 服务 (后台运行)
# android.services = MainService

# ==================== 清理配置 ====================

# 构建后清理
android.clean_building_files = True

# 删除临时文件
android.delete_temp_files = True
