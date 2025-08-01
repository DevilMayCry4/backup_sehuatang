#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask Web应用 - Jellyfin电影查询
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

# 添加父目录到路径，以便导入项目模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jellyfin_movie_checker import JellyfinMovieChecker
from jellyfin_config import config
from crawler.javbus_crawler import JavBusCrawler
from config import config as app_config

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

# 初始化MongoDB连接
mongo_client = None
mongo_db = None
mongo_collection = None
add_movie_collection = None

def init_mongodb():
    """初始化MongoDB连接"""
    global mongo_client, mongo_db, mongo_collection, add_movie_collection
    try:
        mongo_config = app_config.get_mongo_config()
        mongo_client = MongoClient(mongo_config['uri'], serverSelectionTimeoutMS=5000)
        # 测试连接
        mongo_client.admin.command('ping')
        # 连接到sehuatang_backup数据库
        mongo_db = mongo_client['sehuatang_backup']
        mongo_collection = mongo_db['sehuatang_crawler']
        add_movie_collection = mongo_db['add_movie']  # 新增订阅表
        
        # 创建索引
        add_movie_collection.create_index("series_name")
        add_movie_collection.create_index("movie_code")
        add_movie_collection.create_index("created_at")
        
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

# 初始化Jellyfin检查器
try:
    jellyfin_checker = JellyfinMovieChecker()
except Exception as e:
    print(f"Jellyfin初始化失败: {e}")
    jellyfin_checker = None

# 初始化JavBus爬虫
try:
    crawler = JavBusCrawler()
except Exception as e:
    print(f"JavBusCrawler初始化失败: {e}")
    crawler = None

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

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search_movie():
    """搜索电影API"""
    try:
        data = request.get_json()
        movie_name = data.get('movie_name', '').strip()
        
        if not movie_name:
            return jsonify({
                'success': False,
                'error': '请输入电影名称'
            })
        
        if not jellyfin_checker:
            return jsonify({
                'success': False,
                'error': 'Jellyfin服务未初始化'
            })
        
        if not crawler:
            return jsonify({
                'success': False,
                'error': 'JavBusCrawler未初始化'
            })

        # 执行爬虫搜索
        crawler_result = crawler.crawl_from_url('https://www.javbus.com/series/'+movie_name)
        
        # 处理爬虫结果
        if not crawler_result or 'movies' not in crawler_result:
            return jsonify({
                'success': False,
                'error': '爬虫未返回有效数据'
            })
        
        movies = crawler_result['movies']
        processed_movies = []
        
        # 遍历每个电影，检查在Jellyfin中是否存在
        for movie in movies:
            movie_code = movie.get('movie_code', '')
            title = movie.get('title', '')
            original_image_url = movie.get('image_url', '')
            
            # 将图片URL转换为代理URL
            proxy_image_url = ''
            if original_image_url:
                proxy_image_url = f"/proxy-image?url={requests.utils.quote(original_image_url, safe='')}"
            
            # 查询MongoDB中的magnet_link
            magnet_link, has_magnet = query_magnet_link(movie_code, title)
            
            # 使用movie_code在Jellyfin中搜索
            jellyfin_exists = False
            jellyfin_details = None
            
            if movie_code:
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
                'image_url': proxy_image_url,  # 使用代理URL
                'original_image_url': original_image_url,  # 保留原始URL用于调试
                'movie_code': movie_code,
                'release_date': movie.get('release_date', ''),
                'movie_url': movie.get('movie_url', ''),
                'has_hd': movie.get('has_hd', False),
                'has_subtitle': movie.get('has_subtitle', False),
                'magnet_link': magnet_link,  # 添加磁力链接
                'has_magnet': has_magnet,    # 添加是否有磁力链接的标识
                'jellyfin_exists': jellyfin_exists,
                'jellyfin_details': jellyfin_details if jellyfin_exists else None
            }
            
            processed_movies.append(processed_movie)
        
        # 返回处理后的结果
        result = {
            'total_movies': len(processed_movies),
            'movies': processed_movies,
            'search_term': movie_name,
            'crawler_info': {
                'total_pages_crawled': crawler_result.get('total_pages_crawled', 1),
                'total_movies_found': crawler_result.get('total_movies', len(movies))
            }
        }
        
        return jsonify({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'搜索失败: {str(e)}'
        })

@app.route('/api/config')
def get_config():
    """获取配置信息API"""
    try:
        return jsonify({
            'success': True,
            'config': {
                'server_url': config.get('server_url', ''),
                'client_name': config.get('client_name', ''),
                'jellyfin_available': jellyfin_checker is not None,
                'mongodb_available': mongo_client is not None
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

# 新增API：订阅电影系列
@app.route('/api/subscribe-series', methods=['POST'])
def subscribe_series():
    """订阅电影系列API"""
    try:
        data = request.get_json()
        series_name = data.get('series_name', '').strip()
        
        if not series_name:
            return jsonify({
                'success': False,
                'error': '请输入系列名称'
            })
        
        if add_movie_collection is None:
            return jsonify({
                'success': False,
                'error': 'MongoDB未初始化'
            })
        
        # 检查是否已经订阅
        existing = add_movie_collection.find_one({
            'series_name': series_name,
            'type': 'subscription'
        })
        
        if existing:
            return jsonify({
                'success': False,
                'error': f'已经订阅了系列 "{series_name}"'
            })
        
        # 添加订阅记录
        subscription_doc = {
            'series_name': series_name,
            'type': 'subscription',
            'status': 'active',
            'created_at': datetime.now(),
            'last_checked': None,
            'total_movies_found': 0
        }
        
        result = add_movie_collection.insert_one(subscription_doc)
        
        return jsonify({
            'success': True,
            'message': f'成功订阅系列 "{series_name}"',
            'subscription_id': str(result.inserted_id)
        })
        
    except Exception as e:
        print(f"订阅系列错误: {e}")
        return jsonify({
            'success': False,
            'error': '服务器内部错误'
        })

# 新增API：获取订阅列表
@app.route('/api/subscriptions', methods=['GET'])
def get_subscriptions():
    """获取订阅列表API"""
    try:
        if add_movie_collection is None:
            return jsonify({
                'success': False,
                'error': 'MongoDB未初始化'
            })
        
        # 查询所有订阅
        subscriptions = list(add_movie_collection.find(
            {'type': 'subscription'},
            {'_id': 1, 'series_name': 1, 'status': 1, 'created_at': 1, 
             'last_checked': 1, 'total_movies_found': 1}
        ).sort('created_at', -1))
        
        # 转换ObjectId为字符串
        for sub in subscriptions:
            sub['_id'] = str(sub['_id'])
        
        return jsonify({
            'success': True,
            'subscriptions': subscriptions
        })
        
    except Exception as e:
        print(f"获取订阅列表错误: {e}")
        return jsonify({
            'success': False,
            'error': '服务器内部错误'
        })

# 新增API：删除订阅
@app.route('/api/subscriptions/<subscription_id>', methods=['DELETE'])
def delete_subscription(subscription_id):
    """删除订阅API"""
    try:
        if add_movie_collection is None:
            return jsonify({
                'success': False,
                'error': 'MongoDB未初始化'
            })
        
        # 删除订阅记录
        result = add_movie_collection.delete_one({
            '_id': ObjectId(subscription_id),
            'type': 'subscription'
        })
        
        if result.deleted_count > 0:
            return jsonify({
                'success': True,
                'message': '订阅已删除'
            })
        else:
            return jsonify({
                'success': False,
                'error': '订阅不存在'
            })
        
    except Exception as e:
        print(f"删除订阅错误: {e}")
        return jsonify({
            'success': False,
            'error': '服务器内部错误'
        })

# 定时任务：检查订阅的电影系列
def check_subscribed_series():
    """检查订阅的电影系列，参考search_movie()逻辑"""
    try:
        if  add_movie_collection is None or mongo_collection is None or jellyfin_checker is None or crawler is None:
            print("定时任务跳过：必要组件未初始化")
            return
        
        print("开始执行定时推送任务...")
        
        # 获取所有活跃的订阅
        subscriptions = list(add_movie_collection.find({
            'type': 'subscription',
            'status': 'active'
        }))
        
        for subscription in subscriptions:
            series_name = subscription['series_name']
            subscription_id = subscription['_id']
            
            print(f"检查订阅系列: {series_name}")
            
            try:
                # 使用爬虫获取系列电影列表
                crawler_result = crawler.crawl_from_url(f'https://www.javbus.com/series/{series_name}')
                
                if not crawler_result or 'movies' not in crawler_result:
                    print(f"系列 {series_name} 爬取失败")
                    continue
                
                movies = crawler_result['movies']
                new_movies_count = 0
                
                # 遍历每个电影
                for movie in movies:
                    movie_code = movie.get('movie_code', '')
                    title = movie.get('title', '')
                    
                    if not movie_code:
                        continue
                    
                    # 检查Jellyfin中是否存在
                    jellyfin_exists = False
                    try:
                        jellyfin_result = jellyfin_checker.check_movie_exists(movie_code)
                        if jellyfin_result.get('exists', False):
                            jellyfin_exists = True
                        else:
                            # 尝试用title搜索
                            if title:
                                jellyfin_result = jellyfin_checker.check_movie_exists(title)
                                if jellyfin_result.get('exists', False):
                                    jellyfin_exists = True
                    except Exception as e:
                        print(f"检查电影 {movie_code} 在Jellyfin中是否存在时出错: {e}")
                    
                    # 如果Jellyfin中不存在，检查MongoDB中是否有磁力链接
                    if not jellyfin_exists:
                        # 在sehuatang_crawler表中查找磁力链接
                        magnet_doc = mongo_collection.find_one({
                            '$or': [
                                {'title': {'$regex': movie_code, '$options': 'i'}},
                                {'movie_code': movie_code}
                            ],
                            'magnet_link': {'$exists': True, '$ne': ''}
                        })
                        
                        if magnet_doc:
                            magnet_link = magnet_doc.get('magnet_link', '')
                            
                            # 检查是否已经登记过
                            existing_record = add_movie_collection.find_one({
                                'movie_code': movie_code,
                                'type': 'movie',
                                'subscription_id': subscription_id
                            })
                            
                            if not existing_record and magnet_link:
                                # 登记到add_movie表
                                movie_doc = {
                                    'series_name': series_name,
                                    'movie_code': movie_code,
                                    'title': title,
                                    'magnet_link': magnet_link,
                                    'type': 'movie',
                                    'subscription_id': subscription_id,
                                    'found_at': datetime.now(),
                                    'jellyfin_exists': False,
                                    'status': 'new'
                                }
                                
                                add_movie_collection.insert_one(movie_doc)
                                new_movies_count += 1
                                print(f"新发现电影: {movie_code} - {title}")
                
                # 更新订阅的最后检查时间
                add_movie_collection.update_one(
                    {'_id': subscription_id},
                    {
                        '$set': {
                            'last_checked': datetime.now(),
                            'total_movies_found': subscription.get('total_movies_found', 0) + new_movies_count
                        }
                    }
                )
                
                print(f"系列 {series_name} 检查完成，新发现 {new_movies_count} 部电影")
                
            except Exception as e:
                print(f"检查系列 {series_name} 时出错: {e}")
        
        print("定时推送任务执行完成")
        
    except Exception as e:
        print(f"定时推送任务执行错误: {e}")

# 启动定时任务
def start_scheduler():
    """启动定时任务调度器"""
    # 每天晚上10点执行
    schedule.every().day.at("22:00").do(check_subscribed_series)
    
    # 也可以设置为每小时执行一次用于测试
    # schedule.every().hour.do(check_subscribed_series)
    
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    
    # 在后台线程中运行调度器
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print("定时任务调度器已启动")

if __name__ == '__main__':
    # 启动定时任务
    start_scheduler()
    app.run(debug=True, host='0.0.0.0', port=5000)