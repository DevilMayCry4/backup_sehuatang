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

def check_subscribed_series(jellyfin_checker, jav_crawler):
    """检查订阅的电影系列"""
    if any(component is None for component in [db_manager.add_movie_collection, db_manager.mongo_collection, jellyfin_checker, jav_crawler, db_manager.found_movies_collection]):
        print("必要组件未初始化，跳过检查")
        return
    
    print("开始执行定时推送任务")
    
    # 从环境变量获取检查间隔天数，默认为7天
    check_interval_days = int(os.getenv('SUBSCRIPTION_CHECK_INTERVAL_DAYS', '7'))
    current_time = datetime.now()
    
    # 移除了直接调用sehuatang_crawler.update_sehuatang()的代码
    # 因为现在爬虫会根据各自的定时任务单独运行
    
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
                movies, series_title =jav_crawler.search_series_movies(series_name)
                
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

def start_scheduler(jellyfin_checker, jav_crawler, sehuatang_crawler):
    """启动定时任务调度器，根据数据库配置时间分别启动爬虫"""
    # 获取爬虫配置
    jav_config = db_manager.get_crawler_config('jav')
    sehuatang_config = db_manager.get_crawler_config('sehuatang')
    
    # 获取配置的时间，如果没有配置则使用默认值
    jav_schedule_time = jav_config.get('schedule_time', '23:00')
    sehuatang_schedule_time = sehuatang_config.get('schedule_time', '23:30')
    
    # 创建单独的函数用于JAV爬虫
    def run_jav_crawler():
        if jav_config.get('is_enabled', True):
            print(f"根据配置启动JAV爬虫，最大页数：{jav_config.get('max_pages', 50)}")
            jav_crawler.update_javbus(max_pages=jav_config.get('max_pages', 50))
            # 更新爬虫最后运行时间
            db_manager.update_crawler_last_run_time('jav')
        else:
            print("JAV爬虫已禁用，跳过爬取")
    
    # 创建单独的函数用于色花堂爬虫
    def run_sehuatang_crawler():
        if sehuatang_config.get('is_enabled', True):
            print(f"根据配置启动色花堂爬虫，最大页数：{sehuatang_config.get('max_pages', 100)}")
            sehuatang_crawler.update_sehuatang(max_pages=sehuatang_config.get('max_pages', 100))
            # 更新爬虫最后运行时间
            db_manager.update_crawler_last_run_time('sehuatang')
        else:
            print("色花堂爬虫已禁用，跳过爬取")
    
    # 创建函数用于订阅检查
    def run_subscription_check():
        check_subscribed_series(jellyfin_checker, jav_crawler)
    
    # 根据配置的时间分别设置定时任务
    schedule.every().day.at(jav_schedule_time).do(run_jav_crawler)
    schedule.every().day.at(sehuatang_schedule_time).do(run_sehuatang_crawler)
    # 每天晚上10点执行订阅检查
    schedule.every().day.at("22:00").do(run_subscription_check)
    
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    
    # 在后台线程中运行调度器
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print(f"定时任务调度器已启动：JAV爬虫({jav_schedule_time})，色花堂爬虫({sehuatang_schedule_time})，订阅检查(22:00)")

def trigger_subscription_check_async(jellyfin_checker,jav_crawler):
    """异步触发订阅检查"""
    def run_check():
        try:
            check_subscribed_series(jellyfin_checker,jav_crawler)
        except Exception as e:
            print(f"手动触发订阅检查时出错: {e}")
    
    # 启动后台线程
    thread = threading.Thread(target=run_check)
    thread.daemon = True
    thread.start()