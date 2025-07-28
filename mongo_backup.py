import pymongo
from datetime import datetime
import logging
import os

# 配置日志
logging.basicConfig(
    filename='backup.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class MongoBackup:
    def __init__(self):
        # 源数据库连接
        self.source_client = pymongo.MongoClient("mongodb+srv://readonly:cS9NSuiJ1ebHnUL0@cluster0.8mosa.mongodb.net/Cluster0?retryWrites=true&w=majority")
        self.source_db = self.source_client["sehuatang"]
        
        # 备份数据库连接（使用本地MongoDB实例）
        self.backup_client = pymongo.MongoClient("mongodb://192.168.100.227:27017/")
        self.backup_db = self.backup_client["sehuatang_backup"]
        
        # 创建备份元数据集合
        self.meta_collection = self.backup_db["backup_metadata"]

    def get_last_backup_time(self, collection_name):
        meta = self.meta_collection.find_one({"collection_name": collection_name})
        return meta["last_backup_time"] if meta else None

    def update_backup_time(self, collection_name):
        self.meta_collection.update_one(
            {"collection_name": collection_name},
            {"$set": {"last_backup_time": datetime.utcnow()}},
            upsert=True
        )

    def backup_collection(self, collection_name):
        source_collection = self.source_db[collection_name]
        backup_collection = self.backup_db[collection_name]
        
        # 获取上次备份时间
        last_backup_time = self.get_last_backup_time(collection_name)
        
        # 构建查询条件
        query = {}
        if last_backup_time:
            query['last_modified'] = {'$gt': last_backup_time}

        try:
            # 获取需要备份的文档
            documents = list(source_collection.find(query))
            
            if not documents:
                logging.info(f"No new or updated documents in collection {collection_name}")
                return
            
            # 批量更新文档
            for doc in documents:
                backup_collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": doc},
                    upsert=True
                )
            
            # 更新备份时间
            self.update_backup_time(collection_name)
            logging.info(f"Backed up {len(documents)} documents in collection: {collection_name}")
            
        except Exception as e:
            logging.error(f"Error backing up collection {collection_name}: {e}")

    def backup_all(self):
        try:
            collections = self.source_db.list_collection_names()
            logging.info(f"Starting backup for collections: {collections}")

            for collection_name in collections:
                self.backup_collection(collection_name)

            logging.info("Backup completed successfully!")

        except Exception as e:
            logging.error(f"Error during backup: {e}")
        finally:
            self.source_client.close()
            self.backup_client.close()

def main():
    backup = MongoBackup()
    backup.backup_all()

if __name__ == '__main__':
    main()