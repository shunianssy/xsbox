# 创建虚拟环境
if (-not (Test-Path "venv")) {
    Write-Host "创建虚拟环境..."
    py -m venv venv
}

# 激活虚拟环境
Write-Host "激活虚拟环境..."
& "venv\Scripts\Activate.ps1"

# 安装依赖
Write-Host "安装依赖..."
pip install -r requirements.txt

# 启动后端服务
Write-Host "启动后端服务..."
py app.py

# 保持窗口打开
Read-Host "按 Enter 键退出..."
