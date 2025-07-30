#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目配置文件
"""

import os
from typing import Dict, Any

class Config:
    """项目配置管理"""
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置"""
        # 加载环境变量文件
        env_file = '.env'
        if os.path.exists(env_file):
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value
        
        return {
            # 爬虫配置
            "base_url": os.getenv("CRAWLER_BASE_URL", "https://example.com"),
            "delay": int(os.getenv("CRAWLER_DELAY", "3")),
            "headless": os.getenv("CRAWLER_HEADLESS", "true").lower() == "true",
            
            # MongoDB配置
            "mongo_uri": os.getenv("MONGO_URI", "mongodb://localhost:27017/"),
            "mongo_db": os.getenv("MONGO_DB", "sehuatang"),
            
            # 日志配置
            "log_config": {
                "log_dir": os.getenv("LOG_DIR", "logs"),
                "log_file": os.getenv("LOG_FILE", "crawler.log"),
                "max_bytes": int(os.getenv("LOG_MAX_BYTES", "10485760")),  # 10MB
                "backup_count": int(os.getenv("LOG_BACKUP_COUNT", "5"))
            }
        }
    
    def get_log_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self.config["log_config"]
    
    def get_mongo_config(self) -> Dict[str, str]:
        """获取MongoDB配置"""
        return {
            "uri": self.config["mongo_uri"],
            "db": self.config["mongo_db"]
        }
    
    def get_crawler_config(self) -> Dict[str, Any]:
        """获取爬虫配置"""
        return {
            "base_url": self.config["base_url"],
            "delay": self.config["delay"],
            "headless": self.config["headless"]
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self.config.get(key, default)

# 全局配置实例
config = Config()