#!/usr/bin/env python
#-*-coding:utf-8-*-

from operator import le
import os
from pymongo import MongoClient
from dotenv import load_dotenv

# 加载环境变量
load_dotenv('/root/backup_sehuatang/copy.env')

# MongoDB 配置
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://192.168.100.227:38234/')
MONGO_DB = os.getenv('MONGO_DB', 'javbus_crawler')

# 全局 MongoDB 客户端
_mongo_client = None
_mongo_db = None

def get_mongo_connection():
    """获取 MongoDB 连接"""
    global _mongo_client, _mongo_db
    if _mongo_client is None:
        _mongo_client = MongoClient(MONGO_URI)
        _mongo_db = _mongo_client[MONGO_DB]
    return _mongo_db

def init_db():
    """创建数据库和集合索引（如果不存在）"""
    try:
        db = get_mongo_connection()
        collection = db.javbus_data
        
        # 创建索引以提高查询性能
        collection.create_index("url", unique=True)
        collection.create_index("code")
        collection.create_index("title")
        
        print("MongoDB collection and indexes created successfully")
        return True
    except Exception as e:
        print(f"Error creating MongoDB collection: {e}")
        return False

 
def write_jav_movie(dict_jav):
    """写入数据到 MongoDB"""
    try:
        db = get_mongo_connection()
        collection = db.javbus_data
        
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
        result = collection.update_one(
            {'url': document['url']},
            {'$set': document},
            upsert=True
        )
        
        if result.upserted_id:
            print(f"Inserted new document with URL: {document['url']}")
        elif result.modified_count > 0:
            print(f"Updated existing document with URL: {document['url']}")
            
        return True
        
    except Exception as e:
        print(f"Error writing data to MongoDB: {e}")
        re


def refresh_data(dict_jav, url):
    """更新指定 URL 的磁力链接数据"""
    try:
        db = get_mongo_connection()
        collection = db.javbus_data
        
        # 更新磁力链接
        result = collection.update_one(
            {'URL': {'$regex': f'^{url}$', '$options': 'i'}},  # 不区分大小写匹配
            {'$set': {'磁力链接': dict_jav.get('磁力链接', '')}}
        )
        
        if result.modified_count > 0:
            print(f"Updated magnet links for URL: {url}")
            return True
        else:
            print(f"No document found with URL: {url}")
            return False
            
    except Exception as e:
        print(f"Error refreshing data in MongoDB: {e}")
        return False

def check_url_not_in_table(url):
    """检查 URL 是否不在数据库中，如果不存在返回 True，存在返回 False"""
    try:
        db = get_mongo_connection()
        collection = db.javbus_data
        
        # 不区分大小写查询
        result = collection.find_one(
            {'URL': {'$regex': f'^{url}$', '$options': 'i'}},
            {'_id': 1}  # 只返回 _id 字段以提高性能
        )
        
        return result is None
        
    except Exception as e:
        print(f"Error checking URL in MongoDB: {e}")
        return True  # 出错时假设不存在


def is_movie_crawed(code):
    try:
        db = get_mongo_connection()
        collection = db.javbus_data
        
        # 不区分大小写查询
        result = collection.find_one(
            {'code': {'$regex': f'^{code}$', '$options': 'i'}}
        ) 
        return result != None and (result) > 0
            
    except Exception as e:
        print(f"Error reading magnets from MongoDB: {e}")
        return False

def read_magnets_from_table(url):
    """从数据库中读取指定 URL 的磁力链接"""
    try:
        db = get_mongo_connection()
        collection = db.javbus_data
        
        # 不区分大小写查询
        result = collection.find_one(
            {'URL': {'$regex': f'^{url}$', '$options': 'i'}},
            {'磁力链接': 1, '_id': 0}  # 只返回磁力链接字段
        )
        
        if result and result.get('磁力链接'):
            return [(result['磁力链接'],)]  # 返回与原 SQLite 版本兼容的格式
        else:
            return None
            
    except Exception as e:
        print(f"Error reading magnets from MongoDB: {e}")
        return None

def write_actress_data(actress_info, local_image_path=None):
    """写入女优数据到 MongoDB"""
    try:
        db = get_mongo_connection()
        collection = db.actresses_data
        
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
        result = collection.update_one(
            {'code': document['code']},
            {'$set': document},
            upsert=True
        )
        
        if result.upserted_id:
            print(f"Inserted new actress: {document['name']} ({document['code']})")
        elif result.modified_count > 0:
            print(f"Updated existing actress: {document['name']} ({document['code']})")
            
        return True
        
    except Exception as e:
        print(f"Error writing actress data to MongoDB: {e}")
        return False

def create_actress_db():
    """创建女优数据库集合和索引"""
    try:
        db = get_mongo_connection()
        collection = db.actresses_data
        
        # 创建索引以提高查询性能
        collection.create_index("code", unique=True)
        collection.create_index("name")
        
        print("Actresses MongoDB collection and indexes created successfully")
        return True
    except Exception as e:
        print(f"Error creating actresses MongoDB collection: {e}")
        return False

def close_connection():
    """关闭 MongoDB 连接"""
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()
        _mongo_client = None
        print("MongoDB connection closed")

# 在程序退出时自动关闭连接
import atexit
atexit.register(close_connection)