#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网站爬虫脚本 - Selenium版本
功能：从首页获取详情页链接，然后提取每个详情页的标题和磁力链接
"""

import sys
import os
import re
import time 
import random

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from urllib.parse import urljoin

# 添加父目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import db_manager
import app_logger

# 修改类名和继承 - 添加当前目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
from selenium_base import BaseSeleniumController

class ForumSeleniumCrawler(BaseSeleniumController):
    """专门用于论坛爬虫的 Selenium 控制器"""
     
    def __init__(self, headless=True, delay=3):
        super().__init__(headless, delay)
        self.base_url = "https://sehuatang.org/forum.php?mod=forumdisplay&fid=103&filter=typeid&typeid=480"

    
    def extract_tid_id(self, url):
        """从URL中提取thread ID"""
        # 支持新格式: tid=数字
        match = re.search(r'tid=(\d+)', url)
        if match:
            return match.group(1)
        
        # 支持旧格式: tid-数字-
        match = re.search(r'tid-(\d+)-', url)
        return match.group(1) if match else None

 
    def get_page_content(self, url, max_retries=3):
        """使用Selenium获取页面内容，支持重试机制"""
        if not self.driver:
            app_logger.error("WebDriver未初始化")
            return None
            
        for attempt in range(max_retries):
            try:
                # 随机延时，避免被检测
                if attempt > 0:
                    wait_time = (attempt + 1) * 5 + random.uniform(2, 5)  # 增加等待时间
                    app_logger.info(f"第{attempt + 1}次重试，等待{wait_time:.1f}秒...")
                    time.sleep(wait_time)
                
                app_logger.info(f"正在访问: {url}")
                
                # 设置页面加载超时
                self.driver.set_page_load_timeout(60)  # 增加超时时间
                
                self.driver.get(url)
                
                # 等待页面加载完成
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # 检查是否遇到验证页面
                page_source = self.driver.page_source
                if '验证您是否是真人' in page_source or 'security check' in page_source.lower():
                    app_logger.warning(f"遇到安全验证页面: {url}")
                    if attempt < max_retries - 1:
                        # 尝试等待更长时间
                        time.sleep(random.uniform(10, 20))
                        continue
                
                # 模拟人类行为，如果处理了年龄确认页面，重新获取页面源码
                handled_age_check = self.simulate_human_behavior()
                if handled_age_check:
                    # 重新获取页面源码
                    page_source = self.driver.page_source 
                    app_logger.info("已获取年龄确认后的新页面数据")
                
                return page_source
                
            except TimeoutException:
                app_logger.error(f"页面加载超时: {url} (尝试{attempt + 1}/{max_retries})")
            except WebDriverException as e:
                if "ERR_CONNECTION_REFUSED" in str(e):
                    app_logger.error(f"连接被拒绝: {url} (尝试{attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        app_logger.info("可能是网络问题或反爬虫机制，等待更长时间后重试...")
                        time.sleep(random.uniform(30, 60))  # 等待30-60秒
                        continue
                else:
                    app_logger.error(f"WebDriver异常: {url} (尝试{attempt + 1}/{max_retries}): {e}")
            except Exception as e:
                app_logger.error(f"获取页面失败: {url} (尝试{attempt + 1}/{max_retries}): {e}")
                
            if attempt == max_retries - 1:
                return None
                
        return None
    
    def simulate_human_behavior(self):
        """模拟人类浏览行为"""
        try:
            # 检查是否遇到年龄确认页面
            page_source = self.driver.page_source
            if '满18岁，请点此进入' in page_source or 'If you are over 18，please click here' in page_source:
                app_logger.info("检测到年龄确认页面，正在点击确认按钮...")
                try:
                    # 尝试点击年龄确认按钮
                    enter_btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CLASS_NAME, "enter-btn"))
                    )
                    enter_btn.click()
                    app_logger.info("已点击年龄确认按钮")
                    
                    # 等待页面跳转
                    time.sleep(random.uniform(2, 4))
                    return True
                except Exception as e:
                    app_logger.warning(f"点击年龄确认按钮失败: {e}")
            
            # 随机滚动页面
            scroll_height = self.driver.execute_script("return document.body.scrollHeight")
            scroll_position = random.randint(0, min(scroll_height, 1000))
            self.driver.execute_script(f"window.scrollTo(0, {scroll_position});")
            
            # 随机停留时间
            time.sleep(random.uniform(1, 3))
            
        except Exception as e:
            app_logger.debug(f"模拟人类行为失败: {e}")
        return False
    
    def extract_thread_links_from_html(self, html_content):

        """从HTML内容中提取详情页链接"""
        thread_links = []
        # 使用正则表达式匹配 thread-数字-1-1.html 格式的链接
        pattern1 = r'<em>\[.*?\]</em>\s*<a href="(forum\.php\?mod=viewthread&amp;tid=(\d+)[^"]*)"[^>]*class="s xst"[^>]*>'
        matches = re.findall(pattern1, html_content)
        print(f"最精确匹配（em后的标题链接）: 找到 {len(matches)} 个链接")
        processed_links = []
        for match in matches:
            link = match[0].replace('&amp;', '&')
            tid = self.extract_tid_id(link)
            if db_manager.is_sehuatang_detail_craled(tid):
               app_logger.info(f"跳过已存在的记录: tid={tid}")
               continue  # 跳过已存在的记录 
                    
 
            processed_links.append(link)
        print(f"处理后的链接: {processed_links}")

        for match in processed_links:
            full_url = urljoin(self.base_url, match)
            thread_links.append(full_url)
        
        # 去重
        thread_links = list(set(thread_links))
        app_logger.info(f"找到 {len(thread_links)} 个详情页链接")
        return thread_links
    
    def extract_thread_links_from_file(self, file_path):
        """从本地HTML文件中提取详情页链接"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            return self.extract_thread_links_from_html(html_content)
        except Exception as e:
            app_logger.error(f"读取文件失败 {file_path}: {e}")
            return []
    
    def extract_title_and_magnet(self, html_content):
        """从详情页HTML中提取标题和磁力链接"""
        title = None
        magnet_links = []
        
        # 提取标题
        title_pattern = r'<span id="thread_subject">([^<]+)</span>'
        title_match = re.search(title_pattern, html_content)
        if title_match:
            title = title_match.group(1).strip()
        
        # 提取磁力链接
        magnet_pattern = r'magnet:\?xt=urn:btih:[A-F0-9]+[^\s<>"]*'
        magnet_matches = re.findall(magnet_pattern, html_content, re.IGNORECASE)
        
        # 清理磁力链接中的HTML实体
        for magnet in magnet_matches:
            clean_magnet = magnet.replace('&amp;', '&')
            magnet_links.append(clean_magnet)
        if len(magnet_links) == 0:
             return title,''
        return title, magnet_links[0]
 
    
    def crawl_thread_details(self, thread_url):
        """爬取单个详情页的信息"""
        app_logger.info(f"正在爬取: {thread_url}")
        
        html_content = self.get_page_content(thread_url)
        if not html_content:
            return None
        
        title, magnet_link = self.extract_title_and_magnet(html_content)
        
        if title or magnet_link:
            data = {
                'url': thread_url,
                'title': title,
                'magnet_link': magnet_link,
                'tid':self.extract_tid_id(thread_url),
 
            }
            # 保存到MongoDB
            db_manager.save_sehuatang_detail_db(data)
            
            return data
        
        return None
    
     
    
    def crawl_from_url(self, home_url):
        """从网络URL开始爬取"""
        app_logger.info(f"开始从URL爬取: {home_url}")
   
        
        # 获取首页内容
        html_content = self.get_page_content(home_url)
        if not html_content:
            app_logger.error("无法获取首页内容")
            return
        
        # 提取详情页链接
        thread_links = self.extract_thread_links_from_html(html_content)
        
        if not thread_links:
            app_logger.warning("未找到任何详情页链接："+home_url)
            return
        
        results = []
        
        # 爬取每个详情页
        for i, thread_url in enumerate(thread_links, 1):
            app_logger.info(f"进度: {i}/{len(thread_links)}")
            
            result = self.crawl_thread_details(thread_url)
            if result:
                results.append(result)
                app_logger.info(f"成功提取: {result['title']}")
            
            # 随机延时避免过于频繁的请求
            if i < len(thread_links):
                delay_time = self.delay + random.uniform(-2, 2)
                time.sleep(max(1, delay_time))
        
        app_logger.info(f"爬取完成，共获取 {len(results)} 条有效数据")
        app_logger.info(f"数据已保存到MongoDB")
        
        return results
    
  
     

    def update_subscription(self):
         crawler = ForumSeleniumCrawler()  
         pageNumbers = 50
         for pageNumber in range(1, pageNumbers + 1):
            url = f"{crawler.base_url}&page={pageNumber}"
            results = crawler.crawl_from_url(url)
            if results:
                print(f"\n第 {pageNumber} 页爬取完成，共获取 {len(results)} 条数据")
         app_logger.info(f"完成全部爬取")
    
    def update_sehuatang(self, pageNumbers=50):
        headless = True
        crawler = ForumSeleniumCrawler(delay=3, headless=headless)  # 设置3秒延时
        
        try: 
            for pageNumber in range(0, pageNumbers + 1):
                url = f"{crawler.base_url}&page={pageNumber}"
                results = crawler.crawl_from_url(url)
                if results:
                    print(f"\n第 {pageNumber} 页爬取完成，共获取 {len(results)} 条数据")
            app_logger.info(f"完成全部爬取")
    
        finally:
            # 确保关闭所有连接
            crawler.close_driver()
def main():
    """主函数"""
 
    headless = True
    crawler = ForumSeleniumCrawler(delay=3, headless=headless)  # 设置3秒延时
    
    try: 
        pageNumbers = 100
        for pageNumber in range(0, pageNumbers + 1):
            url = f"{crawler.base_url}&page={pageNumber}"
            results = crawler.crawl_from_url(url)
            if results:
                print(f"\n第 {pageNumber} 页爬取完成，共获取 {len(results)} 条数据")
        app_logger.info(f"完成全部爬取")
    
    finally:
        # 确保关闭所有连接
        crawler.close_driver()


if __name__ == "__main__":
    main()
