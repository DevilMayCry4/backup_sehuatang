#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片代理模块
"""

import requests
from urllib.parse import urlparse
from flask import Response, jsonify

def proxy_image(image_url):
    """图片代理函数 - 解决跨域图片显示问题"""
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