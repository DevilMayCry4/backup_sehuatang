import os
import hashlib
import json
from datetime import datetime

class StaticVersionManager:
    def __init__(self, static_folder):
        self.static_folder = static_folder
        self.version_file = os.path.join(static_folder, 'versions.json')
        self.versions = self.load_versions()
    
    def load_versions(self):
        """加载版本信息"""
        if os.path.exists(self.version_file):
            with open(self.version_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_versions(self):
        """保存版本信息"""
        with open(self.version_file, 'w') as f:
            json.dump(self.versions, f, indent=2)
    
    def get_file_hash(self, filepath):
        """获取文件哈希值"""
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    
    def get_versioned_url(self, filename):
        """获取带版本号的URL"""
        filepath = os.path.join(self.static_folder, filename)
        if os.path.exists(filepath):
            file_hash = self.get_file_hash(filepath)
            return f"/static/{filename}?v={file_hash}"
        return f"/static/{filename}"
    
    def update_versions(self):
        """更新所有文件版本"""
        for root, dirs, files in os.walk(self.static_folder):
            for file in files:
                if file.endswith(('.css', '.js', '.png', '.jpg', '.jpeg', '.gif')):
                    filepath = os.path.join(root, file)
                    rel_path = os.path.relpath(filepath, self.static_folder)
                    self.versions[rel_path] = {
                        'hash': self.get_file_hash(filepath),
                        'updated': datetime.now().isoformat()
                    }
        self.save_versions()

# 在app.py中使用
version_manager = StaticVersionManager(app.static_folder)

# 添加模板函数
@app.template_global()
def versioned_url(filename):
    return version_manager.get_versioned_url(filename)