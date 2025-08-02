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

# 初始化所有组件（移到模块级别）
jellyfin_checker, crawler = init_components()

# 注册路由（移到模块级别）
register_routes(app, jellyfin_checker, crawler)

# 启动定时任务（移到模块级别）
start_scheduler(jellyfin_checker, crawler)

if __name__ == '__main__':
    print("Flask应用启动中...")
    app.run(debug=False, host='0.0.0.0', port=5000)


