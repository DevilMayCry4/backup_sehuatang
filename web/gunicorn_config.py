# 日志配置
accesslog = "/root/backup_sehuatang/logs/gunicorn_access.log"
errorlog = "/root/backup_sehuatang/logs/gunicorn_error.log"
loglevel = "info"
capture_output = True

# 日志格式
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s'

# 日志轮转
max_bytes = 10485760  # 10MB
backup_count = 5

# 绑定地址和端口
bind = "0.0.0.0:5000"

# Worker数量
workers = 4
worker_class = "sync"
