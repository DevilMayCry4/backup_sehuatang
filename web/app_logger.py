import logging
import os 

log_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/logs'
print(log_dir)
if not os.path.exists(log_dir):
   os.makedirs(log_dir, mode=0o755)  # 设置目录权限
log_path = os.path.join(log_dir, 'app.log')

logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

logger = logging.getLogger(__name__)


def info(msg):
    logger.info(msg)


def error(msg):
    logger.error(msg)

def warning(msg):
    logger.warning(msg)