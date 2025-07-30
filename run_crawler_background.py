#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
后台运行爬虫脚本 - 非交互版本
"""

import sys
import os
from selenium_crawler import SeleniumWebCrawler
import logging

def run_background_crawler():
    """后台运行爬虫"""
    # 使用无头模式
    crawler = SeleniumWebCrawler(delay=3, headless=True)
    
    try:
        # 默认从在线论坛爬取
        print(f"开始后台爬取: {crawler.default_forum_url}")
        logging.info("开始后台爬取任务")
        
        pageNumbers = 1117
        for pageNumber in range(140, pageNumbers + 1):
            url = f"{crawler.default_forum_url}&page={pageNumber}"
            results = crawler.crawl_from_url(url)
            if results:
                logging.info(f"第 {pageNumber} 页爬取完成，共获取 {len(results)} 条数据")
                print(f"第 {pageNumber} 页完成")
        
        logging.info("完成全部爬取任务")
        print("爬取任务完成")
        
    except Exception as e:
        logging.error(f"爬取过程中出现错误: {e}")
        print(f"错误: {e}")
    finally:
        # 确保关闭所有连接
        crawler.close_connection()
        logging.info("爬虫连接已关闭")

if __name__ == "__main__":
    run_background_crawler()