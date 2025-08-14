import logging
import os 
import time
from logging.handlers import RotatingFileHandler

log_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/logs'
print(log_dir)
if not os.path.exists(log_dir):
   os.makedirs(log_dir, mode=0o755)  # 设置目录权限
info_log_path = os.path.join(log_dir, 'app_info.log')
error_log_path  = os.path.join(log_dir, 'app_error.log')
warning_log_path  = os.path.join(log_dir, 'app_warning.log')
debug_log_path  = os.path.join(log_dir, 'app_debug.log')

# 设置时区为北京时间
os.environ['TZ'] = 'Asia/Shanghai'
time.tzset()

# 创建logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # 设置最低级别为DEBUG

# 清除现有的handlers（如果有的话）
logger.handlers.clear()

# 创建格式化器
formatter = logging.Formatter(
    fmt='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 创建INFO级别handler
info_handler = RotatingFileHandler(
    info_log_path, 
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
info_handler.setLevel(logging.INFO)
info_handler.setFormatter(formatter)
# 只记录INFO级别的消息
info_handler.addFilter(lambda record: record.levelno == logging.INFO)

# 创建WARNING级别handler
warning_handler = RotatingFileHandler(
    warning_log_path,
    maxBytes=10*1024*1024,
    backupCount=5,
    encoding='utf-8'
)
warning_handler.setLevel(logging.WARNING)
warning_handler.setFormatter(formatter)
# 只记录WARNING级别的消息
warning_handler.addFilter(lambda record: record.levelno == logging.WARNING)

# 创建ERROR级别handler
error_handler = RotatingFileHandler(
    error_log_path,
    maxBytes=10*1024*1024,
    backupCount=5,
    encoding='utf-8'
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(formatter)
# 只记录ERROR级别的消息
error_handler.addFilter(lambda record: record.levelno == logging.ERROR)

# 创建DEBUG级别handler
debug_handler = RotatingFileHandler(
    debug_log_path,
    maxBytes=10*1024*1024,
    backupCount=5,
    encoding='utf-8'
)
debug_handler.setLevel(logging.DEBUG)
debug_handler.setFormatter(formatter)
# 只记录DEBUG级别的消息
debug_handler.addFilter(lambda record: record.levelno == logging.DEBUG)

# 添加所有handlers到logger
logger.addHandler(info_handler)
logger.addHandler(warning_handler)
logger.addHandler(error_handler)
logger.addHandler(debug_handler)

def info(msg):
    logger.info(msg)
    print(msg)

def debug(msg):
    logger.debug(msg)
    print(msg)

def error(msg):
    logger.error(msg)
    print(msg)

def warning(msg):
    logger.warning(msg)
    print(msg)