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
        env_file = '/server/backup_sehuatang/copy.env'
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
            "max_retries": int(os.getenv("max_retries", "3")),
            "page_load_timeout": int(os.getenv("page_load_timeout", "30")),
            "implicit_wait": int(os.getenv("implicit_wait", "10")),
            
            # MongoDB配置
            "mongo_uri": os.getenv("MONGO_URI", "mongodb://localhost:27017/"),
            "mongo_db": os.getenv("MONGO_DB", "sehuatang_crawler"),
            "collection_name":os.getenv("collection_name","thread_details"),
            
            # 日志配置
            "log_config": {
                "log_dir": os.getenv("LOG_DIR", "logs"),
                "log_file": os.getenv("LOG_FILE", "crawler.log"),
                "max_bytes": int(os.getenv("LOG_MAX_BYTES", "10485760")),  # 10MB
                "backup_count": int(os.getenv("LOG_BACKUP_COUNT", "5"))
            },
            
            # 邮件配置
            "email_config": {
                "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
                "smtp_port": int(os.getenv("SMTP_PORT", "587")),
                "email": os.getenv("EMAIL", ""),
                "password": os.getenv("EMAIL_PASSWORD", ""),
                "to_email": os.getenv("TO_EMAIL", "")
            },
            
            # 115开发平台配置
            "yun115_config": {
                "app_id": os.getenv("YUN115_APP_ID", ""),
                "app_secret": os.getenv("YUN115_APP_SECRET", ""),
                "api_base_url": os.getenv("YUN115_API_BASE_URL", "https://webapi.115.com"),
                "redirect_uri": os.getenv("YUN115_REDIRECT_URI", ""),
                "access_token": os.getenv("YUN115_ACCESS_TOKEN", ""),
                "refresh_token": os.getenv("YUN115_REFRESH_TOKEN", "")
            }
        }
    
    def get_log_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self.config["log_config"]
    
    def get_email_config(self) -> Dict[str, Any]:
        """获取邮件配置"""
        return self.config["email_config"]
    
    def get_mongo_config(self) -> Dict[str, str]:
        """获取MongoDB配置"""
        return {
            "uri": self.config["mongo_uri"],
            "db_name": self.config["mongo_db"],
            "collection_name":self.config["collection_name"]
        }
    
    def get_crawler_config(self) -> Dict[str, Any]:
        """获取爬虫配置"""
        return {
            "base_url": self.config["base_url"],
            "delay": self.config["delay"],
            "headless": self.config["headless"],
            "max_retries":self.config["max_retries"],
            "page_load_timeout":self.config["page_load_timeout"],
            "implicit_wait":self.config["implicit_wait"],
        }
    
    def get_yun115_config(self) -> Dict[str, str]:
        """获取115开发平台配置"""
        return {
            "app_id": self.config["yun115_config"]["app_id"],
            "app_secret": self.config["yun115_config"]["app_secret"],
            "api_base_url": self.config["yun115_config"]["api_base_url"],
            "redirect_uri": self.config["yun115_config"]["redirect_uri"],
            "access_token": self.config["yun115_config"]["access_token"],
            "refresh_token": self.config["yun115_config"]["refresh_token"]
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self.config.get(key, default)

# 全局配置实例
config = Config()