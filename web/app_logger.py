import logging
import os 
import time

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

logging.basicConfig(
    filename=info_log_path,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    encoding='utf-8'
)

logging.basicConfig(
    filename=warning_log_path,
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    encoding='utf-8'
)

logging.basicConfig(
    filename=error_log_path,
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    encoding='utf-8'
)

logging.basicConfig(
    filename=debug_log_path,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    encoding='utf-8'
)

logger = logging.getLogger(__name__)


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