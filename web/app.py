#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask Web应用 - Jellyfin电影查询
"""

from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
import sys
import os
from jinja2.utils import F
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
    """检查订阅的电影系列"""
    if any(component is None for component in [add_movie_collection, mongo_collection, jellyfin_checker, crawler, found_movies_collection]):
        print("必要组件未初始化，跳过检查")
        return
    
    print("开始执行定时推送任务")
    
    # 从环境变量获取检查间隔天数，默认为7天
    check_interval_days = int(os.getenv('SUBSCRIPTION_CHECK_INTERVAL_DAYS', '7'))
    current_time = datetime.now()
    
    # 收集本次检查发现的所有新电影
    newly_found_movies = []
    
    try:
        # 获取所有订阅
        subscriptions = list(add_movie_collection.find({'type': 'subscription'}))
        
        for subscription in subscriptions:
            series_name = subscription.get('series_name')
            subscription_id = subscription.get('_id')
            last_checked = subscription.get('last_checked')
            
            if not series_name:
                continue
            
            # 检查是否在指定天数内已经检查过
            if last_checked:
                # 如果last_checked是字符串，转换为datetime对象
                if isinstance(last_checked, str):
                    try:
                        last_checked = datetime.fromisoformat(last_checked.replace('Z', '+00:00'))
                    except ValueError:
                        # 如果转换失败，视为需要检查
                        last_checked = None
                
                if last_checked and isinstance(last_checked, datetime):
                    days_since_last_check = (current_time - last_checked).days
                    if days_since_last_check < check_interval_days:
                        print(f"系列 {series_name} 在 {days_since_last_check} 天前已检查过，跳过（间隔设置：{check_interval_days}天）")
                        continue
            
            print(f"检查系列: {series_name}")
            
            try:
                # 使用爬虫获取电影列表
                movies, series_title = crawler.search_movies(series_name)
                
                # 更新订阅的last_checked时间
                add_movie_collection.update_one(
                    {'_id': subscription_id},
                    {
                        '$set': {
                            'last_checked': current_time.isoformat(),
                            'last_check_status': 'success'
                        }
                    }
                )
                
                if not movies:
                    print(f"未找到系列 {series_name} 的电影")
                    continue

                new_movies_count = 0
                found_movies_count = 0
                
                for movie in movies:
                    title = movie.get('title', '')
                    movie_code = movie.get('movie_code', '')
                    
                    if not movie_code:
                        print(f"电影 {title} 没有有效的电影编码")
                        continue
                    else:
                        print(f"电影 {title} 电影编码是：({movie_code})")
                    # 检查Jellyfin中是否存在
                    jellyfin_exists = jellyfin_checker.check_movie_exists(movie_code)['exists']
                    
                    if not jellyfin_exists:
                        found_movies_count += 1
                        new_movies_count += 1
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
                            
                            # 检查是否已经登记过到found_movies表
                            existing_record = found_movies_collection.find_one({
                                'movie_code': movie_code
                            })
                            
                            if not existing_record and magnet_link:
                                # 登记到found_movies表
                                movie_doc = {
                                    'series_name': series_name,
                                    'movie_code': movie_code,
                                    'title': title,
                                    'magnet_link': magnet_link,
                                    'type': 'movie',
                                    'subscription_id': subscription_id,
                                    'found_at': datetime.now(),
                                    'jellyfin_exists': False,
                                    'status': 'new',
                                    'image_url':movie.get('image_url','')
                                }
                                
                                found_movies_collection.insert_one(movie_doc)
                                
                                # 添加到本次发现的电影列表
                                newly_found_movies.append(movie_doc)
                                print(f"发现新电影并已记录: {title} ({movie_code})")
                            else:
                                print(f"电影 {title} ({movie_code}) 已存在，跳过")
                        else:
                            print(f"未找到电影 {title} ({movie_code}) 的磁力链接")
                    else:
                        print(f"电影 {title} ({movie_code}) 在Jellyfin中已存在，跳过")
                # 更新订阅的最后检查时间
                add_movie_collection.update_one(
                    {'_id': subscription_id},
                    {
                        '$set': {
                            'title':series_title,
                            'last_checked': datetime.now(),
                            'total_movies_found': len(movies),
                            'totoal_found_magnet_movies': found_movies_count
                        }
                    }
                ) 
            except Exception as e:
                print(f"检查系列 {series_name} 时出错: {e}")
        
        # 如果有新发现的电影，发送批量邮件通知
        if newly_found_movies:
            send_batch_email_notification(newly_found_movies)
        
        print("定时推送任务执行完成")
        
    except Exception as e:
        print(f"执行定时推送任务时出错: {e}")

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

# 在delete_subscription函数后添加手动触发订阅检查的API
@app.route('/api/trigger-subscription-check', methods=['POST'])
def trigger_subscription_check():

    print("手动触发订阅检查")
    """手动触发订阅检查API"""
    try:
        if add_movie_collection is None or mongo_collection is None or jellyfin_checker is None or crawler is None or found_movies_collection is None:
            return jsonify({
                'success': False,
                'error': '必要组件未初始化，请检查MongoDB、Jellyfin和爬虫连接'
            })
        
        # 在后台线程中执行订阅检查，避免阻塞请求
        def run_check():
            try:
                check_subscribed_series()
            except Exception as e:
                print(f"手动触发订阅检查时出错: {e}")
        
        # 启动后台线程
        thread = threading.Thread(target=run_check)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': '订阅检查已开始执行，请查看控制台日志了解进度'
        })
        
    except Exception as e:
        print(f"触发订阅检查错误: {e}")
        return jsonify({
            'success': False,
            'error': '服务器内部错误'
        })

# 新增API：获取订阅检查状态
@app.route('/api/subscription-check-status', methods=['GET'])
def get_subscription_check_status():
    """获取最近的订阅检查状态"""
    try:
        if add_movie_collection is None:
            return jsonify({
                'success': False,
                'error': 'MongoDB未初始化'
            })
        
        # 获取最近更新的订阅记录
        recent_subscriptions = list(add_movie_collection.find({
            'type': 'subscription',
            'status': 'active'
        }).sort('last_checked', -1).limit(10))
        
        status_info = []
        for sub in recent_subscriptions:
            status_info.append({
                'series_name': sub.get('series_name', ''),
                'last_checked': sub.get('last_checked', '').isoformat() if sub.get('last_checked') else '从未检查',
                'total_movies_found': sub.get('total_movies_found', 0),
                'totoal_found_magnet_movies': sub.get('totoal_found_magnet_movies', 0)
            })
        
        return jsonify({
            'success': True,
            'subscriptions': status_info
        })
        
    except Exception as e:
        print(f"获取订阅检查状态错误: {e}")
        return jsonify({
            'success': False,
            'error': '服务器内部错误'
        })

    except Exception as e:
        print(f"触发订阅检查错误: {e}")
        return jsonify({
            'success': False,
            'error': '服务器内部错误'
        })

def send_batch_email_notification(movies_list):
    """批量发送新电影发现邮件通知"""
    try:
        email_config = app_config.get_email_config()
        
        # 检查是否启用邮件功能
        if not email_config.get('enable_email', False):
            return
            
        # 检查必要的邮件配置
        if not all([email_config.get('sender_email'), 
                   email_config.get('sender_password'),
                   email_config.get('recipient_emails')]):
            print("邮件配置不完整，跳过邮件发送")
            return
        
        # 收集所有磁力链接
        magnet_links = [movie['magnet_link'] for movie in movies_list if movie.get('magnet_link')]
        magnet_links_text = '\n'.join(magnet_links)
        
        # 创建邮件内容
        subject = f"🎬 发现 {len(movies_list)} 部新电影"
        
        # 构建电影列表HTML
        movies_html = ""
        for i, movie in enumerate(movies_list, 1):
            # 获取图片URL，如果没有则使用默认占位符
            image_url = movie.get('image_url', '')
            image_html = ""
            if image_url:
                image_html = f'<img src="{image_url}" alt="{movie["title"]}" style="width: 120px; height: 160px; object-fit: cover; border-radius: 4px; margin-right: 15px; float: left;">'
            
            movies_html += f"""
            <div style="background-color: #f9f9f9; padding: 15px; margin: 15px 0; border-left: 4px solid #007bff; border-radius: 4px; overflow: hidden; min-height: 180px;">
                {image_html}
                <div style="{"margin-left: 140px;" if image_url else ""}">
                    <h4 style="margin: 0 0 8px 0; color: #333;">{i}. {movie['title']}</h4>
                    <p style="margin: 4px 0;"><strong>系列:</strong> {movie['series_name']}</p>
                    <p style="margin: 4px 0;"><strong>代码:</strong> {movie['movie_code']}</p>
                    <p style="margin: 4px 0;"><strong>发现时间:</strong> {movie['found_at'].strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p style="margin: 4px 0;"><strong>磁力链接:</strong> <a href="{movie['magnet_link']}" style="color: #007bff;">点击下载</a></p>
                </div>
                <div style="clear: both;"></div>
            </div>
            """
        
        html_body = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                .copy-button {{
                    background-color: #28a745;
                    color: white;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 14px;
                    margin: 10px 0;
                }}
                .copy-button:hover {{
                    background-color: #218838;
                }}
                .magnet-links {{
                    background-color: #f8f9fa;
                    padding: 15px;
                    border-radius: 5px;
                    border: 1px solid #dee2e6;
                    font-family: monospace;
                    font-size: 12px;
                    max-height: 200px;
                    overflow-y: auto;
                    white-space: pre-wrap;
                    word-break: break-all;
                }}
            </style>
        </head>
        <body>
            <h2>🎬 发现 {len(movies_list)} 部新电影</h2>
            
            <div style="background-color: #d4edda; padding: 15px; border-radius: 5px; margin: 15px 0; border: 1px solid #c3e6cb;">
                <h3 style="margin: 0 0 10px 0; color: #155724;">📋 一键复制所有磁力链接</h3>
                <button class="copy-button" onclick="copyToClipboard()">📋 复制所有磁力链接</button>
                <div id="magnetLinks" class="magnet-links">{magnet_links_text}</div>
            </div>
            
            <h3>📽️ 电影详情列表</h3>
            {movies_html}
            
            <div style="margin-top: 20px; padding: 10px; background-color: #e9ecef; border-radius: 5px;">
                <p style="margin: 0; font-size: 12px; color: #6c757d;"><em>此邮件由电影订阅系统自动发送 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
            </div>
            
            <script>
                function copyToClipboard() {{
                    const magnetLinks = document.getElementById('magnetLinks').textContent;
                    
                    // 创建临时文本区域
                    const textArea = document.createElement('textarea');
                    textArea.value = magnetLinks;
                    document.body.appendChild(textArea);
                    
                    // 选择并复制
                    textArea.select();
                    document.execCommand('copy');
                    
                    // 清理
                    document.body.removeChild(textArea);
                    
                    // 更新按钮文本
                    const button = event.target;
                    const originalText = button.textContent;
                    button.textContent = '✅ 已复制!';
                    button.style.backgroundColor = '#007bff';
                    
                    setTimeout(() => {{
                        button.textContent = originalText;
                        button.style.backgroundColor = '#28a745';
                    }}, 2000);
                }}
            </script>
        </body>
        </html>
        """
        
        # 创建邮件对象
        msg = MIMEMultipart('alternative')
        msg['From'] = email_config['sender_email']
        msg['To'] = ', '.join(email_config['recipient_emails'])
        msg['Subject'] = Header(subject, 'utf-8')
        
        # 添加HTML内容
        html_part = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(html_part)
        
        # 发送邮件
        with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
            server.starttls()
            server.login(email_config['sender_email'], email_config['sender_password'])
            server.send_message(msg)
            
        print(f"批量邮件通知已发送: 共 {len(movies_list)} 部新电影")
        
    except Exception as e:
        print(f"发送批量邮件通知失败: {e}")

def send_email_notification(movie_info):
    """发送新电影发现邮件通知"""
    try:
        email_config = app_config.get_email_config()
        
        # 检查是否启用邮件功能
        if not email_config.get('enable_email', False):
            return
            
        # 检查必要的邮件配置
        if not all([email_config.get('sender_email'), 
                   email_config.get('sender_password'),
                   email_config.get('recipient_emails')]):
            print("邮件配置不完整，跳过邮件发送")
            return
        
        # 创建邮件内容
        subject = f"🎬 发现新电影: {movie_info['title']}"
        
        html_body = f"""
        <html>
        <body>
            <h2>🎬 发现新电影通知</h2>
            <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 10px 0;">
                <p><strong>系列名称:</strong> {movie_info['series_name']}</p>
                <p><strong>电影代码:</strong> {movie_info['movie_code']}</p>
                <p><strong>电影标题:</strong> {movie_info['title']}</p>
                <p><strong>发现时间:</strong> {movie_info['found_at'].strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>磁力链接:</strong> <a href="{movie_info['magnet_link']}">点击下载</a></p>
            </div>
            <p><em>此邮件由电影订阅系统自动发送</em></p>
        </body>
        </html>
        """
        
        # 创建邮件对象
        msg = MIMEMultipart('alternative')
        msg['From'] = email_config['sender_email']
        msg['To'] = ', '.join(email_config['recipient_emails'])
        msg['Subject'] = Header(subject, 'utf-8')
        
        # 添加HTML内容
        html_part = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(html_part)
        
        # 发送邮件
        with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
            server.starttls()
            server.login(email_config['sender_email'], email_config['sender_password'])
            server.send_message(msg)
            
        print(f"邮件通知已发送: {movie_info['title']}")
        
    except Exception as e:
        print(f"发送邮件通知失败: {e}")

@app.route('/subscriptions')
def subscriptions_page():
    """订阅管理页面"""
    return render_template('subscriptions.html')

@app.route('/api/subscription-movies/<series_name>', methods=['GET'])
def get_subscription_movies(series_name):
    """获取指定订阅的电影列表"""
    try:
        if found_movies_collection is None:
            return jsonify({
                'success': False,
                'error': 'MongoDB未初始化'
            })
        
        # 查询found_movies集合中found_movies字段等于series_name的电影
        movies_cursor = found_movies_collection.find({
            'series_name': series_name
        }).sort('found_at', -1)  # 按发现时间倒序排列
        
        movies = []
        for movie_doc in movies_cursor:
            movie_data = {
                'movie_code': movie_doc.get('movie_code', ''),
                'title': movie_doc.get('title', ''),
                'magnet_link': movie_doc.get('magnet_link', ''),
                'found_at': movie_doc.get('found_at', ''),
                'image_url': movie_doc.get('image_url', '')
            }
            
            # 如果有image_url，转换为代理URL
            if movie_data['image_url']:
                movie_data['image_url'] = f"/proxy-image?url={movie_data['image_url']}"
            
            movies.append(movie_data)
        
        return jsonify({
            'success': True,
            'movies': movies,
            'total_count': len(movies)
        })
        
    except Exception as e:
        print(f"获取订阅电影错误: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

    except Exception as e:
        print(f"触发订阅检查错误: {e}")
        return jsonify({
            'success': False,
            'error': '服务器内部错误'
        })

if __name__ == '__main__':
    # 启动定时任务
    start_scheduler()
    app.run(debug=True, host='0.0.0.0', port=5000)


