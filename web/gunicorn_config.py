 
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

# 静态文件缓存配置
max_requests = 1000
max_requests_jitter = 50

# 启用预加载应用
preload_app = True

# 设置静态文件缓存
static_map = {
    '/static': '/server/static'
}
