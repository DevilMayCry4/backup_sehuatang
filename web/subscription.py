#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订阅管理模块
"""

import os
import threading
import time
import schedule
from datetime import datetime, timedelta
from database import db_manager
from email_notification import send_batch_email_notification

def check_subscribed_series(jellyfin_checker, crawler,sehuatang_crawler):

    sehuatang_crawler.update_sehuatang()

    """检查订阅的电影系列"""
    if any(component is None for component in [db_manager.add_movie_collection, db_manager.mongo_collection, jellyfin_checker, crawler, db_manager.found_movies_collection]):
        print("必要组件未初始化，跳过检查")
        return
    
    print("开始执行定时推送任务")
    
    # 从环境变量获取检查间隔天数，默认为7天
    check_interval_days = int(os.getenv('SUBSCRIPTION_CHECK_INTERVAL_DAYS', '7'))
    current_time = datetime.now()
    
    
    
    try:
        # 获取所有订阅
        # 收集本次检查发现的所有新电影
        newly_found_movies = []
        subscriptions = db_manager.get_subscriptions()
        
        for subscription in subscriptions:
            series_name = subscription.get('series_name')
            subscription_id = subscription.get('_id')
            last_checked = subscription.get('last_checked')
            status = subscription.get('status')
            
            if not series_name or status != 'active':
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
                db_manager.update_subscription(subscription_id, {
                    'last_checked': current_time.isoformat(),
                    'last_check_status': 'success'
                })
                
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
                        
                        # 查找磁力链接
                        magnet_link = db_manager.find_magnet_link(movie_code)
                        
                        if magnet_link:
                            # 检查是否已经登记过到found_movies表
                            if not db_manager.check_movie_exists_in_found(movie_code):
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
                                    'image_url': movie.get('image_url', '')
                                }
                                
                                db_manager.save_found_movie(movie_doc)
                                
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
                db_manager.update_subscription(subscription_id, {
                    'title': series_title,
                    'last_checked': datetime.now(),
                    'total_movies_found': len(movies),
                    'totoal_found_magnet_movies': found_movies_count
                })
                
            except Exception as e:
                print(f"检查系列 {series_name} 时出错: {e}")
        
        # 如果有新发现的电影，发送批量邮件通知
        if newly_found_movies:
            send_batch_email_notification(newly_found_movies)
        
        print("定时推送任务执行完成")
        
    except Exception as e:
        print(f"执行定时推送任务时出错: {e}")

def start_scheduler(jellyfin_checker, crawler,sehuatang_crawler):
    """启动定时任务调度器"""
    # 每天晚上10点执行
    schedule.every().day.at("23:00").do(lambda: check_subscribed_series(jellyfin_checker, crawler,sehuatang_crawler))
    
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    
    # 在后台线程中运行调度器
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print("定时任务调度器已启动")

def trigger_subscription_check_async(jellyfin_checker, crawler):
    """异步触发订阅检查"""
    def run_check():
        try:
            check_subscribed_series(jellyfin_checker, crawler)
        except Exception as e:
            print(f"手动触发订阅检查时出错: {e}")
    
    # 启动后台线程
    thread = threading.Thread(target=run_check)
    thread.daemon = True
    thread.start()