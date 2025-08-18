#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask Web应用 - Jellyfin电影查询 (重构版)
"""

from flask import Flask, session, redirect, url_for, jsonify
from flask_cors import CORS
import sys
import os
from datetime import timedelta
from functools import wraps

# 添加父目录到路径，以便导入项目模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入模块
from database import db_manager
from routes import register_routes
from subscription import start_scheduler
from jellyfin_movie_checker import JellyfinMovieChecker
from crawler.javbus_crawler import JavBusCrawler
  
# 创建Flask应用
app = Flask(__name__, 
           static_folder=os.path.join("/server/", 'static'),  # 自定义文件夹名
           static_url_path='/static')  # 自定义URL路径
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# 配置CORS - 允许所有来源访问
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'session_id' not in session:
            return redirect(url_for('login_page'))
        
        user_info = db_manager.get_user_session(session['session_id'])
        if not user_info:
            session.clear()
            return redirect(url_for('login_page'))
        
        return f(*args, **kwargs)
    return decorated_function

def api_login_required(f):
    """API登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'session_id' not in session:
            return jsonify({
                'success': False,
                'error': '请先登录',
                'redirect': '/login'
            }), 401
        
        user_info = db_manager.get_user_session(session['session_id'])
        if not user_info:
            session.clear()
            return jsonify({
                'success': False,
                'error': '会话已过期，请重新登录',
                'redirect': '/login'
            }), 401
        
        # 设置用户ID到session中，供API使用
        session['user_id'] = user_info.get('user_id') or str(user_info.get('_id'))
        
        return f(*args, **kwargs)
    return decorated_function

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


# 保留这个调用，它会处理所有初始化
jellyfin_checker, crawler = init_components()

# 注册路由
register_routes(app, jellyfin_checker, crawler)

# 启动定时任务调度器
start_scheduler(jellyfin_checker, crawler)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=6000)


