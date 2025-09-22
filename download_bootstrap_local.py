#!/usr/bin/env python3

import os
import requests
from pathlib import Path
import re

def download_file(url, local_path, is_binary=False):
    """下载文件到本地路径"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # 确保目录存在
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        if is_binary:
            # 字体文件使用二进制模式
            with open(local_path, 'wb') as f:
                f.write(response.content)
        else:
            # CSS和JS文件使用文本模式
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
        
        print(f"成功下载: {url} -> {local_path}")
        return True
    except Exception as e:
        print(f"下载失败 {url}: {e}")
        return False

def fix_bootstrap_icons_css(css_path):
    """修复bootstrap-icons.css中的字体路径"""
    try:
        with open(css_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 替换字体路径为本地路径
        content = re.sub(
            r'url\("\.\/fonts\/bootstrap-icons\.woff2\?[^"]*"\)',
            'url("../fonts/bootstrap-icons.woff2")',
            content
        )
        content = re.sub(
            r'url\("\.\/fonts\/bootstrap-icons\.woff\?[^"]*"\)',
            'url("../fonts/bootstrap-icons.woff")',
            content
        )
        
        with open(css_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"已修复字体路径: {css_path}")
        return True
    except Exception as e:
        print(f"修复字体路径失败: {e}")
        return False

def main():
    """主函数：下载Bootstrap文件到本地"""
    base_dir = Path(__file__).parent
    static_css_dir = base_dir / "web" / "static" / "css"
    static_js_dir = base_dir / "web" / "static" / "js"
    static_font_dir = base_dir / "web" / "static" / "fonts"
    
    # 要下载的文件列表
    files_to_download = [
        {
            "url": "https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css",
            "local_path": static_css_dir / "bootstrap.min.css",
            "is_binary": False
        },
        {
            "url": "https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js",
            "local_path": static_js_dir / "bootstrap.bundle.min.js",
            "is_binary": False
        },
        {
            "url": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/bootstrap-icons.css",
            "local_path": static_css_dir / "bootstrap-icons.css",
            "is_binary": False
        },
        {
            "url": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/fonts/bootstrap-icons.woff",
            "local_path": static_font_dir / "bootstrap-icons.woff",
            "is_binary": True
        },
        {
            "url": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/fonts/bootstrap-icons.woff2",
            "local_path": static_font_dir / "bootstrap-icons.woff2",
            "is_binary": True
        }
    ]
    
    success_count = 0
    total_count = len(files_to_download)
    
    print(f"开始下载 {total_count} 个Bootstrap文件...")
    
    for file_info in files_to_download:
        print(f"正在下载: {file_info['url']}")
        if download_file(file_info["url"], file_info["local_path"], file_info["is_binary"]):
            success_count += 1
        else:
            print(f"下载失败: {file_info['url']}")
    
    # 修复bootstrap-icons.css中的字体路径
    if (static_css_dir / "bootstrap-icons.css").exists():
        fix_bootstrap_icons_css(static_css_dir / "bootstrap-icons.css")
    
    print(f"\n下载完成: {success_count}/{total_count} 个文件成功")
    
    if success_count == total_count:
        print("所有Bootstrap文件下载成功！")
        print("\n接下来需要更新模板文件中的引用路径...")
        return True
    else:
        print("部分文件下载失败！")
        return False

if __name__ == "__main__":
    main()