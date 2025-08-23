#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库模块 - MongoDB连接和操作
"""

from pymongo import MongoClient
from datetime import datetime, timedelta
from bson import ObjectId
import sys
import os
import atexit
import ast
import app_logger

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import config as app_config

class DatabaseManager:
    def __init__(self):
        self.mongo_client = None
        self.mongo_db = None
        self.mongo_collection = None
        self.add_movie_collection = None
        self.found_movies_collection = None
        # JavBus 爬虫相关集合
        self.javbus_data_collection = None
        self.actresses_data_collection = None
        self.processed_actresses_collection = None
        # 用户认证相关集合
        self.users_collection = None
        self.sessions_collection = None
        # 类别数据集合
        self.genres_collection = None
        # 演员收藏集合
        self.actress_favorites_collection = None
        # 系列收藏集合
        self.series_favorites_collection = None
        # 厂商收藏集合
        self.studio_favorites_collection = None
        
    def init_mongodb(self):
        """初始化MongoDB连接"""
        try:
            mongo_config = app_config.get_mongo_config()
            self.mongo_client = MongoClient(mongo_config['uri'], serverSelectionTimeoutMS=5000)
            # 测试连接
            self.mongo_client.admin.command('ping')
            # 连接到sehuatang_backup数据库
            self.mongo_db = self.mongo_client['sehuatang_crawler']
            self.mongo_collection = self.mongo_db['thread_details']
            self.add_movie_collection = self.mongo_db['add_movie']
            self.found_movies_collection = self.mongo_db['found_movies']
            self.retry_collection = self.mongo_db['retry_urls']
            self.processed_actresses_collection = self.mongo_db['processed_actresses']
            
            # JavBus 爬虫相关集合
            self.javbus_data_collection = self.mongo_db['javbus_data']
            self.actresses_data_collection = self.mongo_db['actresses_data']
            
            # 用户认证相关集合
            self.users_collection = self.mongo_db['users']
            self.sessions_collection = self.mongo_db['sessions']
            
            # 类别数据集合
            self.genres_collection = self.mongo_db['genres_data']
            
            # 演员收藏集合
            self.actress_favorites_collection = self.mongo_db['actress_favorites']
            
            # 系列收藏集合
            self.series_favorites_collection = self.mongo_db['series_favorites']
            
            # 厂商收藏集合
            self.studio_favorites_collection = self.mongo_db['studio_favorites']
            
            # 创建默认管理员用户（如果不存在）
            self._create_default_admin()
            
            app_logger.info("MongoDB连接成功")
            return True
        except Exception as e:
            app_logger.error(f"MongoDB连接失败: {e}")
            return False

    def get_subscriptions(self):
        """获取所有订阅"""
        if self.add_movie_collection is None:
            return []
        return list(self.add_movie_collection.find({'type': 'subscription'}))
    
    def create_subscription(self, series_name):
        """创建订阅"""
        if self.add_movie_collection is None:
            raise Exception('MongoDB未初始化')
            
        # 检查是否已经订阅
        existing = self.add_movie_collection.find_one({
            'series_name': series_name,
            'type': 'subscription'
        })
        
        if existing:
            raise Exception(f'已经订阅了系列 "{series_name}"')
        
        # 添加订阅记录
        subscription_doc = {
            'series_name': series_name,
            'type': 'subscription',
            'status': 'active',
            'created_at': datetime.now(),
            'last_checked': None,
            'total_movies_found': 0
        }
        
        result = self.add_movie_collection.insert_one(subscription_doc)
        return str(result.inserted_id)
    
    def delete_subscription(self, subscription_id):
        """删除订阅"""
        if self.add_movie_collection is None:
            raise Exception('MongoDB未初始化')
            
        result = self.add_movie_collection.delete_one({
            '_id': ObjectId(subscription_id),
            'type': 'subscription'
        })
        
        return result.deleted_count > 0
    
    def update_subscription(self, subscription_id, update_data):
        """更新订阅信息"""
        if self.add_movie_collection is None:
            raise Exception('MongoDB未初始化')
            
        self.add_movie_collection.update_one(
            {'_id': subscription_id},
            {'$set': update_data}
        )
    
    def save_found_movie(self, movie_doc):
        """保存发现的电影"""
        if self.found_movies_collection is None:
            raise Exception('MongoDB未初始化')
            
        return self.found_movies_collection.insert_one(movie_doc)
    
    def get_subscription_movies(self, series_name):
        """获取指定订阅的电影列表"""
        if self.found_movies_collection is None:
            raise Exception('MongoDB未初始化')
            
        return list(self.found_movies_collection.find({
            'series_name': series_name
        }).sort('found_at', -1))
    
    def find_magnet_link(self, movie_code):
        """查找磁力链接"""
        if self.mongo_collection is None:
            return None
            
        magnet_doc = self.mongo_collection.find_one({
            '$or': [
                {'title': {'$regex': movie_code, '$options': 'i'}},
                {'movie_code': movie_code}
            ],
            'magnet_link': {'$exists': True, '$ne': ''}
        })
        
        return magnet_doc.get('magnet_link', '') if magnet_doc else None
    
    def update_subscription_status(self, subscription_id, new_status):
        """更新订阅状态"""
        if self.add_movie_collection is None:
            raise Exception('MongoDB未初始化')
            
        try:
            result = self.add_movie_collection.update_one(
                {'_id': ObjectId(subscription_id), 'type': 'subscription'},
                {'$set': {'status': new_status}}
            )
            return result.matched_count > 0
        except Exception as e:
            app_logger.info(f"更新订阅状态错误: {e}")
            return False
    
    def check_movie_exists_in_found(self, movie_code):
        """检查电影是否已在found_movies中存在"""
        if self.found_movies_collection is None:
            return False
            
        return self.found_movies_collection.find_one({'movie_code': movie_code}) is not None
    
    # ==================== JavBus 爬虫相关方法 ====================
    
    def write_jav_movie(self, dict_jav):
        """写入JAV电影数据到 MongoDB"""
        try:
            if self.javbus_data_collection is None:
                raise Exception('MongoDB未初始化')
            # 准备文档数据
            document = {
                'url': dict_jav.get('URL', ''),
                'code': dict_jav.get('識別碼', ''),
                'title': dict_jav.get('標題', ''),
                'cover': dict_jav.get('封面', ''), 
                'release_date': dict_jav.get('發行日期', ''),
                'duration': dict_jav.get('長度', ''),
                'director': dict_jav.get('導演', ''),
                'studio': dict_jav.get('製作商', ''),
                'publisher': dict_jav.get('發行商', ''),
                'series': dict_jav.get('系列', ''),
                'actresses': dict_jav.get('演員', ''),
                'genres': dict_jav.get('類別', ''),
                'magnet_links': dict_jav.get('磁力链接', ''),
                'uncensored': dict_jav.get('無碼', 0),
                'is_single': dict_jav.get('is_single', False),
                'is_subtitle': dict_jav.get('is_subtitle', False),
            }
            
            # 使用 upsert 操作，如果 URL 已存在则更新，否则插入
            result = self.javbus_data_collection.update_one(
                {'url': document['url']},
                {'$set': document},
                upsert=True
            )
            
            if result.upserted_id:
                app_logger.info(f"Inserted new document with URL: {document['url']}")
            elif result.modified_count > 0:
                app_logger.info(f"Updated existing document with URL: {document['url']}")
                
            return True
            
        except Exception as e:
            app_logger.info(f"Error writing data to MongoDB: {e}")
            return False
    
    def refresh_data(self, dict_jav, url):
        """更新指定 URL 的磁力链接数据"""
        try:
            if self.javbus_data_collection is None:
                raise Exception('MongoDB未初始化')
            
            # 更新磁力链接
            result = self.javbus_data_collection.update_one(
                {'URL': {'$regex': f'^{url}$', '$options': 'i'}},  # 不区分大小写匹配
                {'$set': {'磁力链接': dict_jav.get('磁力链接', '')}}
            )
            
            if result.modified_count > 0:
                app_logger.info(f"Updated magnet links for URL: {url}")
                return True
            else:
                app_logger.info(f"No document found with URL: {url}")
                return False
                
        except Exception as e:
            app_logger.info(f"Error refreshing data in MongoDB: {e}")
            return False
    
    def check_url_not_in_table(self, url):
        """检查 URL 是否不在数据库中，如果不存在返回 True，存在返回 False"""
        try:
            if self.javbus_data_collection is None:
                return True
            
            # 不区分大小写查询
            result = self.javbus_data_collection.find_one(
                {'URL': {'$regex': f'^{url}$', '$options': 'i'}},
                {'_id': 1}  # 只返回 _id 字段以提高性能
            )
            
            return result is None
            
        except Exception as e:
            app_logger.info(f"Error checking URL in MongoDB: {e}")
            return True  # 出错时假设不存在
    
    def is_movie_crawed(self, code):
        """检查电影是否已被爬取"""
        try:
            if self.javbus_data_collection is None:
                return False
            
            # 不区分大小写查询
            result = self.javbus_data_collection.find_one(
                {'code': {'$regex': f'^{code}$', '$options': 'i'}}
            ) 
            return result is not None
                
        except Exception as e:
            app_logger.info(f"Error checking movie crawled status: {e}")
            return False
    
    def read_magnets_from_table(self, url):
        """从数据库中读取指定 URL 的磁力链接"""
        try:
            if self.javbus_data_collection is None:
                return None
            
            # 不区分大小写查询
            result = self.javbus_data_collection.find_one(
                {'URL': {'$regex': f'^{url}$', '$options': 'i'}},
                {'磁力链接': 1, '_id': 0}  # 只返回磁力链接字段
            )
            
            if result and result.get('磁力链接'):
                return [(result['磁力链接'],)]  # 返回与原 SQLite 版本兼容的格式
            else:
                return None
                
        except Exception as e:
            app_logger.info(f"Error reading magnets from MongoDB: {e}")
            return None
    
    def write_actress_data(self, actress_info, local_image_path=None):
        """写入演员数据到 MongoDB"""
        try:
            if self.actresses_data_collection is None:
                raise Exception('MongoDB未初始化')
            
            # 准备文档数据
            document = {
                'name': actress_info.get('name', ''),
                'code': actress_info.get('code', ''),
                'detail_url': actress_info.get('detail_url', ''),
                'image_url': actress_info.get('image_url', ''),
                'local_image_path': local_image_path or actress_info.get('local_image_path', ''),
                'height': actress_info.get('height', ''),
                'cup_size': actress_info.get('cup_size', ''),
                'bust': actress_info.get('bust', ''),
                'waist': actress_info.get('waist', ''),
                'hip': actress_info.get('hip', ''),
                'hobby': actress_info.get('hobby', '')
            }
            
            # 使用 upsert 操作，如果 code 已存在则更新，否则插入
            result = self.actresses_data_collection.update_one(
                {'code': document['code']},
                {'$set': document},
                upsert=True
            )
            
            if result.upserted_id:
                app_logger.info(f"Inserted new actress: {document['name']} ({document['code']})")
            elif result.modified_count > 0:
                app_logger.info(f"Updated existing actress: {document['name']} ({document['code']})")
                
            return True
            
        except Exception as e:
            app_logger.info(f"Error writing actress data to MongoDB: {e}")
            return False
    
    def get_paginated_actresses(self, page=1, per_page=20, cup_size_filter=None):
        """获取分页演员数据"""
        try:
            if self.actresses_data_collection is None:
                return None, 0
                
            # 构建查询条件
            query = {}
            if cup_size_filter:
                query['cup_size'] = cup_size_filter
                
            actresses = list(self.actresses_data_collection.find(query)
                            .skip((page-1)*per_page)
                            .limit(per_page))
            total = self.actresses_data_collection.count_documents(query)
            return actresses, total
        except Exception as e:
            app_logger.info(f"获取分页演员数据错误: {e}")
            return None, 0
    
    def get_all_star(self):
        """获取全部演员数据"""
        try:
            if self.actresses_data_collection is None:
                return None
            return self.actresses_data_collection.find().sort("_id", 1)
        except Exception as e:
            app_logger.info(f"Error getting top actresses from MongoDB: {e}")
            return None

    def get_top_star(self):
        """获取前10个演员数据"""
        try:
            if self.actresses_data_collection is None:
                return None
            return self.actresses_data_collection.find().sort("_id", 1).limit(100)
        except Exception as e:
            app_logger.info(f"Error getting top actresses from MongoDB: {e}")
            return None
    
    def search_actresses(self, search_keyword=None, page=1, per_page=20, cup_size_filter=None):
        """搜索演员数据，支持按名称和代码搜索"""
        try:
            if self.actresses_data_collection is None:
                return None, 0
                
            # 构建查询条件
            query_conditions = []
            
            # 如果有搜索关键字，添加搜索条件
            if search_keyword and search_keyword.strip():
                search_regex = {'$regex': search_keyword.strip(), '$options': 'i'}
                # 在 name 和 code 字段中搜索关键字
                search_query = {
                    '$or': [
                        {'name': search_regex},
                        {'code': search_regex}
                    ]
                }
                query_conditions.append(search_query)
            
            # 添加罩杯筛选条件
            if cup_size_filter:
                query_conditions.append({'cup_size': cup_size_filter})
            
            # 合并所有查询条件
            if query_conditions:
                if len(query_conditions) > 1:
                    final_query = {'$and': query_conditions}
                else:
                    final_query = query_conditions[0]
            else:
                final_query = {}
                
            actresses = list(self.actresses_data_collection.find(final_query)
                            .skip((page-1)*per_page)
                            .limit(per_page))
            total = self.actresses_data_collection.count_documents(final_query)
            
            # 转换ObjectId为字符串
            for actress in actresses:
                if '_id' in actress:
                    actress['_id'] = str(actress['_id'])
                    
            return actresses, total
        except Exception as e:
            app_logger.info(f"搜索演员数据错误: {e}")
            return None, 0
    
    def add_retry_url(self, url, error_type, error_message,code):
        """添加失败URL到重试表"""
        try:
            # 检查URL是否已存在
            existing_url = self.retry_collection.find_one({'url': url})
            if existing_url:
                app_logger.info(f"重试URL已存在，跳过添加: {url}")
                return True
                
            self.retry_collection.insert_one({
                'url': url,
                'error_type': error_type,
                'error_message': error_message,
                'retry_count': 0,
                'last_retry_time': None,
                'created_at': datetime.now(),
                'status': 'pending',
                'code':code
            })
            return True
        except Exception as e:
            app_logger.error("添加重试URL失败: {url}, 错误: {e}")
            return False

    def get_pending_retry_urls(self, limit=100):
        """获取待重试的URL"""
        return list(self.retry_collection.find().limit(limit))
    
    def remove_retry(self, url):
        """删除重试URL记录"""
        try:
            result = self.retry_collection.delete_one({'url': url})
            if result.deleted_count > 0:
                app_logger.info(f"成功删除重试URL记录: {url}")
                return True
            else:
                app_logger.warning(f"未找到要删除的重试URL记录: {url}")
                return False
        except Exception as e:
            app_logger.error(f"删除重试URL记录失败: {url}, 错误: {e}")
            return False

    def update_retry_status(self, url, success, retry_count):
        """更新重试状态"""
        try:
            self.retry_collection.update_one(
                {'url': url},
                {'$set': {
                    'status': 'success' if success else 'failed',
                    'retry_count': retry_count + 1,
                    'last_retry_time': datetime.now()
                }}
            )
            return True
        except Exception as e:
            app_logger.error("更新重试状态失败: {url}, 错误: {e}")
            return False
            
    def get_all_movies(self, page=1, per_page=20, search_keyword=None, is_single=None, is_subtitle=None, sort_by='release_date'):
        """获取所有影片(分页)，支持关键字搜索和筛选"""
        try:
            if self.javbus_data_collection is None:
                return None, 0
            
            # 构建查询条件列表
            query_conditions = []
            
            # 如果有搜索关键字，添加搜索条件
            if search_keyword and search_keyword.strip():
                search_regex = {'$regex': search_keyword.strip(), '$options': 'i'}
                # 在 title、code、actresses 或 genres 字段中搜索关键字
                search_query = {
                    '$or': [
                        {'title': search_regex},
                        {'code': search_regex},
                        {'actresses': search_regex},
                        {'genres': search_regex}
                    ]
                }
                query_conditions.append(search_query)
            
            # 添加is_single筛选条件
            if is_single is not None:
                query_conditions.append({'is_single': is_single})
            
            # 添加is_subtitle筛选条件
            if is_subtitle is not None:
                query_conditions.append({'is_subtitle': is_subtitle})
            
            # 合并所有查询条件
            if query_conditions:
                final_query = {'$and': query_conditions}
            else:
                final_query = {}
            
            # 设置排序方式
            sort_field = sort_by if sort_by in ['release_date', 'title', 'code'] else 'release_date'
            sort_order = -1  # 降序排列
            
            movies = list(self.javbus_data_collection.find(
                final_query
            ).sort(sort_field, sort_order).skip((page-1)*per_page).limit(per_page))
            
            # 转换 ObjectId 为字符串以支持 JSON 序列化
            for movie in movies:
                if '_id' in movie:
                    movie['_id'] = str(movie['_id'])
            
            total = self.javbus_data_collection.count_documents(final_query)
            return movies, total
        except Exception as e:
            app_logger.error(f"获取所有影片错误: {e}")
            return None, 0
    
    def get_series_movies(self, series_name, page=1, per_page=20, search_keyword=None, is_single=None, is_subtitle=None):
        """获取指定系列的所有影片(分页)，按发布日期最新排序，支持关键字搜索和筛选"""
        try:
            if self.javbus_data_collection is None:
                return None, 0
            
            # 基础查询条件：系列名称完全匹配
            base_query = {'series': series_name}
            
            # 构建查询条件列表
            query_conditions = [base_query]
            
            # 如果有搜索关键字，添加额外的查询条件
            if search_keyword and search_keyword.strip():
                search_regex = {'$regex': search_keyword.strip(), '$options': 'i'}
                # 在 title 或 genres 字段中搜索关键字
                search_query = {
                    '$or': [
                        {'title': search_regex},
                        {'genres': search_regex}
                    ]
                }
                query_conditions.append(search_query)
            
            # 添加is_single筛选条件
            if is_single is not None:
                query_conditions.append({'is_single': is_single})
            
            # 添加is_subtitle筛选条件
            if is_subtitle is not None:
                query_conditions.append({'is_subtitle': is_subtitle})
            
            # 合并所有查询条件
            if len(query_conditions) > 1:
                final_query = {'$and': query_conditions}
            else:
                final_query = base_query
                
            movies = list(self.javbus_data_collection.find(
                final_query
            ).sort('release_date', -1).skip((page-1)*per_page).limit(per_page))
            
            total = self.javbus_data_collection.count_documents(final_query)
            return movies, total
        except Exception as e:
            app_logger.error(f"获取系列影片错误: {e}")
            return None, 0
    
    def get_actress_movies(self, actress_name, page=1, per_page=20, search_keyword=None, is_single=None, is_subtitle=None):
        """获取指定演员的所有影片(分页)，按发布日期最新排序，支持关键字搜索和筛选"""
        try:
            if self.javbus_data_collection is None:
                return None, 0
            
            # 基础查询条件：包含该演员
            base_query = {'actresses': {'$regex': actress_name, '$options': 'i'}}
            
            # 构建查询条件列表
            query_conditions = [base_query]
            
            # 如果有搜索关键字，添加额外的查询条件
            if search_keyword and search_keyword.strip():
                search_regex = {'$regex': search_keyword.strip(), '$options': 'i'}
                # 在 title 或 genres 字段中搜索关键字
                search_query = {
                    '$or': [
                        {'title': search_regex},
                        {'genres': search_regex}
                    ]
                }
                query_conditions.append(search_query)
            
            # 添加is_single筛选条件
            if is_single is not None:
                query_conditions.append({'is_single': is_single})
            
            # 添加is_subtitle筛选条件
            if is_subtitle is not None:
                query_conditions.append({'is_subtitle': is_subtitle})
            
            # 合并所有查询条件
            if len(query_conditions) > 1:
                final_query = {'$and': query_conditions}
            else:
                final_query = base_query
                
            movies = list(self.javbus_data_collection.find(
                final_query
            ).sort('release_date', -1).skip((page-1)*per_page).limit(per_page))
            
            total = self.javbus_data_collection.count_documents(final_query)
            return movies, total
        except Exception as e:
            app_logger.info(f"获取演员影片错误: {e}")
            return None, 0
    
    def get_studio_movies(self, studio_name, page=1, per_page=20, search_keyword=None, is_single=None, is_subtitle=None):
        """获取指定制作商的所有影片(分页)，按发布日期最新排序，支持关键字搜索和筛选"""
        try:
            if self.javbus_data_collection is None:
                return None, 0
            
            # 基础查询条件：制作商名称完全匹配
            base_query = {'studio': studio_name}
            
            # 构建查询条件列表
            query_conditions = [base_query]
            
            # 如果有搜索关键字，添加额外的查询条件
            if search_keyword and search_keyword.strip():
                search_regex = {'$regex': search_keyword.strip(), '$options': 'i'}
                # 在 title 或 genres 字段中搜索关键字
                search_query = {
                    '$or': [
                        {'title': search_regex},
                        {'genres': search_regex}
                    ]
                }
                query_conditions.append(search_query)
            
            # 添加is_single筛选条件
            if is_single is not None:
                query_conditions.append({'is_single': is_single})
            
            # 添加is_subtitle筛选条件
            if is_subtitle is not None:
                query_conditions.append({'is_subtitle': is_subtitle})
            
            # 合并所有查询条件
            if len(query_conditions) > 1:
                final_query = {'$and': query_conditions}
            else:
                final_query = base_query
                
            movies = list(self.javbus_data_collection.find(
                final_query
            ).sort('release_date', -1).skip((page-1)*per_page).limit(per_page))
            
            total = self.javbus_data_collection.count_documents(final_query)
            return movies, total
        except Exception as e:
            app_logger.error(f"获取制作商影片错误: {e}")
            return None, 0
    
    def parse_actress_to_array(self,movie):
        """解析数据库里的演员信息，将字符串转换为数组"""
        if movie == None:
            return None
        else:
            actresses = movie['actresses']
            if actresses == None:
                return None
            else:
                return  actresses.split('\n')

    def parser_magnet_links_to_array(self,movie):
        """解析数据库里的磁力信息，将字符串转换为数组"""
        if movie == None:
            return None
        else:
            magnet_links = movie['magnet_links']
            if magnet_links == None:
                return None
            else:
                return self.parse_string_to_array(magnet_links)

        
    def parse_string_to_array(self,data_string):
        """将字符串解析为数组"""
        if not data_string:
            return []
        
        data_list = []
        lines = data_string.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if line:
                try:
                    # 使用 ast.literal_eval 安全解析
                    data = ast.literal_eval(line)
                    data_list.append(data)
                except (ValueError, SyntaxError) as e:
                    app_logger.info(f"解析行失败: {line}, 错误: {e}")
        return data_list

    def record_failed_image_download(self, image_url, error_message, movie_code=None):
        """记录下载失败的图片地址"""
        try:
            # 创建失败图片记录集合（如果不存在）
            if not hasattr(self, 'failed_images_collection'):
                self.failed_images_collection = self.mongo_db['failed_images']
                # 创建索引
                self.failed_images_collection.create_index("image_url")
                self.failed_images_collection.create_index("created_at")
            
            # 检查是否已经记录过这个失败的图片
            existing_record = self.failed_images_collection.find_one({"image_url": image_url})
            
            if existing_record:
                # 更新失败次数和最后失败时间
                self.failed_images_collection.update_one(
                    {"image_url": image_url},
                    {
                        "$inc": {"failure_count": 1},
                        "$set": {
                            "last_failed_at": datetime.now(),
                            "last_error_message": str(error_message)
                        }
                    }
                )
            else:
                # 创建新的失败记录
                failed_image_doc = {
                    "image_url": image_url,
                    "movie_code": movie_code,
                    "error_message": str(error_message),
                    "failure_count": 1,
                    "created_at": datetime.now(),
                    "last_failed_at": datetime.now(),
                    "last_error_message": str(error_message)
                }
                self.failed_images_collection.insert_one(failed_image_doc)
            
            app_logger.info(f"已记录失败图片: {image_url}")
            return True
            
        except Exception as e:
            app_logger.info(f"记录失败图片时出错: {e}")
            return False

    def get_failed_images(self, limit=100):
        """获取失败的图片记录"""
        try:
            if not hasattr(self, 'failed_images_collection'):
                return []
            
            failed_images = list(self.failed_images_collection.find().sort("last_failed_at", -1).limit(limit))
            return failed_images
        except Exception as e:
            app_logger.info(f"获取失败图片记录时出错: {e}")
            return []

    def close_connection(self):
        """关闭 MongoDB 连接"""
        if self.mongo_client:
            self.mongo_client.close()
            self.mongo_client = None
            app_logger.info(f"MongoDB connection closed")
    
    def is_sehuatang_detail_craled(self,tid):
        return self.mongo_collection.find_one({'tid': tid})

    def save_sehuatang_detail_db(self, data):
        """保存数据到MongoDB"""
        if not self.mongo_client:
            app_logger.warning("MongoDB未连接，跳过数据保存")
            return False
        
        try:
            # 添加时间戳
            data['crawl_time'] = datetime.now()  
            # 检查是否已存在
            existing = self.mongo_collection.find_one({'tid': data['tid']})
            if existing:
                # 更新现有记录
                self.mongo_collection.update_one(
                    {'tid': data['tid']},

                    {'$set': data}
                )
                app_logger.info(f"更新MongoDB记录: {data['title']}")
            else:
                # 插入新记录
                self.mongo_collection.insert_one(data)
                app_logger.info(f"保存到MongoDB: {data['title']}")
            return True
        except Exception as e:
            app_logger.error(f"保存到MongoDB失败: {e}")
            return False
            
    def is_actress_processed(self, actress_code):
        """检查演员是否已经处理过"""
        if self.processed_actresses_collection is None:
            return False
        return self.processed_actresses_collection.find_one({'actress_code': actress_code}) is not None
    
    def mark_actress_as_processed(self, actress_code, actress_name=None):
        """标记演员为已处理"""
        if self.processed_actresses_collection is None:
            return False
        
        try:
            doc = {
                'actress_code': actress_code,
                'actress_name': actress_name,
                'processed_at': datetime.now()
            }
            
            # 使用 upsert 避免重复插入
            self.processed_actresses_collection.update_one(
                {'actress_code': actress_code},
                {'$set': doc},
                upsert=True
            )
            app_logger.info(f"标记演员 {actress_code} 为已处理")
            return True
        except Exception as e:
            app_logger.error(f"标记演员 {actress_code} 为已处理失败: {e}")
            return False
    
    def get_processed_actresses_count(self):
        """获取已处理演员数量"""
        if self.processed_actresses_collection is None:
            return 0
        return self.processed_actresses_collection.count_documents({})
    
    def clear_processed_actresses(self):
        """清空已处理演员记录（用于重新开始处理）"""
        if self.processed_actresses_collection is None:
            return False
        
        try:
            result = self.processed_actresses_collection.delete_many({})
            app_logger.info(f"清空了 {result.deleted_count} 条已处理演员记录")
            return True
        except Exception as e:
            app_logger.error(f"清空已处理演员记录失败: {e}")
            return False
    
    def get_actress_code_by_name(self, actress_name):
        """根据演员名称查询演员code"""
        if self.processed_actresses_collection is None:
            return None
        
        try:
            # 在processed_actresses集合中查找匹配的演员名称
            actress = self.processed_actresses_collection.find_one(
                {'actress_name': {'$regex': f'^{actress_name}$', '$options': 'i'}}
            )
            
            if actress:
                return actress.get('actress_code')
            else:
                app_logger.info(f"未找到演员 {actress_name} 的code")
                return None
        except Exception as e:
            app_logger.error(f"查询演员code失败: {e}")
            return None
    
    def _create_default_admin(self):
        """创建默认管理员用户"""
        try:
            # 检查是否已存在管理员用户
            if self.users_collection.find_one({'username': 'admin'}):
                return
            
            import hashlib
            # 默认密码：admin123
            password_hash = hashlib.sha256('admin123'.encode()).hexdigest()
            
            admin_user = {
                'username': 'admin',
                'password_hash': password_hash,
                'role': 'admin',
                'created_at': datetime.now(),
                'is_active': True
            }
            
            self.users_collection.insert_one(admin_user)
            app_logger.info("默认管理员用户创建成功 (用户名: admin, 密码: admin123)")
            
        except Exception as e:
            app_logger.error(f"创建默认管理员用户失败: {e}")
    
    def authenticate_user(self, username, password):
        """用户认证"""
        try:
            import hashlib
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            user = self.users_collection.find_one({
                'username': username,
                'password_hash': password_hash,
                'is_active': True
            })
            
            if user:
                # 更新最后登录时间
                self.users_collection.update_one(
                    {'_id': user['_id']},
                    {'$set': {'last_login': datetime.now()}}
                )
                return {
                    'user_id': str(user['_id']),
                    'username': user['username'],
                    'role': user['role']
                }
            return None
            
        except Exception as e:
            app_logger.error(f"用户认证失败: {e}")
            return None
    
    def change_password(self, username, old_password, new_password):
        """修改用户密码"""
        try:
            import hashlib
            
            # 验证旧密码
            old_password_hash = hashlib.sha256(old_password.encode()).hexdigest()
            user = self.users_collection.find_one({
                'username': username,
                'password_hash': old_password_hash,
                'is_active': True
            })
            
            if not user:
                return {
                    'success': False,
                    'error': '原密码错误'
                }
            
            # 生成新密码哈希
            new_password_hash = hashlib.sha256(new_password.encode()).hexdigest()
            
            # 更新密码
            result = self.users_collection.update_one(
                {'_id': user['_id']},
                {
                    '$set': {
                        'password_hash': new_password_hash,
                        'password_updated_at': datetime.now()
                    }
                }
            )
            
            if result.modified_count > 0:
                app_logger.info(f"用户 {username} 密码修改成功")
                return {
                    'success': True,
                    'message': '密码修改成功'
                }
            else:
                return {
                    'success': False,
                    'error': '密码修改失败'
                }
                
        except Exception as e:
            app_logger.error(f"修改密码失败: {e}")
            return {
                'success': False,
                'error': f'修改密码失败: {str(e)}'
            }

    def create_user_session(self, user_info):
        """创建用户会话"""
        try:
            import uuid
            session_id = str(uuid.uuid4())
            
            session_data = {
                'session_id': session_id,
                'user_id': user_info['user_id'],
                'username': user_info['username'],
                'role': user_info['role'],
                'created_at': datetime.now(),
                'last_accessed': datetime.now(),
                'expires_at': datetime.now() + timedelta(hours=24)  # 24小时过期
            }
            
            self.sessions_collection.insert_one(session_data)
            return session_id
            
        except Exception as e:
            app_logger.error(f"创建用户会话失败: {e}")
            return None
    
    def get_user_session(self, session_id):
        """获取用户会话信息"""
        try:
            session = self.sessions_collection.find_one({
                'session_id': session_id,
                'expires_at': {'$gt': datetime.now()}
            })
            
            if session:
                # 更新最后访问时间
                self.sessions_collection.update_one(
                    {'session_id': session_id},
                    {'$set': {'last_accessed': datetime.now()}}
                )
                return {
                    'user_id': session['user_id'],
                    'username': session['username'],
                    'role': session['role']
                }
            return None
            
        except Exception as e:
            app_logger.error(f"获取用户会话失败: {e}")
            return None
    
    def delete_user_session(self, session_id):
        """删除用户会话（退出登录）"""
        try:
            result = self.sessions_collection.delete_one({'session_id': session_id})
            return result.deleted_count > 0
            
        except Exception as e:
            app_logger.error(f"删除用户会话失败: {e}")
            return False
    
    def cleanup_expired_sessions(self):
        """清理过期会话"""
        try:
            result = self.sessions_collection.delete_many({
                'expires_at': {'$lt': datetime.now()}
            })
            if result.deleted_count > 0:
                app_logger.info(f"清理了 {result.deleted_count} 个过期会话")
            return result.deleted_count
            
        except Exception as e:
            app_logger.error(f"清理过期会话失败: {e}")
            return 0

    def get_backup_records(self):
        """获取备份记录"""
        if self.mongo_db is None:
            return []
        backup_collection = self.mongo_db['backup_records']
        return list(backup_collection.find().sort('created_at', -1))
    
    def save_backup_record(self, backup_info):
        """保存备份记录"""
        if self.mongo_db is None:
            raise Exception('MongoDB未初始化')
        
        backup_collection = self.mongo_db['backup_records']
        backup_doc = {
            'backup_file': backup_info['backup_file'],
            'folders_backed_up': backup_info['folders_backed_up'],
            'total_folders': backup_info['total_folders'],
            'backup_size': backup_info['backup_size'],
            'created_at': datetime.now(),
            'status': 'completed'
        }
        
        result = backup_collection.insert_one(backup_doc)
        return str(result.inserted_id)
    
    def get_backed_up_folders(self):
        """获取已备份的文件夹列表"""
        if self.mongo_db is None:
            return set()
        
        backup_collection = self.mongo_db['backup_records']
        backed_up_folders = set()
        
        for record in backup_collection.find():
            if 'folders_backed_up' in record:
                backed_up_folders.update(record['folders_backed_up'])
        
        return backed_up_folders
    
    def save_genre_data(self, genre_info):
        """保存类别数据到数据库"""
        try:
            if self.genres_collection is None:
                app_logger.error("genres_collection未初始化")
                return False
            
            # 检查是否已存在相同的类别代码
            existing = self.genres_collection.find_one({'code': genre_info['code']})
            
            if existing:
                # 更新现有记录
                result = self.genres_collection.update_one(
                    {'code': genre_info['code']},
                    {'$set': {
                        'name': genre_info['name'],
                        'url': genre_info['url'],
                        'category': genre_info.get('category', ''),
                        'updated_at': datetime.now()
                    }}
                )
                app_logger.info(f"更新类别数据: {genre_info['name']} ({genre_info['code']})")
                return result.modified_count > 0
            else:
                # 插入新记录
                genre_doc = {
                    'code': genre_info['code'],
                    'name': genre_info['name'],
                    'url': genre_info['url'],
                    'category': genre_info.get('category', ''),
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                
                result = self.genres_collection.insert_one(genre_doc)
                app_logger.info(f"保存新类别数据: {genre_info['name']} ({genre_info['code']})")
                return result.inserted_id is not None
                
        except Exception as e:
            app_logger.error(f"保存类别数据失败: {e}")
            return False
    
    def get_all_genres(self, category=None):
        """获取所有类别数据"""
        try:
            if self.genres_collection is None:
                return []
            
            query = {}
            if category:
                query['category'] = category
            
            genres = list(self.genres_collection.find(query).sort('name', 1))
            return genres
            
        except Exception as e:
            app_logger.error(f"获取类别数据失败: {e}")
            return []
    
    def get_genre_by_code(self, code):
        """根据代码获取类别信息"""
        try:
            if self.genres_collection is None:
                return None
            
            return self.genres_collection.find_one({'code': code})
            
        except Exception as e:
            app_logger.error(f"获取类别信息失败: {e}")
            return None
    
    def search_movies_by_genres(self, names=None, page=1, per_page=20, search_keyword=None, is_single=None, is_subtitle=None, sort_by='release_date'):
        """根据分类代码搜索影片，支持多选分类、关键字、单体、字幕筛选"""
        try:
            if self.javbus_data_collection is None:
                return None, 0
            
            # 构建查询条件列表
            query_conditions = []
            genre_names = names
            # 如果指定了分类代码，添加分类筛选条件
            if genre_names and len(genre_names) > 0:
                # 支持多选分类，影片的genres字段包含任一指定分类即可
                genre_query = {
                    '$or': [
                        {'genres': {'$regex': name, '$options': 'i'}} for name in genre_names
                    ]
                }
                query_conditions.append(genre_query)
            
            # 如果有搜索关键字，添加搜索条件
            if search_keyword and search_keyword.strip():
                search_regex = {'$regex': search_keyword.strip(), '$options': 'i'}
                # 在 title、code、actresses 或 genres 字段中搜索关键字
                search_query = {
                    '$or': [
                        {'title': search_regex}
                    ]
                }
                query_conditions.append(search_query)
            
            # 添加is_single筛选条件
            if is_single is not None:
                query_conditions.append({'is_single': is_single})
            
            # 添加is_subtitle筛选条件
            if is_subtitle is not None:
                query_conditions.append({'is_subtitle': is_subtitle})
            
            # 合并所有查询条件
            if query_conditions:
                final_query = {'$and': query_conditions}
            else:
                final_query = {}
            
            # 设置排序方式
            sort_field = sort_by if sort_by in ['release_date', 'title', 'code'] else 'release_date'
            sort_order = -1  # 降序排列
            
            movies = list(self.javbus_data_collection.find(
                final_query
            ).sort(sort_field, sort_order).skip((page-1)*per_page).limit(per_page))
            
            # 转换 ObjectId 为字符串以支持 JSON 序列化
            for movie in movies:
                if '_id' in movie:
                    movie['_id'] = str(movie['_id'])
             
            total = self.javbus_data_collection.count_documents(final_query)
            return movies, total
            
        except Exception as e:
            app_logger.error(f"根据分类搜索影片错误: {e}")
            return None, 0
    
    def get_genres_by_category(self):
        """按分类分组获取所有类别数据"""
        try:
            if self.genres_collection is None:
                return {}
            
            # 获取所有类别数据
            all_genres = list(self.genres_collection.find({}).sort('name', 1))
            
            # 按category分组
            genres_by_category = {}
            for genre in all_genres:
                category = genre.get('category', '其他')
                if category not in genres_by_category:
                    genres_by_category[category] = []
                genres_by_category[category].append(genre)
            
            return genres_by_category
            
        except Exception as e:
            app_logger.error(f"按分类获取类别数据失败: {e}")
            return {}
    
    def add_actress_favorite(self, user_id, actress_code, actress_name):
        """添加演员收藏"""
        try:
            if self.actress_favorites_collection is None:
                raise Exception('MongoDB未初始化')
            
            # 检查是否已经收藏
            existing = self.actress_favorites_collection.find_one({
                'user_id': user_id,
                'actress_code': actress_code
            })
            
            if existing:
                return {'success': False, 'message': '已经收藏过该演员'}
            
            # 添加收藏记录
            favorite_doc = {
                'user_id': user_id,
                'actress_code': actress_code,
                'actress_name': actress_name,
                'created_at': datetime.now()
            }
            
            result = self.actress_favorites_collection.insert_one(favorite_doc)
            
            if result.inserted_id:
                app_logger.info(f"用户 {user_id} 收藏演员 {actress_name} ({actress_code})")
                return {'success': True, 'message': '收藏成功'}
            else:
                return {'success': False, 'message': '收藏失败'}
                
        except Exception as e:
            app_logger.error(f"添加演员收藏失败: {e}")
            return {'success': False, 'message': f'收藏失败: {str(e)}'}
    
    def remove_actress_favorite(self, user_id, actress_code):
        """取消演员收藏"""
        try:
            if self.actress_favorites_collection is None:
                raise Exception('MongoDB未初始化')
            
            result = self.actress_favorites_collection.delete_one({
                'user_id': user_id,
                'actress_code': actress_code
            })
            
            if result.deleted_count > 0:
                app_logger.info(f"用户 {user_id} 取消收藏演员 {actress_code}")
                return {'success': True, 'message': '取消收藏成功'}
            else:
                return {'success': False, 'message': '未找到收藏记录'}
                
        except Exception as e:
            app_logger.error(f"取消演员收藏失败: {e}")
            return {'success': False, 'message': f'取消收藏失败: {str(e)}'}
    
    def is_actress_favorited(self, user_id, actress_code):
        """检查演员是否已被收藏"""
        try:
            if self.actress_favorites_collection is None:
                return False
            
            favorite = self.actress_favorites_collection.find_one({
                'user_id': user_id,
                'actress_code': actress_code
            })
            
            return favorite is not None
            
        except Exception as e:
            app_logger.error(f"检查演员收藏状态失败: {e}")
            return False
    
    def get_user_favorite_actresses(self, user_id, page=1, per_page=20, cup_size_filter=None):
        """获取用户收藏的演员列表（分页）"""
        try:
            if self.actress_favorites_collection is None or self.actresses_data_collection is None:
                return None, 0
            
            # 获取用户收藏的演员代码列表
            favorite_codes = []
            favorites = self.actress_favorites_collection.find({'user_id': user_id})
            for fav in favorites:
                favorite_codes.append(fav['actress_code'])
            
            if not favorite_codes:
                return [], 0
            
            # 构建查询条件
            query = {'code': {'$in': favorite_codes}}
            if cup_size_filter:
                query['cup_size'] = cup_size_filter
            
            # 获取演员详细信息
            actresses = list(self.actresses_data_collection.find(query)
                           .skip((page-1)*per_page)
                           .limit(per_page))
            
            # 转换ObjectId为字符串
            for actress in actresses:
                if '_id' in actress:
                    actress['_id'] = str(actress['_id'])
            
            total = self.actresses_data_collection.count_documents(query)
            
            return actresses, total
            
        except Exception as e:
            app_logger.error(f"获取用户收藏演员列表失败: {e}")
            return None, 0
    
    def get_actress_favorite_count(self, actress_code):
        """获取演员的收藏数量"""
        try:
            if self.actress_favorites_collection is None:
                return 0
            
            count = self.actress_favorites_collection.count_documents({
                'actress_code': actress_code
            })
            
            return count
            
        except Exception as e:
            app_logger.error(f"获取演员收藏数量失败: {e}")
            return 0
    
    def get_actress_favorites(self, user_id, page=1, per_page=20, search='', cup_size='', sort_order='latest'):
        """获取用户收藏的演员列表（支持搜索、筛选和排序）"""
        try:
            if self.actress_favorites_collection is None or self.actresses_data_collection is None:
                return {
                    'favorites': [],
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total': 0,
                        'total_pages': 0,
                        'has_prev': False,
                        'has_next': False
                    }
                }
            
            # 获取用户收藏的演员代码列表
            favorite_codes = []
            favorites = self.actress_favorites_collection.find({'user_id': user_id})
            for fav in favorites:
                favorite_codes.append(fav['actress_code'])
            
            if not favorite_codes:
                return {
                    'favorites': [],
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total': 0,
                        'total_pages': 0,
                        'has_prev': False,
                        'has_next': False
                    }
                }
            
            # 构建查询条件
            query = {'code': {'$in': favorite_codes}}
            
            # 添加搜索条件
            if search:
                query['name'] = {'$regex': search, '$options': 'i'}
            
            # 添加罩杯筛选
            if cup_size:
                query['cup_size'] = cup_size
            
            # 设置排序
            sort_field = '_id'
            sort_direction = -1  # 默认降序（最新）
            
            if sort_order == 'name_asc':
                sort_field = 'name'
                sort_direction = 1
            elif sort_order == 'name_desc':
                sort_field = 'name'
                sort_direction = -1
            elif sort_order == 'oldest':
                sort_field = '_id'
                sort_direction = 1
            # 'latest' 使用默认值
            
            # 获取总数
            total = self.actresses_data_collection.count_documents(query)
            
            # 获取演员详细信息
            actresses = list(self.actresses_data_collection.find(query)
                           .sort(sort_field, sort_direction)
                           .skip((page-1)*per_page)
                           .limit(per_page))
            
            # 转换ObjectId为字符串
            for actress in actresses:
                if '_id' in actress:
                    actress['_id'] = str(actress['_id'])
            
            # 计算分页信息
            total_pages = (total + per_page - 1) // per_page
            
            return {
                'favorites': actresses,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'total_pages': total_pages,
                    'has_prev': page > 1,
                    'has_next': page < total_pages
                }
            }
            
        except Exception as e:
            app_logger.error(f"获取用户收藏演员列表失败: {e}")
            return {
                'favorites': [],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': 0,
                    'total_pages': 0,
                    'has_prev': False,
                    'has_next': False
                }
            }

    def get_all_favorite_actresses(self):
        """获取所有收藏的演员列表（不分用户）"""
        try:
            if self.actress_favorites_collection is None or self.actresses_data_collection is None:
                return None
            
            # 获取所有收藏的演员代码列表（去重）
            favorite_codes = self.actress_favorites_collection.distinct('actress_code')
            
            if not favorite_codes:
                return []
            
            # 获取演员详细信息
            actresses = list(self.actresses_data_collection.find({'code': {'$in': favorite_codes}}))
            
            # 转换ObjectId为字符串
            for actress in actresses:
                if '_id' in actress:
                    actress['_id'] = str(actress['_id'])
            
            return actresses
            
        except Exception as e:
            app_logger.error(f"获取所有收藏演员列表失败: {e}")
            return None

    # 系列收藏相关函数
    def add_series_favorite(self, user_id, series_name, cover_url=None):
        """添加系列收藏"""
        try:
            if self.series_favorites_collection is None:
                app_logger.error("系列收藏集合未初始化")
                return False
            
            # 检查是否已经收藏
            existing = self.series_favorites_collection.find_one({
                'user_id': user_id,
                'series_name': series_name
            })
            
            if existing:
                app_logger.info(f"用户 {user_id} 已收藏系列 {series_name}")
                return True
            
            favorite_doc = {
                'user_id': user_id,
                'series_name': series_name,
                'cover_url': cover_url,
                'created_at': datetime.now()
            }
            
            result = self.series_favorites_collection.insert_one(favorite_doc)
            app_logger.info(f"用户 {user_id} 收藏系列 {series_name} 成功")
            return True
            
        except Exception as e:
            app_logger.error(f"添加系列收藏失败: {e}")
            return False
    
    def remove_series_favorite(self, user_id, series_name):
        """取消系列收藏"""
        try:
            if self.series_favorites_collection is None:
                app_logger.error("系列收藏集合未初始化")
                return False
            
            result = self.series_favorites_collection.delete_one({
                'user_id': user_id,
                'series_name': series_name
            })
            
            if result.deleted_count > 0:
                app_logger.info(f"用户 {user_id} 取消收藏系列 {series_name} 成功")
                return True
            else:
                app_logger.warning(f"用户 {user_id} 未收藏系列 {series_name}")
                return False
                
        except Exception as e:
            app_logger.error(f"取消系列收藏失败: {e}")
            return False
    
    def is_series_favorited(self, user_id, series_name):
        """检查系列是否已收藏"""
        try:
            if self.series_favorites_collection is None:
                return False
            
            result = self.series_favorites_collection.find_one({
                'user_id': user_id,
                'series_name': series_name
            })
            
            return result is not None
            
        except Exception as e:
            app_logger.error(f"检查系列收藏状态失败: {e}")
            return False
    
    def get_user_favorite_series(self, user_id, page=1, per_page=20):
        """获取用户收藏的系列列表"""
        try:
            if self.series_favorites_collection is None:
                return {'series': [], 'total': 0, 'page': page, 'per_page': per_page, 'total_pages': 0}
            
            skip = (page - 1) * per_page
            
            # 获取总数
            total = self.series_favorites_collection.count_documents({'user_id': user_id})
            
            # 获取分页数据
            cursor = self.series_favorites_collection.find(
                {'user_id': user_id}
            ).sort('created_at', -1).skip(skip).limit(per_page)
            
            series_list = list(cursor)
            
            # 转换ObjectId为字符串
            for series in series_list:
                series['_id'] = str(series['_id'])
            
            total_pages = (total + per_page - 1) // per_page
            
            return {
                'series': series_list,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages
            }
            
        except Exception as e:
            app_logger.error(f"获取用户收藏系列失败: {e}")
            return {'series': [], 'total': 0, 'page': page, 'per_page': per_page, 'total_pages': 0}
    
    # 厂商收藏相关函数
    def add_studio_favorite(self, user_id, studio_name, cover_image=None):
        """添加厂商收藏"""
        try:
            if self.studio_favorites_collection is None:
                app_logger.error("厂商收藏集合未初始化")
                return False
            
            # 检查是否已经收藏
            existing = self.studio_favorites_collection.find_one({
                'user_id': user_id,
                'studio_name': studio_name
            })
            
            if existing:
                app_logger.info(f"用户 {user_id} 已收藏厂商 {studio_name}")
                return True
            
            favorite_doc = {
                'user_id': user_id,
                'studio_name': studio_name,
                'cover_url': cover_image,
                'created_at': datetime.now()
            }
            
            result = self.studio_favorites_collection.insert_one(favorite_doc)
            app_logger.info(f"用户 {user_id} 收藏厂商 {studio_name} 成功")
            return True
            
        except Exception as e:
            app_logger.error(f"添加厂商收藏失败: {e}")
            return False
    
    def remove_studio_favorite(self, user_id, studio_name):
        """取消厂商收藏"""
        try:
            if self.studio_favorites_collection is None:
                app_logger.error("厂商收藏集合未初始化")
                return False
            
            result = self.studio_favorites_collection.delete_one({
                'user_id': user_id,
                'studio_name': studio_name
            })
            
            if result.deleted_count > 0:
                app_logger.info(f"用户 {user_id} 取消收藏厂商 {studio_name} 成功")
                return True
            else:
                app_logger.warning(f"用户 {user_id} 未收藏厂商 {studio_name}")
                return False
                
        except Exception as e:
            app_logger.error(f"取消厂商收藏失败: {e}")
            return False
    
    def is_studio_favorited(self, user_id, studio_name):
        """检查厂商是否已收藏"""
        try:
            if self.studio_favorites_collection is None:
                return False
            
            result = self.studio_favorites_collection.find_one({
                'user_id': user_id,
                'studio_name': studio_name
            })
            
            return result is not None
            
        except Exception as e:
            app_logger.error(f"检查厂商收藏状态失败: {e}")
            return False
    
    def get_user_favorite_studios(self, user_id, page=1, per_page=20):
        """获取用户收藏的厂商列表"""
        try:
            if self.studio_favorites_collection is None:
                return {'studios': [], 'total': 0, 'page': page, 'per_page': per_page, 'total_pages': 0}
            
            skip = (page - 1) * per_page
            
            # 获取总数
            total = self.studio_favorites_collection.count_documents({'user_id': user_id})
            
            # 获取分页数据
            cursor = self.studio_favorites_collection.find(
                {'user_id': user_id}
            ).sort('created_at', -1).skip(skip).limit(per_page)
            
            studios_list = list(cursor)
            
            # 转换ObjectId为字符串
            for studio in studios_list:
                studio['_id'] = str(studio['_id'])
            
            total_pages = (total + per_page - 1) // per_page
            
            return {
                'studios': studios_list,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages
            }
            
        except Exception as e:
            app_logger.error(f"获取用户收藏厂商失败: {e}")
            return {'studios': [], 'total': 0, 'page': page, 'per_page': per_page, 'total_pages': 0}
# 创建全局数据库管理器实例
db_manager = DatabaseManager()

# 在程序退出时自动关闭连接
def cleanup_db_connection():
    db_manager.close_connection()
atexit.register(cleanup_db_connection)

    

    

 




