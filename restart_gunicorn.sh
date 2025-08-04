#!/bin/bash

# 重启 gunicorn
echo "正在重启 gunicorn..."
./stop_gunicorn.sh
sleep 2
./start_gunicorn.sh