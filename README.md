# Xsbox

这是一个实验性项目，基于[TurboWarp](https://github.com/TurboWarp)的scratch多人协作解决方案，同时也是一个开源项目，欢迎提交pr和issue

## 介绍

Xsbox是一个基于[TurboWarp](https://github.com/TurboWarp)的实验性项目，提供了关于scratch协作的开源解决方案

## 功能

基于flask框架，websocket协议，实现了scratch的多人协作

## 警告

目前仍处于实验阶段，存在诸多未知BUG需要解决，如果你有发现bug可以新建一个issue，或者你有优化点可以拉取提交一个pr

## 使用

环境需求：python3.12.9（别的不稳定），nodejs24，pnpm

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动服务

```bash
python app.py
pnpm start
```

### 访问

打开浏览器访问`http://localhost:8169`即可使用

## 贡献

欢迎提交pr，或者新建issue

## 许可证

本项目采用GPLv3许可证