#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask Web应用 - Jellyfin电影查询
"""

from flask import Flask, render_template, request, jsonify
import sys
import os

# 添加父目录到路径，以便导入项目模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jellyfin_movie_checker import JellyfinMovieChecker
from jellyfin_config import config

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# 初始化Jellyfin检查器
try:
    jellyfin_checker = JellyfinMovieChecker()
except Exception as e:
    print(f"Jellyfin初始化失败: {e}")
    jellyfin_checker = None

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
        
        # 执行搜索
        result = jellyfin_checker.check_movie_exists(movie_name)
        
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
                'jellyfin_available': jellyfin_checker is not None
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)