import logging
import os 
import time

log_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/logs'
print(log_dir)
if not os.path.exists(log_dir):
   os.makedirs(log_dir, mode=0o755)  # 设置目录权限
log_path = os.path.join(log_dir, 'app.log')

# 设置时区为北京时间
os.environ['TZ'] = 'Asia/Shanghai'
time.tzset()

logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    encoding='utf-8'
)

logger = logging.getLogger(__name__)


def info(msg):
    logger.info(msg)


def error(msg):
    logger.error(msg)

def warning(msg):
    logger.warning(msg)