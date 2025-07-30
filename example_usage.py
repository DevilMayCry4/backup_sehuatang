#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jellyfin电影检查器使用示例
"""

from jellyfin_movie_checker import JellyfinMovieChecker
from jellyfin_config import config
 

def main():
    
    # 创建检查器
    checker = JellyfinMovieChecker( 
    )
    
    # 示例：检查多部电影
    movies_to_check = [
        "阿凡达",
        "泰坦尼克号",
        "复仇者联盟",
        "不存在的电影"
    ]
    
    results = []
    for movie_name in movies_to_check:
        print(f"\n{'='*60}")
        result = checker.check_movie_exists(movie_name)
        results.append(result)
    
    # 汇总结果
    print(f"\n{'='*60}")
    print("📊 检查汇总:")
    found_count = sum(1 for r in results if r["exists"])
    print(f"✅ 找到: {found_count}/{len(results)} 部电影")
    
    for result in results:
        status = "✅" if result["exists"] else "❌"
        count_info = f" ({result['count']} 个结果)" if result["exists"] else ""
        print(f"  {status} {result['search_term']}{count_info}")

if __name__ == "__main__":
    main()