#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jellyfin电影存在性检查脚本

功能：
- 连接到Jellyfin服务器
- 搜索指定的电影
- 返回电影是否存在及详细信息

使用方法：
python jellyfin_movie_checker.py "电影名称"
"""

import requests
import json
import sys
import argparse
import hashlib
import uuid
import os
from typing import Dict, List, Optional, Any
from urllib.parse import quote
from jellyfin_config import config


class JellyfinMovieChecker:
    def __init__(self, server_url: Optional[str] = None, username: Optional[str] = None, 
                 password: Optional[str] = None, client_name: Optional[str] = None, 
                 client_version: Optional[str] = None):
        """
        初始化Jellyfin电影检查器
        
        Args:
            server_url: Jellyfin服务器地址 (例如: http://localhost:8096)，默认从环境变量获取
            username: 用户名，默认从环境变量获取
            password: 密码，默认从环境变量获取
            client_name: 客户端名称，默认从环境变量获取
            client_version: 客户端版本，默认从环境变量获取
        """
        # 加载环境变量文件
        
        # 使用传入参数或从配置中获取
        self.server_url = (server_url or config.get("server_url")).rstrip('/')
        self.username = username or config.get("username")
        self.password = password or config.get("password")
        self.client_name = client_name or config.get("client_name")
        self.client_version = client_version or config.get("client_version")
        
        # 验证必需的配置
        if not all([self.server_url, self.username, self.password]):
            missing = []
            if not self.server_url: missing.append("server_url")
            if not self.username: missing.append("username")
            if not self.password: missing.append("password")
            raise ValueError(f"缺少必需的配置: {', '.join(missing)}。请设置环境变量或传入参数。")
        
        # 生成设备ID (基于用户名的哈希)
        self.device_id = hashlib.md5(f"{self.username}_{uuid.getnode()}".encode()).hexdigest()
        self.device_name = "Python Movie Checker"
        
        self.access_token = None
        self.user_id = None
        self.session = requests.Session()

    def authenticate(self) -> bool:
        """
        认证用户并获取访问令牌
        
        Returns:
            bool: 认证是否成功
        """
        auth_url = f"{self.server_url}/Users/AuthenticateByName"
        
        # 设置认证头（无令牌）
        headers = {
            "Authorization": f'MediaBrowser Client="{self.client_name}", Device="{self.device_name}", DeviceId="{self.device_id}", Version="{self.client_version}"',
            "Content-Type": "application/json"
        }
        
        # 认证数据
        auth_data = {
            "Username": self.username,
            "Pw": self.password
        }
        
        try:
            response = self.session.post(auth_url, headers=headers, json=auth_data)
            response.raise_for_status()
            
            auth_result = response.json()
            self.access_token = auth_result.get("AccessToken")
            self.user_id = auth_result.get("User", {}).get("Id")
            
            if self.access_token and self.user_id:
                print(f"✅ 认证成功，用户ID: {self.user_id}")
                return True
            else:
                print("❌ 认证失败：未获取到访问令牌或用户ID")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ 认证请求失败: {e}")
            return False
        except json.JSONDecodeError as e:
            print(f"❌ 认证响应解析失败: {e}")
            return False
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """
        获取带有认证信息的请求头
        
        Returns:
            Dict[str, str]: 请求头字典
        """
        return {
            "Authorization": f'MediaBrowser Client="{self.client_name}", Device="{self.device_name}", DeviceId="{self.device_id}", Version="{self.client_version}", Token="{self.access_token}"',
            "Content-Type": "application/json"
        }
    
    def get_movie_libraries(self) -> List[Dict[str, Any]]:
        """
        获取所有电影库
        
        Returns:
            List[Dict[str, Any]]: 电影库列表
        """
        if not self.access_token:
            print("❌ 请先进行认证")
            return []
        
        views_url = f"{self.server_url}/Users/{self.user_id}/Views"
        headers = self._get_auth_headers()
        
        try:
            response = self.session.get(views_url, headers=headers)
            response.raise_for_status()
            
            views_data = response.json()
            movie_libraries = []
            
            for item in views_data.get("Items", []):
                # 查找电影类型的库
                if item.get("CollectionType") == "movies":
                    movie_libraries.append({
                        "id": item.get("Id"),
                        "name": item.get("Name"),
                        "type": item.get("CollectionType")
                    })
            
            print(f"📚 找到 {len(movie_libraries)} 个电影库")
            for lib in movie_libraries:
                print(f"  - {lib['name']} (ID: {lib['id']})")
            
            return movie_libraries
            
        except requests.exceptions.RequestException as e:
            print(f"❌ 获取库信息失败: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"❌ 库信息响应解析失败: {e}")
            return []
    
    def search_movies(self, movie_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        搜索电影
        
        Args:
            movie_name: 电影名称
            limit: 搜索结果限制
            
        Returns:
            List[Dict[str, Any]]: 搜索结果列表
        """
        if not self.access_token:
            print("❌ 请先进行认证")
            return []
        
        # 获取电影库
        movie_libraries = self.get_movie_libraries()
        if not movie_libraries:
            print("❌ 未找到电影库")
            return []
        
        all_results = []
        
        for library in movie_libraries:
            library_id = library["id"]
            library_name = library["name"]
            
            print(f"🔍 在库 '{library_name}' 中搜索 '{movie_name}'...")
            
            # 搜索API端点
            search_url = f"{self.server_url}/Users/{self.user_id}/Items"
            headers = self._get_auth_headers()
            
            # 搜索参数
            params = {
                "ParentId": library_id,
                "IncludeItemTypes": "Movie",
                "SearchTerm": movie_name,
                "Recursive": "true",
                "Limit": limit,
                "Fields": "Overview,Genres,ProductionYear,CommunityRating,OfficialRating,Path"
            }
            
            try:
                response = self.session.get(search_url, headers=headers, params=params)
                response.raise_for_status()
                
                search_data = response.json()
                items = search_data.get("Items", [])
                
                for item in items:
                    movie_info = {
                        "id": item.get("Id"),
                        "name": item.get("Name"),
                        "year": item.get("ProductionYear"),
                        "overview": item.get("Overview", "")[:200] + "..." if item.get("Overview") and len(item.get("Overview", "")) > 200 else item.get("Overview", ""),
                        "genres": item.get("Genres", []),
                        "rating": item.get("CommunityRating"),
                        "official_rating": item.get("OfficialRating"),
                        "path": item.get("Path"),
                        "library": library_name,
                        "library_id": library_id,
                        "server_url": self.server_url
                    }
                    all_results.append(movie_info)
                
                print(f"  📁 在 '{library_name}' 中找到 {len(items)} 个结果")
                
            except requests.exceptions.RequestException as e:
                print(f"❌ 搜索请求失败 (库: {library_name}): {e}")
            except json.JSONDecodeError as e:
                print(f"❌ 搜索响应解析失败 (库: {library_name}): {e}")
        
        return all_results
    
    def check_movie_exists(self, movie_name: str) -> Dict[str, Any]:
        """
        检查电影是否存在
        
        Args:
            movie_name: 电影名称
            
        Returns:
            Dict[str, Any]: 检查结果
        """
        print(f"🎬 正在检查电影: '{movie_name}'")
        print("=" * 50)
        
        # 认证
        if not self.authenticate():
            return {
                "exists": False,
                "error": "认证失败",
                "movies": []
            }
        
        # 搜索电影
        movies = self.search_movies(movie_name)
        
        result = {
            "exists": len(movies) > 0,
            "count": len(movies),
            "movies": movies,
            "search_term": movie_name
        }
        
        # 显示结果
        print("\n" + "=" * 50)
        if result["exists"]:
            print(f"Jellyfin中 ✅ 找到 {result['count']} 部相关电影:")
            for i, movie in enumerate(movies, 1):
                print(f"\n{i}. {movie['name']}")
                if movie['year']:
                    print(f"   📅 年份: {movie['year']}")
                if movie['genres']:
                    print(f"   🎭 类型: {', '.join(movie['genres'])}")
                if movie['rating']:
                    print(f"   ⭐ 评分: {movie['rating']}/10")
                if movie['official_rating']:
                    print(f"   🔞 分级: {movie['official_rating']}")
                print(f"   📚 所在库: {movie['library']}")
                if movie['path']:
                    print(f"   📁 路径: {movie['path']}")
                if movie['overview']:
                    print(f"   📝 简介: {movie['overview']}")
                print(f"   🔗 链接: {movie['server_url']}/web/index.html#!/details?id={movie['id']}")
        else:
            print(f"Jellyfin中 ❌ 未找到电影: '{movie_name}'")
        
        return result

def main():
    # 加载环境变量文件
    load_env_file()
    
    parser = argparse.ArgumentParser(description="检查Jellyfin服务器上是否存在指定电影")
    parser.add_argument("movie_name", help="要搜索的电影名称")
    parser.add_argument("--server", help="Jellyfin服务器地址 (覆盖环境变量)")
    parser.add_argument("--username", help="用户名 (覆盖环境变量)")
    parser.add_argument("--password", help="密码 (覆盖环境变量)")
    parser.add_argument("--json", action="store_true", help="以JSON格式输出结果")
    
    args = parser.parse_args()
    
    try:
        # 创建检查器实例，优先使用命令行参数，其次使用环境变量
        checker = JellyfinMovieChecker(
            server_url=args.server,
            username=args.username,
            password=args.password
        )
         
    except ValueError as e:
        print(f"❌ 配置错误: {e}")
        print("\n💡 请确保设置了以下环境变量或使用命令行参数:")
        print("   JELLYFIN_SERVER_URL=http://localhost:8096")
        print("   JELLYFIN_USERNAME=your_username")
        print("   JELLYFIN_PASSWORD=your_password")
        print("\n或者创建 .env 文件包含上述配置")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 运行错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()