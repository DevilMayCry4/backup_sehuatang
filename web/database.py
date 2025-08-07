#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库模块 - MongoDB连接和操作
"""

from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
import sys
import os
from dotenv import load_dotenv
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
            
            # JavBus 爬虫相关集合
            self.javbus_data_collection = self.mongo_db['javbus_data']
            self.actresses_data_collection = self.mongo_db['actresses_data']
            
            # 创建索引
            self.add_movie_collection.create_index("series_name")
            self.add_movie_collection.create_index("movie_code")
            self.add_movie_collection.create_index("created_at")
            
            # 为found_movies表创建索引
            self.found_movies_collection.create_index("movie_code")
            self.found_movies_collection.create_index("series_name")
            self.found_movies_collection.create_index("subscription_id")
            self.found_movies_collection.create_index("found_at")
            
            # JavBus 数据索引
            self.javbus_data_collection.create_index("url", unique=True)
            self.javbus_data_collection.create_index("code")
            self.javbus_data_collection.create_index("title")
            
            # 演员数据索引
            self.actresses_data_collection.create_index("code", unique=True)
            self.actresses_data_collection.create_index("name")

            #重试索引
            self.retry_collection.create_index("url", unique=True)
            
            app_logger.info(f"MongoDB连接成功")
            return True
        except Exception as e:
            app_logger.info(f"MongoDB连接失败: {e}")
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
                'uncensored': dict_jav.get('無碼', 0)
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
    
    def add_retry_url(self, url, error_type, error_message):
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
                'status': 'pending'
            })
            return True
        except Exception as e:
            app_logger.error("添加重试URL失败: {url}, 错误: {e}")
            return False

    def get_pending_retry_urls(self, limit=100):
        """获取待重试的URL"""
        return list(self.retry_collection.find({
            'status': 'pending'
        }).limit(limit))

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
            
    def get_actress_movies(self, actress_name, page=1, per_page=20):
        """获取指定演员的所有影片(分页)"""
        try:
            if self.javbus_data_collection is None:
                return None, 0
                
            movies = list(self.javbus_data_collection.find(
                {'actresses': {'$regex': actress_name, '$options': 'i'}}
            ).skip((page-1)*per_page).limit(per_page))
            
            total = self.javbus_data_collection.count_documents(
                {'actresses': {'$regex': actress_name, '$options': 'i'}}
            )
            return movies, total
        except Exception as e:
            app_logger.info(f"获取演员影片错误: {e}")
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

# 创建全局数据库管理器实例
db_manager = DatabaseManager()
db_manager.init_mongodb()

# 在程序退出时自动关闭连接
def cleanup_db_connection():
    db_manager.close_connection()

atexit.register(cleanup_db_connection)

# ==================== 兼容性函数 ====================
# 为了保持与原 db_manger.py 的兼容性，提供以下函数

def get_mongo_connection():
    """获取 MongoDB 连接 - 兼容性函数"""
    if db_manager.mongo_db is None:
        db_manager.init_mongodb()
    return db_manager.mongo_db

def init_db():
    """初始化数据库 - 兼容性函数"""
    return db_manager.init_mongodb()

def write_jav_movie(dict_jav):
    """写入JAV电影数据 - 兼容性函数"""
    return db_manager.write_jav_movie(dict_jav)

def refresh_data(dict_jav, url):
    """更新磁力链接数据 - 兼容性函数"""
    return db_manager.refresh_data(dict_jav, url)

def check_url_not_in_table(url):
    """检查URL是否不在表中 - 兼容性函数"""
    return db_manager.check_url_not_in_table(url)

def is_movie_crawed(code):
    """检查电影是否已爬取 - 兼容性函数"""
    return db_manager.is_movie_crawed(code)

def read_magnets_from_table(url):
    """读取磁力链接 - 兼容性函数"""
    return db_manager.read_magnets_from_table(url)

def write_actress_data(actress_info, local_image_path=None):
    """写入演员数据 - 兼容性函数"""
    return db_manager.write_actress_data(actress_info, local_image_path)

def create_actress_db():
    """创建演员数据库 - 兼容性函数"""
    # 索引创建已在 init_mongodb 中处理
    return True

def close_connection():
    """关闭连接 - 兼容性函数"""
    return db_manager.close_connection()

def get_all_star():
    """获取所有演员 - 兼容性函数"""
    return db_manager.get_all_star()

def get_top_star():
    """获取热门演员 - 兼容性函数"""
    return db_manager.get_top_star()




