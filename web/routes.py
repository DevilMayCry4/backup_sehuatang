#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路由模块
"""

from flask import render_template, request, jsonify
from urllib.parse import quote
from database import db_manager
from movie_search import process_movie_search_results
from subscription import trigger_subscription_check_async
from image_proxy import proxy_image
 

def register_routes(app, jellyfin_checker, crawler):
    """注册所有路由"""
    
    @app.route('/')
    def index():
        """主页"""
        return render_template('index.html')
    
    @app.route('/subscriptions')
    def subscriptions_page():
        """订阅管理页面"""
        return render_template('subscriptions.html')
    
    @app.route('/proxy-image')
    def proxy_image_route():
        """图片代理路由"""
        image_url = request.args.get('url')
        return proxy_image(image_url)
    
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
            processed_movies = process_movie_search_results(movies, jellyfin_checker)
            
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
            from jellyfin_config import config
            return jsonify({
                'success': True,
                'config': {
                    'server_url': config.get('server_url', ''),
                    'client_name': config.get('client_name', ''),
                    'jellyfin_available': jellyfin_checker is not None,
                    'mongodb_available': db_manager.mongo_client is not None
                }
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            })
    
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
            
            subscription_id = db_manager.create_subscription(series_name)
            
            return jsonify({
                'success': True,
                'message': f'成功订阅系列 "{series_name}"',
                'subscription_id': subscription_id
            })
            
        except Exception as e:
            print(f"订阅系列错误: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            })
    
    @app.route('/api/subscriptions', methods=['GET'])
    def get_subscriptions():
        """获取订阅列表API"""
        try:
            subscriptions = db_manager.get_subscriptions()
            
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
    
    @app.route('/api/subscriptions/<subscription_id>', methods=['DELETE'])
    def delete_subscription(subscription_id):
        """删除订阅API"""
        try:
            success = db_manager.delete_subscription(subscription_id)
            
            if success:
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
    
    @app.route('/api/trigger-subscription-check', methods=['POST'])
    def trigger_subscription_check():
        """手动触发订阅检查API"""
        print("手动触发订阅检查")
        try:
            if any(component is None for component in [db_manager.add_movie_collection, db_manager.mongo_collection, jellyfin_checker, crawler, db_manager.found_movies_collection]):
                return jsonify({
                    'success': False,
                    'error': '必要组件未初始化，请检查MongoDB、Jellyfin和爬虫连接'
                })
            
            # 在后台线程中执行订阅检查，避免阻塞请求
            trigger_subscription_check_async(jellyfin_checker, crawler)
            
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
    
    @app.route('/api/subscription-check-status', methods=['GET'])
    def get_subscription_check_status():
        """获取最近的订阅检查状态"""
        try:
            # 获取最近更新的订阅记录
            recent_subscriptions = list(db_manager.add_movie_collection.find({
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
    
    @app.route('/subscription-movies/<series_name>')
    def subscription_movies_page(series_name):
        """订阅电影列表页面"""
        try:
            # 获取订阅信息
            subscription = db_manager.add_movie_collection.find_one({
                'series_name': series_name,
                'type': 'subscription'
            })
            
            if not subscription:
                return render_template('error.html', 
                                     error_message=f'订阅 "{series_name}" 不存在'), 404
            
            return render_template('subscription_movies.html', 
                                 series_name=series_name,
                                 subscription=subscription)
            
        except Exception as e:
            print(f"获取订阅电影页面错误: {e}")
            return render_template('error.html', 
                                 error_message='加载订阅电影页面失败'), 500
    
    # 在文件末尾添加缺失的路由
    @app.route('/api/subscriptions/<subscription_id>/status', methods=['PUT'])
    def update_subscription_status(subscription_id):
        """更新订阅状态API"""
        try:
            from bson import ObjectId
            
            data = request.get_json()
            new_status = data.get('status', '').strip()
            
            if new_status not in ['active', 'inactive']:
                return jsonify({
                    'success': False,
                    'error': '状态值无效，只能是 active 或 inactive'
                })
            
            # 更新订阅状态
            result = db_manager.update_subscription_status(subscription_id, new_status)
            
            if not result:
                return jsonify({
                    'success': False,
                    'error': '订阅不存在'
                })
            
            return jsonify({
                'success': True,
                'message': f'订阅状态已更新为 {new_status}'
            })
            
        except Exception as e:
            print(f"更新订阅状态错误: {e}")
            return jsonify({
                'success': False,
                'error': '服务器内部错误'
            })
    
    @app.route('/api/crawl-all-star', methods=['POST'])
    def crawl_all_star():
        """更新全部演员电影API"""
        try:
            import crawler.javbus.crawler as javbus_crawler
            # 在后台线程中执行爬虫任务
            import threading
            def run_crawler():
                try:
                    javbus_crawler.craw_all_star()
                    print("全部演员电影更新完成")
                except Exception as e:
                    print(f"全部演员电影更新错误: {e}")
            
            thread = threading.Thread(target=run_crawler)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'success': True,
                'message': '全部演员电影更新任务已开始执行，请查看控制台日志了解进度'
            })
            
        except Exception as e:
            print(f"启动全部演员电影更新错误: {e}")
            return jsonify({
                'success': False,
                'error': f'启动失败: {str(e)}'
            })
    
    @app.route('/api/crawl-top-star', methods=['POST'])
    def crawl_top_star():
        """更新热门演员API"""
        try: 
            # 在后台线程中执行爬虫任务
            import threading 
            def run_crawler():
                try:
                    import crawler.javbus.crawler as javbus_crawler
                    javbus_crawler.craw_top_star()
                    print("热门演员更新完成")
                except Exception as e:
                    print(f"热门演员更新错误: {e}")
            
            thread = threading.Thread(target=run_crawler)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'success': True,
                'message': '热门演员更新任务已开始执行，请查看控制台日志了解进度'
            })
            
        except Exception as e:
            print(f"启动热门演员更新错误: {e}")
            return jsonify({
                'success': False,
                'error': f'启动失败: {str(e)}'
            })
    
    @app.route('/api/update-sehuatang', methods=['POST'])
    def update_sehuatang():
        """更新论坛电影API"""
        try:
            # 在后台线程中执行爬虫任务
            import threading
            def run_crawler():
                try:
                    # 修改导入路径
                    import sys
                    import os
                    crawler_dir = os.path.join(os.path.dirname(__file__), 'crawler')
                    sys.path.insert(0, crawler_dir)
                    
                    from selenium_crawler import ForumSeleniumCrawler
                    crawler_instance = ForumSeleniumCrawler()
                    crawler_instance.update_sehuatang()
                    print("论坛电影更新完成")
                except Exception as e:
                    print(f"论坛电影更新错误: {e}")
                    import traceback
                    traceback.print_exc()
            
            thread = threading.Thread(target=run_crawler)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'success': True,
                'message': '论坛电影更新任务已开始执行，请查看控制台日志了解进度'
            })
            
        except Exception as e:
            print(f"启动论坛电影更新错误: {e}")
            return jsonify({
                'success': False,
                'error': f'启动失败: {str(e)}'
            })

    # 在 register_routes 函数中添加新路由
    
    @app.route('/mobile/movie-detail/<series_name>/<int:movie_index>')
    def mobile_movie_detail(series_name, movie_index):
        """移动端电影详情页面"""
        try:
            # 获取订阅的电影列表
            movies_docs = db_manager.get_subscription_movies(series_name)
            
            if not movies_docs or movie_index >= len(movies_docs):
                return render_template('error.html', 
                                     error_message='电影不存在'), 404
            
            movie = movies_docs[movie_index]
            
            return render_template('movie_detail_mobile.html', 
                                 movie=movie, 
                                 series_name=series_name)
            
        except Exception as e:
            print(f"获取移动端电影详情错误: {e}")
            return render_template('error.html', 
                                 error_message='加载电影详情失败'), 500
    
    @app.route('/actresses')
    def actresses_list():
        page = request.args.get('page', 1, type=int)
        cup_size_filter = request.args.get('cup_size', None)
        per_page = 20
        
        actresses, total = db_manager.get_paginated_actresses(page, per_page, cup_size_filter)
        
        # 定义完整的罩杯尺寸列表 A-M
        all_cup_sizes = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M']
        
        return render_template('actresses.html', 
                             actresses=actresses,
                             page=page,
                             per_page=per_page,
                             total=total,
                             cup_size_filter=cup_size_filter,
                             all_cup_sizes=all_cup_sizes)
    
    @app.route('/actress/<code>')
    def actress_movies(code):
        """演员影片列表"""
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # 获取演员信息
        actress = db_manager.actresses_data_collection.find_one({'code': code})
        # 获取该演员的所有影片(分页)
        movies, total = db_manager.get_actress_movies(actress['name'], page, per_page)
        if not movies:
            movies = []
                                 
        return render_template('actress_movies.html', 
                             actress=actress,
                             movies=movies,
                             page=page,
                             per_page=per_page,
                             total=total)
    
    @app.route('/jav-movie-detail/<movie_code>')
    def actress_movie_detail( movie_code):
        """演员影片详情页面"""
        try:
            # 获取影片详情
            movie = db_manager.javbus_data_collection.find_one({'code': movie_code})
            if not movie:
                return render_template('error.html', 
                                     error_message='影片不存在'), 404
            magnet_links = db_manager.parser_magnet_links_to_array(movie)
            movie['magnet_links'] = magnet_links
            parse_actress_to_array = db_manager.parse_actress_to_array(movie)
            movie['actresses'] = parse_actress_to_array
            return render_template('jav_movie_detail.html',  
                                 movie=movie)
            
        except Exception as e:
            print(f"获取演员影片详情错误: {e}")
            return render_template('error.html', 
                                 error_message="获取演员影片详情错误"), 500

 
    @app.route('/api/subscription-movies/<series_name>', methods=['GET'])
    def get_subscription_movies(series_name):
        """获取指定订阅的电影列表"""
        try:
            movies_docs = db_manager.get_subscription_movies(series_name)
            
            movies = []
            for movie_doc in movies_docs:
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
    