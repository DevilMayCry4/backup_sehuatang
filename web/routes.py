#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路由模块
"""

from flask import render_template, request, jsonify, session, redirect, url_for
from urllib.parse import quote
from database import db_manager
from movie_search import process_movie_search_results, find_movie_in_jellyfin_itemId
from subscription import trigger_subscription_check_async
from image_proxy import proxy_image
from web import app_logger
import os
import sys
from datetime import datetime, timedelta
import multiprocessing
from flask import send_file

def register_routes(app, jellyfin_checker, crawler):
    """注册所有路由"""
    
    # 导入装饰器
    from app import login_required, api_login_required
    
    @app.route('/login')
    def login_page():
        """登录页面"""
        return render_template('login.html')
    
    @app.route('/api/login', methods=['POST'])
    def login():
        """用户登录API"""
        try:
            data = request.get_json()
            username = data.get('username', '').strip()
            password = data.get('password', '').strip()
            
            if not username or not password:
                return jsonify({
                    'success': False,
                    'error': '请输入用户名和密码'
                })
            
            # 验证用户
            user_info = db_manager.authenticate_user(username, password)
            if not user_info:
                return jsonify({
                    'success': False,
                    'error': '用户名或密码错误'
                })
            
            # 创建会话
            session_id = db_manager.create_user_session(user_info)
            if not session_id:
                return jsonify({
                    'success': False,
                    'error': '创建会话失败'
                })
            
            # 设置session
            session['session_id'] = session_id
            session['username'] = user_info['username']
            session.permanent = True
            
            return jsonify({
                'success': True,
                'message': '登录成功',
                'user': {
                    'username': user_info['username'],
                    'role': user_info['role']
                }
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'登录失败: {str(e)}'
            })
    
    @app.route('/api/logout', methods=['POST'])
    def logout():
        """用户退出登录API"""
        try:
            if 'session_id' in session:
                db_manager.delete_user_session(session['session_id'])
            
            session.clear()
            
            return jsonify({
                'success': True,
                'message': '退出登录成功'
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'退出登录失败: {str(e)}'
            })
    
    @app.route('/api/check-auth')
    def check_auth():
        """检查用户认证状态API"""
        try:
            if 'session_id' not in session:
                return jsonify({
                    'authenticated': False
                })
            
            user_info = db_manager.get_user_session(session['session_id'])
            if not user_info:
                session.clear()
                return jsonify({
                    'authenticated': False
                })
            
            return jsonify({
                'authenticated': True,
                'user': {
                    'username': user_info['username'],
                    'role': user_info['role']
                }
            })
            
        except Exception as e:
            return jsonify({
                'authenticated': False,
                'error': str(e)
            })
    
    @app.route('/api/change-password', methods=['POST'])
    @api_login_required
    def change_password():
        """修改密码API"""
        try:
            data = request.get_json()
            old_password = data.get('old_password', '').strip()
            new_password = data.get('new_password', '').strip()
            confirm_password = data.get('confirm_password', '').strip()
            
            # 验证输入
            if not old_password or not new_password or not confirm_password:
                return jsonify({
                    'success': False,
                    'error': '请填写所有密码字段'
                })
            
            if new_password != confirm_password:
                return jsonify({
                    'success': False,
                    'error': '新密码和确认密码不一致'
                })
            
            if len(new_password) < 6:
                return jsonify({
                    'success': False,
                    'error': '新密码长度至少6位'
                })
            
            if old_password == new_password:
                return jsonify({
                    'success': False,
                    'error': '新密码不能与原密码相同'
                })
            
            # 获取当前用户信息
            user_info = db_manager.get_user_session(session['session_id'])
            if not user_info:
                return jsonify({
                    'success': False,
                    'error': '用户会话无效'
                })
            
            # 修改密码
            result = db_manager.change_password(user_info['username'], old_password, new_password)
            
            if result['success']:
                # 密码修改成功后，清除所有会话，要求重新登录
                db_manager.delete_user_session(session['session_id'])
                session.clear()
                
                return jsonify({
                    'success': True,
                    'message': '密码修改成功，请重新登录',
                    'redirect': '/login'
                })
            else:
                return jsonify(result)
                
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'修改密码失败: {str(e)}'
            })
    
    @app.route('/')
    @login_required
    def index():
        """主页"""
        return render_template('index.html')
    
    @app.route('/subscriptions')
    @login_required
    def subscriptions_page():
        """订阅管理页面"""
        return render_template('subscriptions.html')
    
    @app.route('/favorites')
    @login_required
    def favorites_page():
        """收藏页面"""
        return render_template('favorites.html')
    
    @app.route('/actress-favorites')
    @login_required
    def actress_favorites():
        """演员收藏页面"""
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '', type=str)
        cup_size = request.args.get('cup_size', '', type=str)
        sort_order = request.args.get('sort', 'latest', type=str)
        
        # 获取当前用户ID
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login_page'))
        
        # 获取收藏演员数据
        result = db_manager.get_actress_favorites(
            user_id=user_id,
            page=page,
            per_page=20,
            search=search,
            cup_size=cup_size,
            sort_order=sort_order
        )
        
        return render_template('actress_favorites.html', 
                             actresses=result['favorites'],
                             pagination=result['pagination'],
                             current_search=search,
                             current_cup_size=cup_size,
                             current_sort=sort_order)

    @app.route('/series-favorites')
    @login_required
    def series_favorites():
        """系列收藏页面"""
        return render_template('series_favorites.html')

    @app.route('/studio-favorites')
    @login_required
    def studio_favorites():
        """厂商收藏页面"""
        return render_template('studio_favorites.html')
    
    @app.route('/proxy-image')
    def proxy_image_route():
        """图片代理路由"""
        image_url = request.args.get('url')
        return proxy_image(image_url)
    
    @app.route('/search', methods=['POST'])
    @api_login_required
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
    @api_login_required
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
    @api_login_required
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
            # 在后台进程中执行爬虫任务
            
            def run_crawler():
                try:
                    javbus_crawler.craw_all_star()
                    app_logger.info("全部演员电影更新完成")
                except Exception as e:
                    app_logger.error(f"全部演员电影更新错误: {e}")
            
            process = multiprocessing.Process(target=run_crawler)
            process.daemon = True
            process.start()
            
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
            def run_crawler():
                try:
                    import crawler.javbus.crawler as javbus_crawler
                    javbus_crawler.craw_top_star()
                    print("热门演员更新完成")
                except Exception as e:
                    print(f"热门演员更新错误: {e}")
            
            process = multiprocessing.Process(target=run_crawler)
            process.daemon = True
            process.start()
            
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
    @login_required
    def actresses_list():
        page = request.args.get('page', 1, type=int)
        cup_size_filter = request.args.get('cup_size', None)
        per_page = 20
        
        # 设置用户ID到session中，供收藏功能使用
        if 'session_id' in session:
            user_info = db_manager.get_user_session(session['session_id'])
            if user_info:
                session['user_id'] = user_info.get('user_id') or str(user_info.get('_id'))
        
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
        search_keyword = request.args.get('search', '', type=str)
        is_single_param = request.args.get('is_single', None)
        is_subtitle_param = request.args.get('is_subtitle', None)
        is_sehuatang_magnet_param = request.args.get('is_sehuatang_magnet', None)
        per_page = 20
        
        # 处理筛选参数
        is_single = None
        if is_single_param == 'true':
            is_single = True
        elif is_single_param == 'false':
            is_single = False
        
        is_subtitle = None
        if is_subtitle_param == 'true':
            is_subtitle = True
        elif is_subtitle_param == 'false':
            is_subtitle = False
            
        is_sehuatang_magnet = None
        if is_sehuatang_magnet_param == 'true':
            is_sehuatang_magnet = True
        elif is_sehuatang_magnet_param == 'false':
            is_sehuatang_magnet = None
        
        # 获取演员信息
        actress = db_manager.actresses_data_collection.find_one({'code': code})
        # 获取该演员的所有影片(分页)，支持搜索和筛选
        movies, total = db_manager.get_actress_movies(
            actress['name'], page, per_page, search_keyword, is_single, is_subtitle, is_sehuatang_magnet
        )
        if not movies:
            movies = []
                             
        return render_template('actress_movies.html', 
                             actress=actress,
                             movies=movies,
                             page=page,
                             per_page=per_page,
                             total=total,
                             search_keyword=search_keyword,
                             is_single_filter=is_single_param,
                             is_subtitle_filter=is_subtitle_param,
                             is_sehuatang_magnet_filter=is_sehuatang_magnet_param)
    
    @app.route('/jav-movie-detail/<movie_code>')
    def actress_movie_detail( movie_code):
        """演员影片详情页面"""
        try:
            # 获取影片详情
            movie = db_manager.getMovieByCode(movie_code)
            if not movie:
                return render_template('error.html', 
                                     error_message='影片不存在'), 404
            return render_template('jav_movie_detail.html',  
                                 movie=movie,
                                 db_manager=db_manager,itemId=movie.get('presentation_key', None))
            
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

    @app.route('/api/retry-failed-movies', methods=['POST'])
    def retry_failed_movies():
        """重试失败电影API"""
        try:
            # 在后台线程中执行重试任务
            import threading
            def run_retry():
                try:
                    # 获取待重试的 URL
                    retry_urls = db_manager.get_pending_retry_urls(limit=1000)
                    
                    if not retry_urls:
                        print("没有待重试的 URL")
                        return
                    
                    print(f"开始重试 {len(retry_urls)} 个失败的 URL")
                    
                    # 导入爬虫模块
                    import sys
                    import os
                    crawler_dir = os.path.join(os.path.dirname(__file__), 'crawler')
                    sys.path.insert(0, crawler_dir) 
                    success_count = 0
                    failed_count = 0
                    import crawler.javbus.crawler as javbus_crawler
                    for retry_url in retry_urls:
                        url = retry_url['url']
                        retry_count = retry_url.get('retry_count', 0)
                        
                        try:
                            app_logger.debug(f"重试处理 URL: {url}")
                            
                            # 根据 URL 类型选择处理方法
                           
                            result = javbus_crawler.process_single_url(url)
                            success = result is not None
                             
                            
                            if success:
                                success_count += 1
                                db_manager.remove_retry(url)
                                app_logger.debug(f"重试成功: {url}")
                            else:
                                failed_count += 1
                                app_logger.debug(f"重试失败: {url}")
                                
                        except Exception as e:
                            failed_count += 1
                            app_logger.debug(f"重试 URL {url} 时发生错误: {e}")
                            db_manager.update_retry_status(url, False, retry_count)
                    
                    app_logger.debug(f"重试完成: 成功 {success_count} 个，失败 {failed_count} 个")
                    
                except Exception as e:
                    print(f"重试失败电影错误: {e}")
                    import traceback
                    traceback.print_exc()
            
            import multiprocessing 
            process = multiprocessing.Process(target=run_retry)
            process.daemon = True
            process.start()
             
            
            return jsonify({
                'success': True,
                'message': '失败电影重试任务已开始执行，请查看控制台日志了解进度'
            })
            
        except Exception as e:
            print(f"启动失败电影重试错误: {e}")
            return jsonify({
                'success': False,
                'error': f'启动失败: {str(e)}'
            })

    @app.route('/api/retry-failed-images', methods=['POST'])
    @api_login_required
    def retry_failed_images():
        """重试失败图片API"""

      

        try:
            import threading
            
            def run_retry():
                try:
                    # 获取失败的图片记录
                    failed_images = db_manager.get_retry_image_urls(limit=1000)
                    
                    if not failed_images:
                        app_logger.info("没有失败的图片需要重试")
                        return
                    
                    app_logger.info(f"开始重试 {len(failed_images)} 个失败的图片")
                    
                    success_count = 0
                    failed_count = 0
                    
                    # 导入图片下载模块
                    import sys
                    import os
                    crawler_dir = os.path.join(os.path.dirname(__file__), 'crawler')
                    sys.path.insert(0, crawler_dir)
                    
                    import crawler.javbus.pageparser as pageparser
                    
                    for failed_image in failed_images:
                        image_url = failed_image['image_url']
                        movie_code = failed_image.get('movie_code', 'unknown')
                        
                        try:
                            app_logger.info(f"重试下载图片: {image_url}")
                            
                            # 构建保存路径
                            save_dir = os.path.join(app.static_folder, 'images', 'covers', movie_code)
                            cover_filename = f"{movie_code}_cover.jpg"
                            
                            # 重试下载图片
                            result = pageparser.download_image(image_url, save_dir, cover_filename, movie_code,remove=True)
                            
                            if result:
                                success_count += 1
                                # 从失败记录中删除
                                db_manager.remove_failed_image(image_url)
                                app_logger.info(f"图片重试下载成功: {image_url}")
                            else:
                                failed_count += 1
                                app_logger.warning(f"图片重试下载失败: {image_url}")
                                
                        except Exception as e:
                            failed_count += 1
                            app_logger.error(f"重试下载图片 {image_url} 时发生错误: {e}")
                    
                    app_logger.info(f"图片重试完成: 成功 {success_count} 个，失败 {failed_count} 个")
                    
                except Exception as e:
                    app_logger.error(f"重试失败图片错误: {e}")
                    import traceback
                    traceback.print_exc()
            
            # 在后台线程中执行重试
            thread = threading.Thread(target=run_retry)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'success': True,
                'message': '失败图片重试任务已开始执行，请查看控制台日志了解进度'
            })
            
        except Exception as e:
            app_logger.error(f"启动失败图片重试错误: {e}")
            return jsonify({
                'success': False,
                'error': f'启动失败: {str(e)}'
            })

    @app.route('/api/backup-images', methods=['POST'])
    @api_login_required
    def backup_images():
        """备份图片API"""
        try:
            import threading
            import zipfile
            import time
            
            def run_backup():
                try:
                    # 图片目录路径
                    covers_dir = os.path.join(app.static_folder, 'images', 'covers')
                    
                    if not os.path.exists(covers_dir):
                        app_logger.error(f"图片目录不存在: {covers_dir}")
                        return
                    
                    # 获取已备份的文件夹
                    backed_up_folders = db_manager.get_backed_up_folders()
                    
                    # 获取所有文件夹
                    all_folders = []
                    new_folders = []
                    
                    for item in os.listdir(covers_dir):
                        item_path = os.path.join(covers_dir, item)
                        if os.path.isdir(item_path):
                            all_folders.append(item)
                            if item not in backed_up_folders:
                                new_folders.append(item)
                    
                    if not new_folders:
                        app_logger.info("没有新的文件夹需要备份")
                        return
                    
                    # 创建备份文件名
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    backup_filename = f"covers_backup_{timestamp}.zip"
                    backup_path = os.path.join(app.static_folder, 'backups', backup_filename)
                    
                    # 确保备份目录存在
                    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                    
                    app_logger.info(f"开始备份 {len(new_folders)} 个新文件夹到 {backup_filename}")
                    
                    # 创建压缩包
                    total_size = 0
                    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for folder_name in new_folders:
                            folder_path = os.path.join(covers_dir, folder_name)
                            
                            # 添加文件夹中的所有文件
                            for root, dirs, files in os.walk(folder_path):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    # 计算相对路径
                                    arcname = os.path.relpath(file_path, covers_dir)
                                    zipf.write(file_path, arcname)
                                    total_size += os.path.getsize(file_path)
                    
                    # 保存备份记录
                    backup_info = {
                        'backup_file': backup_filename,
                        'folders_backed_up': new_folders,
                        'total_folders': len(new_folders),
                        'backup_size': total_size
                    }
                    
                    db_manager.save_backup_record(backup_info)
                    
                    app_logger.info(f"备份完成: {backup_filename}, 大小: {total_size / 1024 / 1024:.2f} MB")
                    
                except Exception as e:
                    app_logger.error(f"备份过程中发生错误: {e}")
                    import traceback
                    traceback.print_exc()
            
            # 在后台线程中执行备份
            thread = threading.Thread(target=run_backup)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'success': True,
                'message': '图片备份任务已开始执行，请查看控制台日志了解进度'
            })
            
        except Exception as e:
            app_logger.error(f"启动图片备份错误: {e}")
            return jsonify({
                'success': False,
                'error': f'启动备份失败: {str(e)}'
            })
    
    @app.route('/api/backup-records', methods=['GET'])
    @api_login_required
    def get_backup_records():
        """获取备份记录API"""
        try:
            records = db_manager.get_backup_records()
            
            # 格式化记录
            formatted_records = []
            for record in records:
                formatted_record = {
                    'id': str(record['_id']),
                    'backup_file': record.get('backup_file', ''),
                    'total_folders': record.get('total_folders', 0),
                    'backup_size': record.get('backup_size', 0),
                    'created_at': record.get('created_at', '').isoformat() if record.get('created_at') else '',
                    'status': record.get('status', 'unknown')
                }
                formatted_records.append(formatted_record)
            
            return jsonify({
                'success': True,
                'records': formatted_records
            })
            
        except Exception as e:
            app_logger.error(f"获取备份记录错误: {e}")
            return jsonify({
                'success': False,
                'error': f'获取备份记录失败: {str(e)}'
            })
    
    @app.route('/api/crawler-status', methods=['GET'])
    @api_login_required
    def get_crawler_status():
        """获取爬虫运行状态API"""
        try:
            # 获取爬虫状态信息
            jav_status = db_manager.get_crawler_running_status('jav')
            sehuatang_status = db_manager.get_crawler_running_status('sehuatang')
            
            return jsonify({
                'success': True,
                'status': {
                    'jav': jav_status,
                    'sehuatang': sehuatang_status
                }
            })
            
        except Exception as e:
            app_logger.error(f"获取爬虫状态错误: {e}")
            return jsonify({
                'success': False,
                'error': f'获取爬虫状态失败: {str(e)}'
            })
    
    @app.route('/series/<series_name>')
    @login_required
    def series_movies_page(series_name):
        """系列电影列表页面"""
        try:
            # 获取查询参数
            page = int(request.args.get('page', 1))
            per_page = 20
            search_keyword = request.args.get('search', '').strip()
            is_single_filter = request.args.get('is_single', '')
            is_subtitle_filter = request.args.get('is_subtitle', '')
            
            # 转换筛选参数
            is_single = None
            if is_single_filter == 'true':
                is_single = True
            elif is_single_filter == 'false':
                is_single = False
                
            is_subtitle = None
            if is_subtitle_filter == 'true':
                is_subtitle = True
            elif is_subtitle_filter == 'false':
                is_subtitle = False
            
            # 获取系列电影数据
            movies, total = db_manager.get_series_movies(
                series_name=series_name,
                page=page,
                per_page=per_page,
                search_keyword=search_keyword if search_keyword else None,
                is_single=is_single,
                is_subtitle=is_subtitle
            )
            
            if movies is None:
                movies = []
                total = 0
            
            return render_template('series_movies.html',
                                movies=movies,
                                page=page,
                                per_page=per_page,
                                total=total,
                                series_name=series_name,
                                search_keyword=search_keyword,
                                is_single_filter=is_single_filter,
                                is_subtitle_filter=is_subtitle_filter)
                                
        except Exception as e:
            app_logger.error(f"系列电影列表页面错误: {e}")
            return render_template('error.html', error_message=f"加载系列 '{series_name}' 的电影列表失败")
    
    @app.route('/movies')
    @login_required
    def movies_page():
        """电影列表页面"""
        try:
            # 获取查询参数
            page = int(request.args.get('page', 1))
            per_page = 20
            search_keyword = request.args.get('search', '').strip()
            is_single_filter = request.args.get('is_single', '')
            is_subtitle_filter = request.args.get('is_subtitle', '')
            is_sehuatang_magnet_filter = request.args.get('is_sehuatang_magnet', '')
            sort_by = request.args.get('sort', 'release_date')
            
            # 转换筛选参数
            is_single = None
            if is_single_filter == 'true':
                is_single = True
            elif is_single_filter == 'false':
                is_single = False
                
            is_subtitle = None
            if is_subtitle_filter == 'true':
                is_subtitle = True
            elif is_subtitle_filter == 'false':
                is_subtitle = False
                
            is_sehuatang_magnet = None
            if is_sehuatang_magnet_filter == 'true':
                is_sehuatang_magnet = True
            elif is_sehuatang_magnet_filter == 'false':
                is_sehuatang_magnet = False
            
            # 获取电影数据
            movies, total = db_manager.get_all_movies(
                page=page,
                per_page=per_page,
                search_keyword=search_keyword if search_keyword else None,
                is_single=is_single,
                is_subtitle=is_subtitle,
                is_sehuatang_magnet=is_sehuatang_magnet,
                sort_by=sort_by
            )
            
            if movies is None:
                movies = []
                total = 0
            
            return render_template('movies.html',
                                movies=movies,
                                page=page,
                                per_page=per_page,
                                total=total,
                                search_keyword=search_keyword,
                                is_single_filter=is_single_filter,
                                is_subtitle_filter=is_subtitle_filter,
                                is_sehuatang_magnet_filter=is_sehuatang_magnet_filter,
                                sort_by=sort_by)
                                
        except Exception as e:
            app_logger.error(f"电影列表页面错误: {e}")
            return render_template('error.html', error_message="加载电影列表失败")
    
    @app.route('/studio/<studio_name>')
    @login_required
    def studio_movies_page(studio_name):
        """制作商电影列表页面"""
        try:
            # 获取查询参数
            page = int(request.args.get('page', 1))
            per_page = 20
            search_keyword = request.args.get('search', '').strip()
            is_single_filter = request.args.get('is_single', '')
            is_subtitle_filter = request.args.get('is_subtitle', '')
            
            # 转换筛选参数
            is_single = None
            if is_single_filter == 'true':
                is_single = True
            elif is_single_filter == 'false':
                is_single = False
                
            is_subtitle = None
            if is_subtitle_filter == 'true':
                is_subtitle = True
            elif is_subtitle_filter == 'false':
                is_subtitle = False
            
            # 获取制作商电影数据
            movies, total = db_manager.get_studio_movies(
                studio_name=studio_name,
                page=page,
                per_page=per_page,
                search_keyword=search_keyword if search_keyword else None,
                is_single=is_single,
                is_subtitle=is_subtitle
            )
            
            if movies is None:
                movies = []
                total = 0
            
            return render_template('studio_movies.html',
                                movies=movies,
                                page=page,
                                per_page=per_page,
                                total=total,
                                studio_name=studio_name,
                                search_keyword=search_keyword,
                                is_single_filter=is_single_filter,
                                is_subtitle_filter=is_subtitle_filter)
                                
        except Exception as e:
            app_logger.error(f"制作商电影列表页面错误: {e}")
            return render_template('error.html', error_message=f"加载制作商 '{studio_name}' 的电影列表失败")
    
    @app.route('/genres')
    @login_required
    def genres_page():
        """分类管理页面"""
        try:
            # 获取所有分类数据，按分类分组
            genres_by_category = db_manager.get_genres_by_category()
            
            return render_template('genres.html', 
                                 genres_by_category=genres_by_category)
                                 
        except Exception as e:
            app_logger.error(f"分类管理页面错误: {e}")
            return render_template('error.html', error_message="加载分类管理页面失败")
    
    @app.route('/genres/search')
    @login_required
    def genres_search_results():
        """分类搜索结果页面"""
        try:
            # 获取查询参数
            page = int(request.args.get('page', 1))
            per_page = 20
            genre_names = request.args.getlist('genres')  # 支持多个分类
            print(genre_names)
            search_keyword = request.args.get('search', '').strip()
            is_single_filter = request.args.get('is_single', '')
            is_subtitle_filter = request.args.get('is_subtitle', '')
            is_sehuatang_magnet_filter = request.args.get('is_sehuatang_magnet', '')
            sort_by = request.args.get('sort_by', 'release_date')
            
            # 转换筛选参数
            is_single = None
            if is_single_filter == 'true':
                is_single = True
            elif is_single_filter == 'false':
                is_single = False
                
            is_subtitle = None
            if is_subtitle_filter == 'true':
                is_subtitle = True
            elif is_subtitle_filter == 'false':
                is_subtitle = False
            
            is_sehuatang_magnet = None
            if is_sehuatang_magnet_filter == 'true':
                is_sehuatang_magnet = True
            elif is_sehuatang_magnet_filter == 'false':
                is_sehuatang_magnet = None
            
            # 搜索影片
            movies, total = db_manager.search_movies_by_genres(
                names=genre_names if genre_names else None,
                page=page,
                per_page=per_page,
                search_keyword=search_keyword if search_keyword else None,
                is_single=is_single,
                is_subtitle=is_subtitle,
                is_sehuatang_magnet=is_sehuatang_magnet,
                sort_by=sort_by
            )
            
            if movies is None:
                movies = []
                total = 0
            
            # 计算分页信息
            total_pages = (total + per_page - 1) // per_page
            
            pagination = {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': total_pages,
                'has_prev': page > 1,
                'has_next': page < total_pages,
                'prev_num': page - 1 if page > 1 else None,
                'next_num': page + 1 if page < total_pages else None
            }
            
            return render_template('genres_search_results.html',
                                movies=movies,
                                pagination=pagination,
                                genre_names=genre_names,
                                search_keyword=search_keyword,
                                is_single_filter=is_single_filter,
                                is_subtitle_filter=is_subtitle_filter,
                                is_sehuatang_magnet_filter=is_sehuatang_magnet_filter,
                                sort_by=sort_by)
                                
        except Exception as e:
            app_logger.error(f"分类搜索结果页面错误: {e}")
            return render_template('error.html', error_message="加载搜索结果失败")
    
    # @app.route('/api/genres/search', methods=['POST'])
    # @api_login_required
    # def search_movies_by_genres_api():
    #     """根据分类搜索影片API"""
    #     try:
    #         data = request.get_json()
            
    #         # 获取搜索参数
    #         genre_names = data.get('genre_names', [])  # 选中的分类名称列表
    #         search_keyword = data.get('search_keyword', '').strip()
    #         is_single_filter = data.get('is_single', '')
    #         is_subtitle_filter = data.get('is_subtitle', '')
    #         page = int(data.get('page', 1))
    #         per_page = int(data.get('per_page', 20))
    #         sort_by = data.get('sort_by', 'release_date')
            
    #         # 转换筛选参数
    #         is_single = None
    #         if is_single_filter == 'true':
    #             is_single = True
    #         elif is_single_filter == 'false':
    #             is_single = False
                
    #         is_subtitle = None
    #         if is_subtitle_filter == 'true':
    #             is_subtitle = True
    #         elif is_subtitle_filter == 'false':
    #             is_subtitle = False
            
            
    #         # 搜索影片
    #         movies, total = db_manager.search_movies_by_genres(
    #             names=genre_names if genre_names else None,
    #             page=page,
    #             per_page=per_page,
    #             search_keyword=search_keyword if search_keyword else None,
    #             is_single=is_single,
    #             is_subtitle=is_subtitle,
    #             sort_by=sort_by
    #         )

    #         print(movies)

    #         if movies is None:
    #             movies = []
    #             total = 0
            
    #         # 计算分页信息
    #         total_pages = (total + per_page - 1) // per_page
            
    #         return jsonify({
    #             'success': True,
    #             'movies': movies,
    #             'pagination': {
    #                 'page': page,
    #                 'per_page': per_page,
    #                 'total': total,
    #                 'pages': total_pages,
    #                 'has_prev': page > 1,
    #                 'has_next': page < total_pages,
    #                 'prev_num': page - 1 if page > 1 else None,
    #                 'next_num': page + 1 if page < total_pages else None
    #             }
    #         })
            
    #     except Exception as e:
    #         app_logger.error(f"分类搜索影片API错误: {e}")
    #         return jsonify({
    #             'success': False,
    #             'error': '搜索失败，请稍后重试'
    #         })
    
    @app.route('/api/genres/categories')
    @api_login_required
    def get_genres_categories_api():
        """获取所有分类数据API"""
        try:
            genres_by_category = db_manager.get_genres_by_category()
            
            return jsonify({
                'success': True,
                'genres_by_category': genres_by_category
            })
            
        except Exception as e:
            app_logger.error(f"获取分类数据API错误: {e}")
            return jsonify({
                'success': False,
                'error': '获取分类数据失败'
            })
    
    # 演员收藏相关API路由
    @app.route('/api/actress/favorite', methods=['POST'])
    @api_login_required
    def add_actress_favorite():
        """添加演员收藏API"""
        try:
            data = request.get_json()
            actress_code = data.get('actress_code')
            actress_name = data.get('actress_name')
            
            if not actress_code or not actress_name:
                return jsonify({
                    'success': False,
                    'error': '演员代码和姓名不能为空'
                })
            
            # 获取当前用户ID
            user_id = session.get('user_id') 
            if not user_id:
                return jsonify({
                    'success': False,   
                    'error': '用户未登录'
                })
            
            # 检查是否已经收藏
            if db_manager.is_actress_favorited(user_id, actress_code):
                return jsonify({
                    'success': False,
                    'error': '该演员已在收藏列表中'
                })
            
            # 添加收藏
            result = db_manager.add_actress_favorite(user_id, actress_code, actress_name)
            
            return jsonify(result)
            
        except Exception as e:
            app_logger.error(f"添加演员收藏API错误: {e}")
            return jsonify({
                'success': False,
                'error': '添加收藏失败，请稍后重试'
            })
    
    @app.route('/api/actress/favorite', methods=['DELETE'])
    @api_login_required
    def remove_actress_favorite():
        """取消演员收藏API"""
        try:
            data = request.get_json()
            actress_code = data.get('actress_code')
            
            if not actress_code:
                return jsonify({
                    'success': False,
                    'error': '演员代码不能为空'
                })
            
            # 获取当前用户ID
            user_id = session.get('user_id')
            if not user_id:
                return jsonify({
                    'success': False,
                    'error': '用户未登录'
                })
            
            # 取消收藏
            result = db_manager.remove_actress_favorite(user_id, actress_code)
            
            return jsonify(result)
            
        except Exception as e:
            app_logger.error(f"取消演员收藏API错误: {e}")
            return jsonify({
                'success': False,
                'error': '取消收藏失败，请稍后重试'
            })
    
    @app.route('/api/actress/favorite/check/<actress_code>')
    @api_login_required
    def check_actress_favorite(actress_code):
        """检查演员收藏状态API"""
        try:
            # 获取当前用户ID
            user_id = session.get('user_id')
            if not user_id:
                return jsonify({
                    'success': False,
                    'error': '用户未登录'
                })
            
            # 检查收藏状态
            is_favorited = db_manager.is_actress_favorited(user_id, actress_code)
            
            return jsonify({
                'success': True,
                'is_favorited': is_favorited
            })
            
        except Exception as e:
            app_logger.error(f"检查演员收藏状态API错误: {e}")
            return jsonify({
                'success': False,
                'error': '检查收藏状态失败'
            })
    
    @app.route('/api/actress/favorites')
    @api_login_required
    def get_user_favorite_actresses():
        """获取用户收藏的演员列表API"""
        try:
            # 获取查询参数
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))
            # 获取当前用户ID
            user_id = session.get('user_id')
            if not user_id:
                return jsonify({
                    'success': False,
                    'error': '用户未登录'
                })
            
            # 获取收藏的演员列表
            actresses, total = db_manager.get_user_favorite_actresses(
                user_id, page, per_page
            )
            
            if actresses is None:
                actresses = []
                total = 0
            
            # 计算分页信息
            total_pages = (total + per_page - 1) // per_page
            return jsonify({
                'success': True,
                'favorites': actresses,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'total_pages': total_pages,
                    'has_prev': page > 1,
                    'has_next': page < total_pages
                }
            })
            
        except Exception as e:
            app_logger.error(f"获取用户收藏演员列表API错误: {e}")
            return jsonify({
                'success': False,
                'error': '获取收藏列表失败，请稍后重试'
            })
    
    # 演员搜索API
    @app.route('/api/actresses/search')
    def search_actresses_api():
        """演员搜索API"""
        try:
            # 获取查询参数
            search_keyword = request.args.get('search', '').strip()
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))
            cup_size_filter = request.args.get('cup_size', None)
            
            # 搜索演员
            actresses, total = db_manager.search_actresses(
                search_keyword=search_keyword if search_keyword else None,
                page=page,
                per_page=per_page,
                cup_size_filter=cup_size_filter
            )
            
            if actresses is None:
                actresses = []
                total = 0
            
            # 计算分页信息
            total_pages = (total + per_page - 1) // per_page
            
            return jsonify({
                'success': True,
                'actresses': actresses,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'total_pages': total_pages,
                    'has_prev': page > 1,
                    'has_next': page < total_pages
                }
            })
            
        except Exception as e:
            app_logger.error(f"演员搜索API错误: {e}")
            return jsonify({
                'success': False,
                'error': '搜索失败，请稍后重试'
            })
    
    # 系列收藏相关API路由
    @app.route('/api/series/favorite', methods=['POST'])
    @api_login_required
    def add_series_favorite():
        """添加系列收藏API"""
        try:
            data = request.get_json()
            series_name = data.get('series_name')
            cover_url = data.get('cover_url')
            print(data)
            print(cover_url)
            if not series_name:
                return jsonify({
                    'success': False,
                    'error': '系列名称不能为空'
                })
            
            # 获取当前用户ID
            user_id = session.get('user_id') 
            if not user_id:
                return jsonify({
                    'success': False,   
                    'error': '用户未登录'
                })
            
            # 检查是否已经收藏
            if db_manager.is_series_favorited(user_id, series_name):
                return jsonify({
                    'success': False,
                    'error': '该系列已在收藏列表中'
                })
            
            # 添加收藏
            result = db_manager.add_series_favorite(user_id, series_name, cover_url)
            
            if result:
                return jsonify({
                    'success': True,
                    'message': '收藏成功'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': '收藏失败'
                })
            
        except Exception as e:
            app_logger.error(f"添加系列收藏API错误: {e}")
            return jsonify({
                'success': False,
                'error': '添加收藏失败，请稍后重试'
            })
    
    @app.route('/api/series/favorite', methods=['DELETE'])
    @api_login_required
    def remove_series_favorite():
        """取消系列收藏API"""
        try:
            data = request.get_json()
            series_name = data.get('series_name')
            
            if not series_name:
                return jsonify({
                    'success': False,
                    'error': '系列名称不能为空'
                })
            
            # 获取当前用户ID
            user_id = session.get('user_id')
            if not user_id:
                return jsonify({
                    'success': False,
                    'error': '用户未登录'
                })
            
            # 取消收藏
            result = db_manager.remove_series_favorite(user_id, series_name)
            
            if result:
                return jsonify({
                    'success': True,
                    'message': '取消收藏成功'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': '取消收藏失败'
                })
            
        except Exception as e:
            app_logger.error(f"取消系列收藏API错误: {e}")
            return jsonify({
                'success': False,
                'error': '取消收藏失败，请稍后重试'
            })
    
    @app.route('/api/series/favorite/check/<series_name>')
    @api_login_required
    def check_series_favorite(series_name):
        """检查系列收藏状态API"""
        try:
            # 获取当前用户ID
            user_id = session.get('user_id')
            if not user_id:
                return jsonify({
                    'success': False,
                    'error': '用户未登录'
                })
            
            # 检查收藏状态
            is_favorited = db_manager.is_series_favorited(user_id, series_name)
            
            return jsonify({
                'success': True,
                'is_favorited': is_favorited
            })
            
        except Exception as e:
            app_logger.error(f"检查系列收藏状态API错误: {e}")
            return jsonify({
                'success': False,
                'error': '检查收藏状态失败'
            })
    
    @app.route('/api/series/favorites')
    @api_login_required
    def get_user_favorite_series():
        """获取用户收藏的系列列表API"""
        try:
            # 获取查询参数
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))
            
            # 获取当前用户ID
            user_id = session.get('user_id')
            if not user_id:
                return jsonify({
                    'success': False,
                    'error': '用户未登录'
                })
            
            # 获取收藏的系列列表
            result = db_manager.get_user_favorite_series(user_id, page, per_page)
            print(result)
            return jsonify({
                'success': True,
                'series': result['series'],
                'pagination': {
                    'page': result['page'],
                    'per_page': result['per_page'],
                    'total': result['total'],
                    'total_pages': result['total_pages'],
                    'has_prev': result['page'] > 1,
                    'has_next': result['page'] < result['total_pages']
                }
            })
            
        except Exception as e:
            app_logger.error(f"获取用户收藏系列列表API错误: {e}")
            return jsonify({
                'success': False,
                'error': '获取收藏列表失败，请稍后重试'
            })
    
    # 厂商收藏相关API路由
    @app.route('/api/studio/favorite', methods=['POST'])
    @api_login_required
    def add_studio_favorite():
        """添加厂商收藏API"""
        try:
            data = request.get_json()
            studio_name = data.get('studio_name')
            cover_image = data.get('cover_image')
            
            if not studio_name:
                return jsonify({
                    'success': False,
                    'error': '厂商名称不能为空'
                })
            
            # 获取当前用户ID
            user_id = session.get('user_id') 
            if not user_id:
                return jsonify({
                    'success': False,   
                    'error': '用户未登录'
                })
            
            # 检查是否已经收藏
            if db_manager.is_studio_favorited(user_id, studio_name):
                return jsonify({
                    'success': False,
                    'error': '该厂商已在收藏列表中'
                })
            
            # 添加收藏
            result = db_manager.add_studio_favorite(user_id, studio_name, cover_image)
            
            if result:
                return jsonify({
                    'success': True,
                    'message': '收藏成功'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': '收藏失败'
                })
            
        except Exception as e:
            app_logger.error(f"添加厂商收藏API错误: {e}")
            return jsonify({
                'success': False,
                'error': '添加收藏失败，请稍后重试'
            })
    
    @app.route('/api/studio/favorite', methods=['DELETE'])
    @api_login_required
    def remove_studio_favorite():
        """取消厂商收藏API"""
        try:
            data = request.get_json()
            studio_name = data.get('studio_name')
            
            if not studio_name:
                return jsonify({
                    'success': False,
                    'error': '厂商名称不能为空'
                })
            
            # 获取当前用户ID
            user_id = session.get('user_id')
            if not user_id:
                return jsonify({
                    'success': False,
                    'error': '用户未登录'
                })
            
            # 取消收藏
            result = db_manager.remove_studio_favorite(user_id, studio_name)
            
            if result:
                return jsonify({
                    'success': True,
                    'message': '取消收藏成功'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': '取消收藏失败'
                })
            
        except Exception as e:
            app_logger.error(f"取消厂商收藏API错误: {e}")
            return jsonify({
                'success': False,
                'error': '取消收藏失败，请稍后重试'
            })
    
    @app.route('/api/studio/favorite/check/<studio_name>')
    @api_login_required
    def check_studio_favorite(studio_name):
        """检查厂商收藏状态API"""
        try:
            # 获取当前用户ID
            user_id = session.get('user_id')
            if not user_id:
                return jsonify({
                    'success': False,
                    'error': '用户未登录'
                })
            
            # 检查收藏状态
            is_favorited = db_manager.is_studio_favorited(user_id, studio_name)
            
            return jsonify({
                'success': True,
                'is_favorited': is_favorited
            })
            
        except Exception as e:
            app_logger.error(f"检查厂商收藏状态API错误: {e}")
            return jsonify({
                'success': False,
                'error': '检查收藏状态失败'
            })
    
    @app.route('/api/studio/favorites')
    @api_login_required
    def get_user_favorite_studios():
        """获取用户收藏的厂商列表API"""
        try:
            # 获取查询参数
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))
            
            # 获取当前用户ID
            user_id = session.get('user_id')
            if not user_id:
                return jsonify({
                    'success': False,
                    'error': '用户未登录'
                })
            
            # 获取收藏的厂商列表
            result = db_manager.get_user_favorite_studios(user_id, page, per_page)
            return jsonify({
                'success': True,
                'studios': result['studios'],
                'pagination': {
                    'page': result['page'],
                    'per_page': result['per_page'],
                    'total': result['total'],
                    'total_pages': result['total_pages'],
                    'has_prev': result['page'] > 1,
                    'has_next': result['page'] < result['total_pages']
                }
            })
            
        except Exception as e:
            app_logger.error(f"获取用户收藏厂商列表API错误: {e}")
            return jsonify({
                'success': False,
                'error': '获取收藏列表失败，请稍后重试'
            })
    
    @app.route('/api/update-jav-home', methods=['POST'])
    @api_login_required
    def update_jav_home():
        """更新JAV首页API"""
        try:
            # 在后台进程中执行爬虫任务
            def run_crawler():
                try:
                    # 在多进程中设置正确的Python路径
                    import sys
                    import os
                    
                    # 添加crawler目录到Python路径
                    crawler_dir = os.path.join(os.path.dirname(__file__), 'crawler')
                    if crawler_dir not in sys.path:
                        sys.path.insert(0, crawler_dir)
                    
                    # 添加javbus目录到Python路径
                    javbus_dir = os.path.join(crawler_dir, 'javbus')
                    if javbus_dir not in sys.path:
                        sys.path.insert(0, javbus_dir)
                    
                    # 导入爬虫模块
                    import crawler.javbus.crawler as javbus_crawler
                    javbus_crawler.process_home_page()  # 这个函数会调用 controller.process_home_page()
                    app_logger.info("JAV首页更新完成")
                except Exception as e:
                    app_logger.error(f"JAV首页更新错误: {e}")
            
            process = multiprocessing.Process(target=run_crawler)
            process.daemon = True
            process.start()
            
            return jsonify({
                'success': True,
                'message': 'JAV首页更新任务已开始执行，请查看控制台日志了解进度'
            })
            
        except Exception as e:
            app_logger.error(f"启动JAV首页更新错误: {e}")
            return jsonify({
                'success': False,
                'error': f'启动失败: {str(e)}'
            })

    # 爬虫配置相关路由
    @app.route('/crawler-config')
    @login_required
    def crawler_config_page():
        """爬虫配置页面"""
        return render_template('crawler_config.html')
    
    @app.route('/api/crawler-config', methods=['GET'])
    @api_login_required
    def get_crawler_config():
        """获取爬虫配置API"""
        try:
            crawler_type = request.args.get('type', 'jav')
            
            if crawler_type not in ['jav', 'sehuatang']:
                return jsonify({
                    'success': False,
                    'error': '无效的爬虫类型'
                })
            
            config = db_manager.get_crawler_config(crawler_type)
            
            return jsonify({
                'success': True,
                'config': config
            })
            
        except Exception as e:
            app_logger.error(f"获取爬虫配置错误: {e}")
            return jsonify({
                'success': False,
                'error': '获取配置失败，请稍后重试'
            })
    
    @app.route('/api/crawler-config', methods=['POST'])
    @api_login_required
    def save_crawler_config():
        """保存爬虫配置API"""
        try:
            data = request.get_json()
            crawler_type = data.get('type')
            
            if crawler_type not in ['jav', 'sehuatang']:
                return jsonify({
                    'success': False,
                    'error': '无效的爬虫类型'
                })
            
            # 验证配置数据
            config_data = {
                'schedule_time': data.get('schedule_time', '23:00'),
                'max_pages': int(data.get('max_pages', 50)),
                'interval_days': int(data.get('interval_days', 7)),
                'is_enabled': bool(data.get('is_enabled', True))
            }
            
            # 验证时间格式
            try:
                datetime.strptime(config_data['schedule_time'], '%H:%M')
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': '时间格式无效，请使用 HH:MM 格式'
                })
            
            # 验证页数和间隔天数
            if config_data['max_pages'] < 1 or config_data['max_pages'] > 1000:
                return jsonify({
                    'success': False,
                    'error': '最大页数必须在1-1000之间'
                })
            
            if config_data['interval_days'] < 1 or config_data['interval_days'] > 365:
                return jsonify({
                    'success': False,
                    'error': '间隔天数必须在1-365之间'
                })
            
            # 保存配置
            result = db_manager.save_crawler_config(crawler_type, config_data)
            
            if result:
                return jsonify({
                    'success': True,
                    'message': f'{crawler_type.upper()}爬虫配置保存成功'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': '保存配置失败'
                })
            
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': '配置数据格式错误'
            })
        except Exception as e:
            app_logger.error(f"保存爬虫配置错误: {e}")
            return jsonify({
                'success': False,
                'error': '保存配置失败，请稍后重试'
            })
    
    @app.route('/api/crawler-config/all', methods=['GET'])
    @api_login_required
    def get_all_crawler_configs():
        """获取所有爬虫配置API"""
        try:
            configs = db_manager.get_all_crawler_configs()
            
            return jsonify({
                'success': True,
                'configs': configs
            })
            
        except Exception as e:
            app_logger.error(f"获取所有爬虫配置错误: {e}")
            return jsonify({
                'success': False,
                'error': '获取配置失败，请稍后重试'
            })
    
    @app.route('/api/crawler-config/toggle', methods=['POST'])
    @api_login_required
    def toggle_crawler_status():
        """切换爬虫启用状态API"""
        try:
            data = request.get_json()
            crawler_type = data.get('type')
            enabled = bool(data.get('enabled', True))
            
            if crawler_type not in ['jav', 'sehuatang']:
                return jsonify({
                    'success': False,
                    'error': '无效的爬虫类型'
                })
            
            result = db_manager.toggle_crawler_status(crawler_type, enabled)
            
            if result:
                status_text = '启用' if enabled else '禁用'
                return jsonify({
                    'success': True,
                    'message': f'{crawler_type.upper()}爬虫已{status_text}'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': '更新状态失败'
                })
            
        except Exception as e:
            app_logger.error(f"切换爬虫状态错误: {e}")
            return jsonify({
                'success': False,
                'error': '更新状态失败，请稍后重试'
            })
    
    @app.route('/api/crawler-config/run', methods=['POST'])
    @api_login_required
    def run_crawler_immediately():
        """立即运行爬虫API"""
        try:
            data = request.get_json()
            crawler_type = data.get('type')
            
            if crawler_type not in ['jav', 'sehuatang']:
                return jsonify({
                    'success': False,
                    'error': '无效的爬虫类型'
                })
            
            # 获取爬虫配置
            config = db_manager.get_crawler_config(crawler_type)
            print(config)
            if not config['is_enabled']:
                return jsonify({
                    'success': False,
                    'error': f'{crawler_type.upper()}爬虫已被禁用，请先启用后再运行'
                })
            
            # 在后台进程中执行爬虫任务
            def run_crawler():
                try:
                    # 在多进程中设置正确的Python路径
              
                    # 添加crawler目录到Python路径
                    crawler_dir = os.path.join(os.path.dirname(__file__), 'crawler')
                    if crawler_dir not in sys.path:
                        sys.path.insert(0, crawler_dir)
                    
                    if crawler_type == 'jav':
                        # 添加javbus目录到Python路径
                        javbus_dir = os.path.join(crawler_dir, 'javbus')
                        if javbus_dir not in sys.path:
                            sys.path.insert(0, javbus_dir)
                        
                        # 导入并运行JAV爬虫
                        import crawler.javbus.crawler as javbus_crawler
                        javbus_crawler.process_home_page(max_pages=config['max_pages'])
                        app_logger.info(f"JAV爬虫运行完成，爬取页数: {config['max_pages']}")
                    
                    elif crawler_type == 'sehuatang':
                        # 导入并运行Sehuatang爬虫
                        from crawler.selenium_crawler import ForumSeleniumCrawler
                        crawler = ForumSeleniumCrawler()
                        crawler.update_sehuatang(pageNumbers=config['max_pages'])
                        app_logger.info(f"Sehuatang爬虫运行完成，爬取页数: {config['max_pages']}")
                    
                    # 更新最后运行时间
                    db_manager.update_crawler_last_run_time(crawler_type)
                    
                except Exception as e:
                    app_logger.error(f"{crawler_type.upper()}爬虫运行错误: {e}")
            
            process = multiprocessing.Process(target=run_crawler)
            process.daemon = True
            process.start()
            
            return jsonify({
                'success': True,
                'message': f'{crawler_type.upper()}爬虫已开始运行，请查看控制台日志了解进度'
            })
            
        except Exception as e:
            app_logger.error(f"启动爬虫错误: {e}")
            return jsonify({
                'success': False,
                'error': f'启动失败: {str(e)}'
            })
    
    @app.route('/api/crawler-config/reset', methods=['POST'])
    @api_login_required
    def reset_crawler_config():
        """重置爬虫配置为默认值API"""
        try:
            data = request.get_json()
            crawler_type = data.get('type')
            
            if crawler_type not in ['jav', 'sehuatang']:
                return jsonify({
                    'success': False,
                    'error': '无效的爬虫类型'
                })
            
            # 删除现有配置，让系统使用默认配置
            db_manager.crawler_config_collection.delete_one({'type': crawler_type})
            
            # 获取默认配置
            default_config = db_manager.get_crawler_config(crawler_type)
            
            return jsonify({
                'success': True,
                'message': f'{crawler_type.upper()}爬虫配置已重置为默认值',
                'config': default_config
            })
            
        except Exception as e:
            app_logger.error(f"重置爬虫配置错误: {e}")
            return jsonify({
                'success': False,
                'error': '重置配置失败，请稍后重试'
            })

    @app.route('/api/audio/list-videos', methods=['POST'])
    def list_videos_in_path():
        """获取指定路径下的视频文件列表"""
        try:
            data = request.get_json()
            if not data or 'path' not in data:
                return jsonify({'error': '请提供路径参数'}), 400
            
            target_path = data['path']
            
            # 验证路径是否存在
            if not os.path.exists(target_path):
                return jsonify({'error': '指定路径不存在'}), 404
            
            if not os.path.isdir(target_path):
                return jsonify({'error': '指定路径不是目录'}), 400
            
            # 支持的视频文件扩展名
            video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.m4v', '.3gp', '.webm'}
            
            video_files = []
            try:
                for filename in os.listdir(target_path):
                    file_path = os.path.join(target_path, filename)
                    
                    # 检查是否为文件且为视频格式
                    if os.path.isfile(file_path):
                        file_ext = os.path.splitext(filename)[1].lower()
                        if file_ext in video_extensions:
                            try:
                                file_size = os.path.getsize(file_path)
                                video_files.append({
                                    'name': filename,
                                    'path': file_path,
                                    'size': file_size,
                                    'extension': file_ext
                                })
                            except OSError:
                                # 跳过无法访问的文件
                                continue
                
                # 按文件名排序
                video_files.sort(key=lambda x: x['name'])
                
                return jsonify({
                    'success': True,
                    'files': video_files,
                    'count': len(video_files),
                    'path': target_path
                })
                
            except PermissionError:
                return jsonify({'error': '没有权限访问指定路径'}), 403
            except Exception as e:
                app_logger.error(f"读取目录失败: {e}")
                return jsonify({'error': '读取目录失败'}), 500
            
        except Exception as e:
            app_logger.error(f"获取视频文件列表失败: {e}")
            return jsonify({'error': '获取文件列表失败'}), 500

    @app.route('/api/audio/process', methods=['POST'])
    def process_video_from_path():
        """处理指定路径的视频文件"""
        try:
            data = request.get_json()
            if not data or 'video_path' not in data:
                return jsonify({'error': '请提供视频文件路径'}), 400
            
            video_path = data['video_path']
            
            # 验证文件是否存在
            if not os.path.exists(video_path):
                return jsonify({'error': '视频文件不存在'}), 404
            
            if not os.path.isfile(video_path):
                return jsonify({'error': '指定路径不是文件'}), 400
            
            # 检查文件类型
            allowed_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.m4v', '.3gp', '.webm'}
            file_ext = os.path.splitext(video_path)[1].lower()
            if file_ext not in allowed_extensions:
                return jsonify({'error': '不支持的视频文件格式'}), 400
            
            # 检查文件是否可读
            try:
                with open(video_path, 'rb') as f:
                    f.read(1)
            except PermissionError:
                return jsonify({'error': '没有权限访问该文件'}), 403
            except Exception as e:
                return jsonify({'error': '文件无法读取'}), 400
            
            # 创建音频处理任务
            task_id = db_manager.create_audio_task(video_path)
            if not task_id:
                return jsonify({'error': '创建处理任务失败'}), 500
            
            # 异步处理（这里简化为同步，实际应该使用Celery等任务队列）
            from audio_processor import AudioProcessor
            processor = AudioProcessor()
            
            # 在后台线程中处理
            import threading
            def process_in_background():
                try:
                    processor.process_video_to_subtitles(video_path, task_id)
                except Exception as e:
                    app_logger.error(f"视频处理失败: {e}")
                    # 更新任务状态为失败
                    db_manager.update_audio_task_status(task_id, 'failed', error_message=str(e))
            
            thread = threading.Thread(target=process_in_background)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'success': True,
                'message': '视频处理任务已开始',
                'task_id': task_id,
                'video_path': video_path
            })
            
        except Exception as e:
            app_logger.error(f"处理视频文件失败: {e}")
            return jsonify({'error': '处理失败'}), 500

    @app.route('/api/audio/upload', methods=['POST'])
    def upload_video_for_processing():
        """上传视频文件进行音频处理（保留原有接口以兼容）"""
        try:
            if 'video_file' not in request.files:
                return jsonify({'error': '没有上传文件'}), 400
            
            file = request.files['video_file']
            if file.filename == '':
                return jsonify({'error': '没有选择文件'}), 400
            
            # 检查文件类型
            allowed_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv'}
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in allowed_extensions:
                return jsonify({'error': '不支持的文件格式'}), 400
            
            # 保存上传的文件
            upload_dir = os.path.join(os.path.dirname(__file__), 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)
            
            # 创建音频处理任务
            task_id = db_manager.create_audio_task(file_path)
            if not task_id:
                return jsonify({'error': '创建处理任务失败'}), 500
            
            # 异步处理（这里简化为同步，实际应该使用Celery等任务队列）
            from audio_processor import AudioProcessor
            processor = AudioProcessor()
            
            # 在后台线程中处理
            import threading
            def process_in_background():
                processor.process_video_to_subtitles(file_path, task_id)
            
            thread = threading.Thread(target=process_in_background)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'message': '文件上传成功，开始处理',
                'task_id': task_id
            })
            
        except Exception as e:
            app_logger.error(f"上传视频文件失败: {e}")
            return jsonify({'error': '上传失败'}), 500

    @app.route('/api/audio/task/<task_id>', methods=['GET'])
    def get_audio_task_status(task_id):
        """获取音频处理任务状态"""
        try:
            task = db_manager.get_audio_task(task_id)
            if not task:
                return jsonify({'error': '任务不存在'}), 404
            
            return jsonify(task)
            
        except Exception as e:
            app_logger.error(f"获取任务状态失败: {e}")
            return jsonify({'error': '获取任务状态失败'}), 500

    @app.route('/api/audio/tasks', methods=['GET'])
    def get_audio_tasks():
        """获取音频处理任务列表"""
        try:
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))
            status = request.args.get('status')
            
            result = db_manager.get_audio_tasks(status, page, per_page)
            return jsonify(result)
            
        except Exception as e:
            app_logger.error(f"获取任务列表失败: {e}")
            return jsonify({'error': '获取任务列表失败'}), 500

    @app.route('/api/audio/download/<task_id>/<subtitle_type>', methods=['GET'])
    def download_subtitle_file(task_id, subtitle_type):
        """下载字幕文件"""
        try:
            subtitle = db_manager.get_subtitle_by_task_id(task_id)
            if not subtitle:
                return jsonify({'error': '字幕文件不存在'}), 404
            
            if subtitle_type == 'japanese':
                file_path = subtitle['japanese_srt_path']
                filename = f"japanese_subtitle_{task_id}.srt"
            elif subtitle_type == 'chinese':
                file_path = subtitle['chinese_srt_path']
                filename = f"chinese_subtitle_{task_id}.srt"
            else:
                return jsonify({'error': '无效的字幕类型'}), 400
            
            if not os.path.exists(file_path):
                return jsonify({'error': '字幕文件不存在'}), 404
            
            return send_file(file_path, as_attachment=True, download_name=filename)
            
        except Exception as e:
            app_logger.error(f"下载字幕文件失败: {e}")
            return jsonify({'error': '下载失败'}), 500

    @app.route('/audio_processor')
    def audio_processor_page():
        """音频处理页面"""
        return render_template('audio_processor.html')
    
    @app.route('/api/video/search-115', methods=['POST'])
    @api_login_required
    def search_115_video():
        """搜索115平台上的视频文件"""
        try:
            from yun115_client import Yun115Client
            from config import config as app_config
            
            data = request.get_json()
            movie_code = data.get('movie_code', '').strip()
            
            if not movie_code:
                return jsonify({
                    'success': False,
                    'error': '请提供电影编号'
                })
            
            # 初始化115客户端
            yun115_config = app_config.get_yun115_config()
            if not yun115_config.get('access_token'):
                return jsonify({
                    'success': False,
                    'error': '115开发平台未配置或未授权'
                })
            
            client = Yun115Client(yun115_config)
            
            # 搜索视频文件
            files = client.search_movie_files(movie_code)
            
            if not files:
                return jsonify({
                    'success': False,
                    'error': f'未找到电影 {movie_code} 的视频文件'
                })
            
            # 选择最佳质量的文件
            best_file = client.get_best_quality_file(files)
            
            if best_file:
                # 保存文件信息到数据库
                db_manager.save_115_file_info(movie_code, best_file)
                
                return jsonify({
                    'success': True,
                    'data': {
                        'file_info': best_file,
                        'total_files': len(files)
                    }
                })
            else:
                return jsonify({
                    'success': False,
                    'error': '无法获取文件信息'
                })
                
        except Exception as e:
            app_logger.error(f"搜索115视频失败: {e}")
            return jsonify({
                'success': False,
                'error': f'搜索失败: {str(e)}'
            })
    
    @app.route('/api/video/play-url/<movie_code>')
    @api_login_required
    def get_play_url(movie_code):
        """获取视频播放地址"""
        try:
            from yun115_client import Yun115Client
            from config import config as app_config
            
            # 先从数据库获取文件信息
            file_info_list = db_manager.get_115_file_info(movie_code)
            
            if not file_info_list:
                # 如果数据库中没有，尝试搜索
                yun115_config = app_config.get_yun115_config()
                if not yun115_config.get('access_token'):
                    return jsonify({
                        'success': False,
                        'error': '115开发平台未配置或未授权'
                    })
                
                client = Yun115Client(yun115_config)
                files = client.search_movie_files(movie_code)
                
                if files:
                    best_file = client.get_best_quality_file(files)
                    if best_file:
                        db_manager.save_115_file_info(movie_code, best_file)
                        file_info_list = [best_file]
            
            if not file_info_list:
                return jsonify({
                    'success': False,
                    'error': f'未找到电影 {movie_code} 的视频文件'
                })
            
            # 使用第一个文件（通常是最佳质量的）
            file_info = file_info_list[0]
            file_id = file_info.get('file_id')
            
            if not file_id:
                return jsonify({
                    'success': False,
                    'error': '文件ID无效'
                })
            
            # 获取播放地址
            yun115_config = app_config.get_yun115_config()
            client = Yun115Client(yun115_config)
            play_url = client.get_play_url(file_id)
            
            if play_url:
                # 更新数据库中的播放地址
                db_manager.update_115_play_url(movie_code, file_id, play_url)
                
                return jsonify({
                    'success': True,
                    'data': {
                        'play_url': play_url,
                        'file_info': file_info
                    }
                })
            else:
                return jsonify({
                    'success': False,
                    'error': '无法获取播放地址'
                })
                
        except Exception as e:
            app_logger.error(f"获取播放地址失败: {e}")
            return jsonify({
                'success': False,
                'error': f'获取播放地址失败: {str(e)}'
            })
    
    @app.route('/api/video/115-files/<movie_code>')
    @api_login_required
    def get_115_files(movie_code):
        """获取电影的115文件列表"""
        try:
            files = db_manager.get_115_file_info(movie_code)
            
            return jsonify({
                'success': True,
                'data': {
                    'files': files,
                    'total': len(files)
                }
            })
            
        except Exception as e:
            app_logger.error(f"获取115文件列表失败: {e}")
            return jsonify({
                'success': False,
                'error': f'获取文件列表失败: {str(e)}'
            })
    
    @app.route('/api/video/refresh-115-token', methods=['POST'])
    @api_login_required
    def refresh_115_token():
        """刷新115访问令牌"""
        try:
            from yun115_client import Yun115Client
            from config import config as app_config
            
            yun115_config = app_config.get_yun115_config()
            client = Yun115Client(yun115_config)
            
            if client.refresh_access_token():
                return jsonify({
                    'success': True,
                    'message': '令牌刷新成功'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': '令牌刷新失败'
                })
                
        except Exception as e:
            app_logger.error(f"刷新115令牌失败: {e}")
            return jsonify({
                'success': False,
                'error': f'刷新令牌失败: {str(e)}'
            })
    
    # 自定义静态文件处理，添加缓存头
    @app.route('/static/<path:filename>')
    def static_files(filename):
        """自定义静态文件处理，添加缓存控制头"""
        response = make_response(send_from_directory(app.static_folder, filename))
        
        # 根据文件类型设置不同的缓存策略
        if filename.endswith(('.css', '.js')):
            # CSS和JS文件缓存1年
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
            response.headers['Expires'] = (datetime.now() + timedelta(days=365)).strftime('%a, %d %b %Y %H:%M:%S GMT')
        elif filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.webp')):
            # 图片文件缓存30天
            response.headers['Cache-Control'] = 'public, max-age=2592000'
            response.headers['Expires'] = (datetime.now() + timedelta(days=30)).strftime('%a, %d %b %Y %H:%M:%S GMT')
        elif filename.endswith(('.woff', '.woff2', '.ttf', '.eot')):
            # 字体文件缓存1年
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
            response.headers['Expires'] = (datetime.now() + timedelta(days=365)).strftime('%a, %d %b %Y %H:%M:%S GMT')
        else:
            # 其他文件缓存1天
            response.headers['Cache-Control'] = 'public, max-age=86400'
            response.headers['Expires'] = (datetime.now() + timedelta(days=1)).strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        # 添加ETag支持
        response.headers['ETag'] = f'"{hash(filename + str(os.path.getmtime(os.path.join(app.static_folder, filename))))}"'
        print(f"ETag: {response.headers['ETag']}")
        return response

    @app.route('/player')
    @login_required
    def player():
        """视频播放页面"""
        # 获取URL参数
        url = request.args.get('url', '')
        title = request.args.get('title', '未知视频')
        poster = request.args.get('poster', '')
        
        if not url:
            return '缺少视频源URL', 400
            
        return render_template('player.html', 
                             url=url,
                             title=title,
                             poster=poster)
                             
    @app.route('/api/sync-jellfin', methods=['POST'])
    @api_login_required
    def sync_jellfin():
        """同步Jellfin数据API"""
        try:
            # 在后台线程中执行同步操作
            def run_sync():
                try:
                    app_logger.info("开始同步Jellyfin数据")
                    
                    import sqlite3
                    import re
                    
                    # 连接Jellyfin SQLite数据库
                    jellyfin_db_path = '/server/backup_sehuatang/JellfinData/library.db'
                    conn = sqlite3.connect(jellyfin_db_path)
                    cursor = conn.cursor()
                    
                    # 查询所有电影记录
                    cursor.execute("SELECT * FROM TypedBaseItems WHERE type = 'MediaBrowser.Controller.Entities.Movies.Movie' AND TopParentId = '5824037d54700c4dcff7f1255022573b'")
                    movies = cursor.fetchall()
                    
                    # 获取列名
                    column_names = [description[0] for description in cursor.description]
                    name_index = column_names.index('Name')
                    presentation_key_index = column_names.index('PresentationUniqueKey')
                    
                    total_movies = len(movies)
                    updated_count = 0
                    
                    app_logger.info(f"从Jellyfin数据库中找到 {total_movies} 部电影")
                    
                    # 遍历所有电影记录
                    for movie in movies:
                        try:
                            movie_name = movie[name_index]
                            presentation_key = movie[presentation_key_index]
                            
                            # 从PresentationUniqueKey中提取电影编码
                            # 例如："BF-519-完全主観 ボクのお义姉さんは波多野结衣" -> "BF-519"
                            # 修改为截取第二个"-"前面的字符串
                            parts = movie_name.split('-')
                            if len(parts) >= 2:
                                movie_code = parts[0] + '-' + parts[1]
                                
                                # 更新MongoDB中的记录
                                result = db_manager.javbus_data_collection.update_one(
                                    {'code': movie_code},
                                    {'$set': {'presentation_key': presentation_key}}
                                )
                                
                                if result.modified_count > 0:
                                    updated_count += 1
                                    app_logger.info(f"已更新电影 {movie_code}: {movie_name}")
                                elif result.matched_count > 0:
                                    app_logger.info(f"电影 {movie_code} 已存在，无需更新")
                                else:
                                    app_logger.info(f"未找到电影 {movie_code} 的记录")
                            else:
                                app_logger.warning(f"无法从 '{presentation_key}' 中提取电影编码")
                        except Exception as e:
                            app_logger.error(f"处理电影记录时出错: {e}")
                    
                    # 关闭数据库连接
                    conn.close()
                    
                    app_logger.info(f"Jellyfin同步完成，共更新 {updated_count}/{total_movies} 部电影")
                    
                except Exception as e:
                    app_logger.error(f"Jellyfin同步过程中出错: {e}")
            
            # 启动后台线程
            import threading
            thread = threading.Thread(target=run_sync)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'success': True,
                'message': 'Jellyfin同步任务已开始执行，请查看控制台日志了解进度'
            })
            
        except Exception as e:
            app_logger.error(f"启动Jellyfin同步错误: {e}")
            return jsonify({
                'success': False,
                'error': f'启动失败: {str(e)}'
            })