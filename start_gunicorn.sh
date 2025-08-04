#!/bin/bash

# 切换到项目目录
cd /root/backup_sehuatang/web

# 创建日志目录
mkdir -p /root/backup_sehuatang/logs

# 启动 gunicorn
gunicorn -c gunicorn_config.py app:app --daemon --pid /var/run/gunicorn.pid

echo "Gunicorn 已启动，PID 文件: /var/run/gunicorn.pid"
echo "访问地址: http://0.0.0.0:5000"