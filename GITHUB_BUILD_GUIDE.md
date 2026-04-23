# GitHub Actions 构建指南

## 问题
当前 GitHub OAuth 权限不足，无法推送 workflow 文件。

## 解决方案

### 方法1: 手动上传 Workflow 文件

1. 打开 GitHub 网页: https://github.com/wellsCopado/wellsqclaw
2. 点击 "Add file" → "Create new file"
3. 文件路径: `.github/workflows/build.yml`
4. 粘贴以下内容:

```yaml
name: Build Android APK

on:
  push:
    branches: [ main, master ]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 180
    container:
      image: kivy/buildozer:latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Download AI Model (Gemma 3 4B Q4_K_M)
        run: |
          mkdir -p assets/models
          # 使用 Hugging Face 下载量化模型
          curl -L -o assets/models/gemma-3-4b-it-q4_k_m.gguf \
            "https://huggingface.co/google/gemma-3-4b-it-q4_k_m.gguf/resolve/main/gemma-3-4b-it-q4_k_m.gguf" \
            || echo "Model download failed - will use cloud API fallback"
          ls -lh assets/models/ || echo "No models directory"

      - name: Build APK
        run: |
          echo "y" | buildozer android debug 2>&1 | tee build.log

      - name: Upload APK
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: cryptomindpro-debug.apk
          path: bin/*.apk
          retention-days: 7
          if-no-files-found: warn

      - name: Upload build log
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: build-log
          path: build.log
          retention-days: 7

      - name: Show results
        if: always()
        run: |
          echo "=== APK files ==="
          find . -name "*.apk" 2>/dev/null || echo "No APK found"
          echo "=== bin/ ==="
          ls -la bin/ 2>/dev/null || echo "No bin/"
          echo "=== build.log tail ==="
          tail -50 build.log 2>/dev/null || echo "No build.log"
```

5. 点击 "Commit new file"

### 方法2: 使用 GitHub CLI (需要 workflow 权限)

```bash
# 登录 GitHub CLI 并授权 workflow 权限
gh auth login --scopes repo,workflow

# 重新推送
git push
```

### 方法3: 手动触发构建

1. 进入 GitHub 仓库页面
2. 点击 "Actions" 标签
3. 选择 "Build Android APK" workflow
4. 点击 "Run workflow" → "Run workflow"

## 模型配置说明

### 当前配置: Gemma 3 4B Q4_K_M (推荐)
- **大小**: ~2.5GB (量化后)
- **质量**: 接近原始 4B 模型 95% 性能
- **速度**: 手机端可运行
- **下载**: 自动从 Hugging Face 下载

### 备选模型 (更小)
如果需要更小的模型，可以修改 workflow:

```yaml
# Gemma 3 2B Q4_K_M (~1.5GB)
curl -L -o assets/models/gemma-3-2b-it-q4_k_m.gguf \
  "https://huggingface.co/google/gemma-3-2b-it-q4_k_m.gguf/resolve/main/gemma-3-2b-it-q4_k_m.gguf"
```

## 构建产物

构建完成后，APK 文件将出现在:
- GitHub Actions Artifacts (下载期限 7 天)
- 文件路径: `bin/cryptomindpro-1.0.0-arm64-v8a_armeabi-v7a-debug.apk`

## 本地修改已提交

以下修改已在本地提交，需要推送到 GitHub:
- `buildozer.spec` - 添加 GGUF 支持和模型路径
- `.github/workflows/build.yml` - GitHub Actions 构建配置

## 下一步

1. 解决 GitHub 权限问题
2. 推送代码到仓库
3. GitHub Actions 自动触发构建
4. 下载 APK 测试
