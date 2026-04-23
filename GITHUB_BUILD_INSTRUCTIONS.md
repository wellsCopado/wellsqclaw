# GitHub Actions 构建配置指南

## 问题
由于 GitHub OAuth 权限限制，无法通过命令行推送 workflow 文件。

## 解决方案（手动上传）

### 步骤1：创建 Workflow 文件
1. 访问 https://github.com/wellsCopado/wellsqclaw
2. 点击 "Add file" → "Create new file"
3. 文件路径：`.github/workflows/build.yml`

### 步骤2：粘贴以下内容

```yaml
name: Build CryptoMind APK

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 180
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install buildozer cython
        sudo apt-get update
        sudo apt-get install -y git zip unzip openjdk-17-jdk
    
    - name: Download Gemma 3 4B Model
      run: |
        mkdir -p mobile/models
        cd mobile/models
        # Download quantized model (~2.5GB)
        wget -q --show-progress https://huggingface.co/lmstudio-community/gemma-3-4b-it-GGUF/resolve/main/gemma-3-4b-it-Q4_K_M.gguf
        ls -lh *.gguf
    
    - name: Build APK
      run: |
        cd mobile
        buildozer android debug
    
    - name: Upload APK
      uses: actions/upload-artifact@v3
      with:
        name: cryptomind-apk
        path: mobile/bin/*.apk
```

### 步骤3：提交文件
- 点击 "Commit new file"
- 这将自动触发构建

### 步骤4：查看构建状态
- 访问 https://github.com/wellsCopado/wellsqclaw/actions
- 构建完成后下载 APK

## 注意事项
- 构建时间约 30-60 分钟
- 模型文件约 2.5GB，下载可能需要时间
- 如果构建失败，检查日志中的错误信息
