#!/bin/bash

# 停止 gunicorn
if [ -f /var/run/gunicorn.pid ]; then
    PID=$(cat /var/run/gunicorn.pid)
    kill $PID
    echo "Gunicorn 已停止 (PID: $PID)"
    rm -f /var/run/gunicorn.pid
else
    echo "未找到 gunicorn PID 文件"
fi