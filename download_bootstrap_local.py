#!/usr/bin/env python3

import os
import requests
from pathlib import Path

def download_file(url, local_path):
    """下载文件到本地路径"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # 确保目录存在
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        print(f"成功下载: {url} -> {local_path}")
        return True
    except Exception as e:
        print(f"下载失败 {url}: {e}")
        return False

def main():
    """主函数：下载Bootstrap CSS文件到本地"""
    base_dir = Path(__file__).parent
    static_css_dir = base_dir / "web" / "static" / "css"
    static_font_dir = base_dir / "web" / "static" / "font"
    
    # 要下载的文件列表
    files_to_download = [
        {
            "url": "https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css",
            "local_path": static_css_dir / "bootstrap.min.css"
        },
        {
            "url": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/bootstrap-icons.css",
            "local_path": static_font_dir / "bootstrap-icons.css"
        },{
            "url": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/fonts/bootstrap-icons.woff?30af91bf14e37666a085fb8a161ff36d.woff",
            "local_path": static_font_dir / "fonts/bootstrap-icons.woff2"
        },{
            "url": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/fonts/bootstrap-icons.woff2?30af91bf14e37666a085fb8a161ff36d.woff2",
            "local_path": static_font_dir / "fonts/bootstrap-icons.woff"
        }
    ]
    
    success_count = 0
    total_count = len(files_to_download)
    
    print(f"开始下载 {total_count} 个CSS文件...")
    print(f"目标目录: {static_css_dir}")
    
    for file_info in files_to_download:
        print(f"正在下载: {file_info['url']}")
        if download_file(file_info["url"], file_info["local_path"]):
            success_count += 1
        else:
            print(f"下载失败: {file_info['url']}")
    
    print(f"\n下载完成: {success_count}/{total_count} 个文件成功")
    
    if success_count == total_count:
        print("所有文件下载成功！")
        return True
    else:
        print("部分文件下载失败！")
        return False

if __name__ == "__main__":
    main()