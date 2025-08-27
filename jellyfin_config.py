#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jellyfin配置文件
"""

import os
from typing import Dict, Any

class JellyfinConfig:
    """Jellyfin配置管理"""


   
    def __init__(self):
        self.config = self._load_config()
        print(self.config)
    
    def _load_config(self) -> Dict[str, Any]:
        env_file = '/server/backup_sehuatang/copy.env'
        if os.path.exists(env_file):
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value
        else:
            print(f"❌ 未找到配置文件: {env_file}")
        """加载配置"""
        return {
            # Jellyfin服务器配置
            "server_url": os.getenv("JELLYFIN_SERVER_URL", "http://localhost:8096"),
            "username": os.getenv("JELLYFIN_USERNAME", ""),
            "password": os.getenv("JELLYFIN_PASSWORD", ""),
            
            # 客户端配置
            "client_name": os.getenv("JELLYFIN_CLIENT_NAME", "Movie Checker"),
            "client_version": os.getenv("JELLYFIN_CLIENT_VERSION", "1.0.0"),
            
            # 搜索配置
            "search_limit": int(os.getenv("JELLYFIN_SEARCH_LIMIT", "50")),
            "timeout": int(os.getenv("JELLYFIN_TIMEOUT", "30")),
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self.config.get(key, default)
    
    def validate(self) -> bool:
        """验证配置"""
        required_fields = ["server_url", "username", "password"]
        for field in required_fields:
            if not self.config.get(field):
                print(f"❌ 缺少必需的配置: {field}")
                return False
        return True

# 全局配置实例
config = JellyfinConfig()