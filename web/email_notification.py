#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件通知模块
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
import sys
import os

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import config as app_config

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