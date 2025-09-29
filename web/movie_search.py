#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
电影搜索模块
"""

import re
from urllib.parse import quote
from database import db_manager

def extract_movie_code_from_title(title):
    """从标题中提取电影编号"""
    if not title:
        return None
    
    # 常见的电影编号格式
    patterns = [
        r'([A-Z]{2,6}-\d{3,4})',  # 如 SSIS-123, PRED-456
        r'([A-Z]{2,6}\d{3,4})',   # 如 SSIS123, PRED456
        r'(\d{6}[-_]\d{3})',      # 如 123456-789
        r'([A-Z]+[-_]\d+)',       # 如 ABC-123
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title.upper())
        if match:
            return match.group(1)
    
    return None

def query_magnet_link(movie_code, title):
    """查询MongoDB中的magnet_link"""
    if db_manager.mongo_collection is None:
        return None, False
    
    try:
        # 首先尝试用movie_code在title字段中搜索
        query_conditions = []
        
        if movie_code:
            # 在title字段中搜索包含movie_code的记录
            query_conditions.extend([
                {'title': {'$regex': movie_code, '$options': 'i'}},
                {'title': {'$regex': movie_code.replace('-', ''), '$options': 'i'}},
                {'title': {'$regex': movie_code.replace('-', '_'), '$options': 'i'}}
            ])
        
        if title:
            # 从title中提取可能的电影编号
            extracted_code = extract_movie_code_from_title(title)
            if extracted_code and extracted_code != movie_code:
                query_conditions.extend([
                    {'title': {'$regex': extracted_code, '$options': 'i'}},
                    {'title': {'$regex': extracted_code.replace('-', ''), '$options': 'i'}}
                ])
        
        # 执行查询
        for condition in query_conditions:
            result = db_manager.mongo_collection.find_one(condition)
            if result and result.get('magnet_link'):
                return result.get('magnet_link'), True
        
        return None, False
        
    except Exception as e:
        print(f"查询MongoDB出错: {e}")
        return None, False

def find_movie_in_jellyfin_itemId(code,title,jellyfin_checker):
    try: 
        # 先用movie_code搜索
        jellyfin_result = jellyfin_checker.check_movie_exists(code)
        if jellyfin_result.get('exists', False) == False:
            jellyfin_result = jellyfin_checker.check_movie_exists(title)
        if jellyfin_result.get('exists', False) == True:
            print(jellyfin_result)
            return  jellyfin_result['movies'][0]['id']
        return None
    except Exception as e:
        print(f"查询Jellyfin出错: {e}")
        return None
           
              

def process_movie_search_results(movies, jellyfin_checker):
    """处理电影搜索结果"""
    processed_movies = []
    
    for movie in movies:
        movie_code = movie.get('movie_code', '')
        title = movie.get('title', '')
        original_image_url = movie.get('image_url', '')
        
        # 将图片URL转换为代理URL
        proxy_image_url = ''
        if original_image_url:
            proxy_image_url = f"/proxy-image?url={quote(original_image_url, safe='')}"
        
        # 查询MongoDB中的magnet_link
        magnet_link, has_magnet = query_magnet_link(movie_code, title)
        
        # 使用movie_code在Jellyfin中搜索
        jellyfin_exists = False
        jellyfin_details = None
        
        if movie_code and jellyfin_checker:
            try:
                # 先用movie_code搜索
                jellyfin_result = jellyfin_checker.check_movie_exists(movie_code)
                if jellyfin_result.get('exists', False):
                    jellyfin_exists = True
                    jellyfin_details = jellyfin_result.get('movies', [])
                else:
                    # 如果movie_code没找到，尝试用title搜索
                    if title:
                        jellyfin_result = jellyfin_checker.check_movie_exists(title)
                        if jellyfin_result.get('exists', False):
                            jellyfin_exists = True
                            jellyfin_details = jellyfin_result.get('movies', [])
            except Exception as e:
                print(f"检查电影 {movie_code} 在Jellyfin中是否存在时出错: {e}")
                jellyfin_exists = False
        
        # 构建返回的电影数据
        processed_movie = {
            'title': title,
            'image_url': proxy_image_url,
            'original_image_url': original_image_url,
            'movie_code': movie_code,
            'release_date': movie.get('release_date', ''),
            'movie_url': movie.get('movie_url', ''),
            'has_hd': movie.get('has_hd', False),
            'has_subtitle': movie.get('has_subtitle', False),
            'magnet_link': magnet_link,
            'has_magnet': has_magnet,
            'jellyfin_exists': jellyfin_exists,
            'jellyfin_details': jellyfin_details if jellyfin_exists else None
        }
        
        processed_movies.append(processed_movie)
    
    return processed_movies