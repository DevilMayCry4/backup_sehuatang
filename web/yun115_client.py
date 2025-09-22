#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
115开发平台API客户端
"""

import requests
import json
import hashlib
import time
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode
import logging

logger = logging.getLogger(__name__)

class Yun115Client:
    """115开发平台API客户端"""
    
    def __init__(self, config: Dict[str, str]):
        """
        初始化115客户端
        
        Args:
            config: 115配置信息，包含app_id, app_secret, api_base_url等
        """
        self.app_id = config.get("app_id")
        self.app_secret = config.get("app_secret")
        self.api_base_url = config.get("api_base_url", "https://webapi.115.com")
        self.access_token = config.get("access_token")
        self.refresh_token = config.get("refresh_token")
        
        if not self.app_id or not self.app_secret:
            raise ValueError("115开发平台配置不完整，请检查app_id和app_secret")
    
    def _generate_signature(self, params: Dict[str, Any], timestamp: int) -> str:
        """
        生成API签名
        
        Args:
            params: 请求参数
            timestamp: 时间戳
            
        Returns:
            签名字符串
        """
        # 按照115 API文档要求生成签名
        sorted_params = sorted(params.items())
        param_str = "&".join([f"{k}={v}" for k, v in sorted_params])
        sign_str = f"{param_str}&timestamp={timestamp}&app_secret={self.app_secret}"
        
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    
    def _make_request(self, endpoint: str, params: Dict[str, Any] = None, method: str = "GET") -> Dict[str, Any]:
        """
        发送API请求
        
        Args:
            endpoint: API端点
            params: 请求参数
            method: 请求方法
            
        Returns:
            API响应数据
        """
        if params is None:
            params = {}
        
        # 添加基础参数
        params.update({
            "app_id": self.app_id,
            "access_token": self.access_token
        })
        
        timestamp = int(time.time())
        signature = self._generate_signature(params, timestamp)
        
        params.update({
            "timestamp": timestamp,
            "sign": signature
        })
        
        url = f"{self.api_base_url}{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, params=params, timeout=30)
            else:
                response = requests.post(url, data=params, timeout=30)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"115 API请求失败: {e}")
            return {"state": False, "error": str(e)}
        except json.JSONDecodeError as e:
            logger.error(f"115 API响应解析失败: {e}")
            return {"state": False, "error": "响应格式错误"}
    
    def search_files(self, keyword: str, file_type: str = "video") -> List[Dict[str, Any]]:
        """
        搜索文件
        
        Args:
            keyword: 搜索关键词
            file_type: 文件类型，默认为video
            
        Returns:
            文件列表
        """
        params = {
            "search_value": keyword,
            "file_type": file_type,
            "limit": 50  # 限制返回数量
        }
        
        response = self._make_request("/files/search", params)
        
        if response.get("state"):
            return response.get("data", [])
        else:
            logger.error(f"搜索文件失败: {response.get('error', '未知错误')}")
            return []
    
    def get_download_url(self, file_id: str) -> Optional[str]:
        """
        获取文件下载地址
        
        Args:
            file_id: 文件ID
            
        Returns:
            下载地址
        """
        params = {
            "file_id": file_id
        }
        
        response = self._make_request("/files/download", params)
        
        if response.get("state"):
            data = response.get("data", {})
            return data.get("download_url")
        else:
            logger.error(f"获取下载地址失败: {response.get('error', '未知错误')}")
            return None
    
    def get_play_url(self, file_id: str) -> Optional[str]:
        """
        获取文件播放地址
        
        Args:
            file_id: 文件ID
            
        Returns:
            播放地址
        """
        params = {
            "file_id": file_id
        }
        
        response = self._make_request("/files/video", params)
        
        if response.get("state"):
            data = response.get("data", {})
            return data.get("play_url")
        else:
            logger.error(f"获取播放地址失败: {response.get('error', '未知错误')}")
            return None
    
    def search_movie_files(self, movie_code: str) -> List[Dict[str, Any]]:
        """
        根据电影编号搜索相关视频文件
        
        Args:
            movie_code: 电影编号
            
        Returns:
            匹配的视频文件列表
        """
        # 搜索包含电影编号的视频文件
        files = self.search_files(movie_code, "video")
        
        # 过滤出最相关的文件
        relevant_files = []
        for file in files:
            file_name = file.get("file_name", "").lower()
            if movie_code.lower() in file_name:
                relevant_files.append(file)
        
        return relevant_files
    
    def get_best_quality_file(self, files: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        从文件列表中选择最佳质量的文件
        
        Args:
            files: 文件列表
            
        Returns:
            最佳质量的文件
        """
        if not files:
            return None
        
        # 按文件大小排序，选择最大的文件（通常质量更好）
        sorted_files = sorted(files, key=lambda x: x.get("file_size", 0), reverse=True)
        return sorted_files[0]
    
    def refresh_access_token(self) -> bool:
        """
        刷新访问令牌
        
        Returns:
            是否刷新成功
        """
        if not self.refresh_token:
            logger.error("没有refresh_token，无法刷新访问令牌")
            return False
        
        params = {
            "refresh_token": self.refresh_token
        }
        
        response = self._make_request("/oauth/token/refresh", params, "POST")
        
        if response.get("state"):
            data = response.get("data", {})
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            return True
        else:
            logger.error(f"刷新访问令牌失败: {response.get('error', '未知错误')}")
            return False
    
    def add_download_task(self, urls: List[str], save_path: str = "") -> Dict[str, Any]:
        """
        添加云下载任务
        
        Args:
            urls: 下载链接列表，支持HTTP(S)、FTP、磁力链和电驴链接
            save_path: 保存路径，默认为根目录
            
        Returns:
            任务创建结果
        """
        if not urls:
            return {"state": False, "error": "下载链接不能为空"}
        
        # 将多个链接用换行符分隔
        url_string = "\n".join(urls)
        
        params = {
            "url": url_string,
            "savepath": save_path
        }
        
        response = self._make_request("/web/lixian", params, "POST")
        
        if response.get("state"):
            logger.info(f"成功添加115云下载任务，链接数量: {len(urls)}")
            return response
        else:
            logger.error(f"添加115云下载任务失败: {response.get('error', '未知错误')}")
            return response
    
    def get_download_tasks(self, page: int = 1) -> Dict[str, Any]:
        """
        获取云下载任务列表
        
        Args:
            page: 页码
            
        Returns:
            任务列表
        """
        params = {
            "page": page
        }
        
        response = self._make_request("/web/lixian", params)
        
        if response.get("state"):
            return response
        else:
            logger.error(f"获取115云下载任务列表失败: {response.get('error', '未知错误')}")
            return response
    
    def delete_download_task(self, hash_value: str) -> Dict[str, Any]:
        """
        删除云下载任务
        
        Args:
            hash_value: 任务hash值
            
        Returns:
            删除结果
        """
        params = {
            "hash": hash_value,
            "method": "delete"
        }
        
        response = self._make_request("/web/lixian", params, "POST")
        
        if response.get("state"):
            logger.info(f"成功删除115云下载任务: {hash_value}")
            return response
        else:
            logger.error(f"删除115云下载任务失败: {response.get('error', '未知错误')}")
            return response
    
    def get_task_status(self, hash_value: str) -> Dict[str, Any]:
        """
        获取云下载任务状态
        
        Args:
            hash_value: 任务hash值
            
        Returns:
            任务状态信息
        """
        params = {
            "hash": hash_value,
            "method": "get_id"
        }
        
        response = self._make_request("/web/lixian", params)
        
        if response.get("state"):
            return response
        else:
            logger.error(f"获取115云下载任务状态失败: {response.get('error', '未知错误')}")
            return response