# CryptoMind Pro Plus AI - Android Build Guide

## GitHub Actions 自动构建

本项目配置了GitHub Actions自动构建APK。

### 构建APK的步骤

1. **创建GitHub仓库**
   ```bash
   # 在GitHub上创建一个新仓库，然后：
   cd /Users/wells/Desktop/crypto/CryptoMindProPlusAI
   git init
   git remote add origin https://github.com/YOUR_USERNAME/CryptoMindProPlusAI.git
   ```

2. **推送代码到GitHub**
   ```bash
   git add .
   git commit -m "Add project with GitHub Actions build workflow"
   git push -u origin main
   ```

3. **查看构建状态**
   - 访问 `https://github.com/YOUR_USERNAME/CryptoMindProPlusAI/actions`
   - 点击最新的workflow run查看构建日志

4. **下载APK**
   - 构建成功后，点击 `Summary` 页面
   - 在 `Artifacts` 部分下载 `cryptomindpro-debug.apk`

### 触发重新构建

- 推送代码到 `main` 分支会自动触发构建
- 或手动触发：在 Actions 页面点击 "Build Android APK" -> "Run workflow"

### 本地构建（备选方案）

如果需要在本地构建，需要Linux或Docker环境：

```bash
# 使用Docker
docker run --rm -v "$PWD":/home/user/hostcwd kivy/kivy:latest bash -c "
    pip install buildozer
    buildozer android debug
"
```

## 项目结构

```
CryptoMindProPlusAI/
├── .github/workflows/build.yml  # GitHub Actions构建配置
├── main.py                      # 应用入口
├── mobile_app.py                # 移动端应用
├── api_server.py                # API服务器
├── config/                      # 配置文件
├── core/                       # 核心逻辑
├── data/                       # 数据文件
├── docs/                       # 文档
├── mobile/                      # 移动端界面
└── buildozer.spec              # Buildozer配置
```

## 版本信息

- 应用版本：6.0.0
- 包名：com.cryptomind
- 最低Android版本：Android 7.0 (API 24)
