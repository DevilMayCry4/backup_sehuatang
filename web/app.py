#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask Web应用 - Jellyfin电影查询 (重构版)
"""

from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
import sys
import os
import requests
from urllib.parse import urlparse
from pymongo import MongoClient
import re
from datetime import datetime, timedelta
from bson import ObjectId
import threading
import time
import schedule
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

# 添加父目录到路径，以便导入项目模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入模块
from database import db_manager
from routes import register_routes
from subscription import start_scheduler
from jellyfin_movie_checker import JellyfinMovieChecker
from crawler.javbus_crawler import JavBusCrawler
from config import config as app_config

# 创建Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# 配置CORS - 允许所有来源访问
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

def init_components():
    """初始化所有组件"""
    # 初始化MongoDB
    db_manager.init_mongodb()
    
    # 初始化Jellyfin检查器
    try:
        jellyfin_checker = JellyfinMovieChecker()
        print("Jellyfin检查器初始化成功")
    except Exception as e:
        print(f"Jellyfin初始化失败: {e}")
        jellyfin_checker = None
    
    # 初始化JavBus爬虫
    try:
        crawler = JavBusCrawler()
        print("JavBus爬虫初始化成功")
    except Exception as e:
        print(f"JavBusCrawler初始化失败: {e}")
        crawler = None
    
    return jellyfin_checker, crawler

 

# 初始化MongoDB连接
mongo_client = None
mongo_db = None
mongo_collection = None
add_movie_collection = None
found_movies_collection = None  # 新增found_movies集合变量

def init_mongodb():
    """初始化MongoDB连接"""
    global mongo_client, mongo_db, mongo_collection, add_movie_collection, found_movies_collection
    try:
        mongo_config = app_config.get_mongo_config()
        mongo_client = MongoClient(mongo_config['uri'], serverSelectionTimeoutMS=5000)
        # 测试连接
        mongo_client.admin.command('ping')
        # 连接到sehuatang_backup数据库
        mongo_db = mongo_client['sehuatang_crawler']
        mongo_collection = mongo_db['thread_details']
        add_movie_collection = mongo_db['add_movie']  # 新增订阅表
        found_movies_collection = mongo_db['found_movies']  # 新增找到的电影表
        
        # 创建索引
        add_movie_collection.create_index("series_name")
        add_movie_collection.create_index("movie_code")
        add_movie_collection.create_index("created_at")
        
        # 为found_movies表创建索引
        found_movies_collection.create_index("movie_code")
        found_movies_collection.create_index("series_name")
        found_movies_collection.create_index("subscription_id")
        found_movies_collection.create_index("found_at")
        
        print("MongoDB连接成功")
        return True
    except Exception as e:
        print(f"MongoDB连接失败: {e}")
        return False

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
    if mongo_collection is None:
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
            result = mongo_collection.find_one(condition)
            if result and result.get('magnet_link'):
                return result.get('magnet_link'), True
        
        return None, False
        
    except Exception as e:
        print(f"查询MongoDB出错: {e}")
        return None, False

# 初始化MongoDB
init_mongodb()

@app.route('/proxy-image')
def proxy_image():
    """图片代理路由 - 解决跨域图片显示问题"""
    image_url = request.args.get('url')
    
    if not image_url:
        return jsonify({'error': '缺少图片URL参数'}), 400
    
    try:
        # 验证URL格式
        parsed_url = urlparse(image_url)
        if not parsed_url.scheme or not parsed_url.netloc:
            return jsonify({'error': '无效的图片URL'}), 400
        
        # 设置请求头，模拟浏览器访问
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': f"{parsed_url.scheme}://{parsed_url.netloc}/",
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache'
        }
        
        # 请求图片
        response = requests.get(image_url, headers=headers, timeout=10, stream=True)
        response.raise_for_status()
        
        # 获取内容类型
        content_type = response.headers.get('Content-Type', 'image/jpeg')
        
        # 返回图片数据
        def generate():
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        
        return Response(
            generate(),
            content_type=content_type,
            headers={
                'Cache-Control': 'public, max-age=3600',  # 缓存1小时
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET',
                'Access-Control-Allow-Headers': 'Content-Type'
            }
        )
        
    except requests.exceptions.RequestException as e:
        print(f"图片代理请求失败: {e}")
        return jsonify({'error': f'图片加载失败: {str(e)}'}), 500
    except Exception as e:
        print(f"图片代理出错: {e}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

 
 
  

if __name__ == '__main__':
    # 初始化组件
    jellyfin_checker, crawler = init_components()
    
    # 注册路由
    register_routes(app, jellyfin_checker, crawler)
    
    # 启动定时任务
    start_scheduler(jellyfin_checker, crawler)
    
    # 启动应用
    print("Flask应用启动中...")
    app.run(debug=True, host='0.0.0.0', port=5000)


