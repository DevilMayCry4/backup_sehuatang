#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import random
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
from pymongo import MongoClient

class BaseSeleniumController:
    """基础 Selenium 控制器类"""
    
    def __init__(self, headless=True, delay=3):
        self.headless = headless
        self.delay = delay
        self.driver = None
        self.max_retries = 3
        self.page_load_timeout = 60
        self.implicit_wait = 15
        
        # 初始化 WebDriver
        self.init_webdriver()
    
    def init_webdriver(self):
        """初始化Selenium WebDriver"""
        try:
            chrome_options = Options()
            
            # 基本配置
            if self.headless:
                chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            
            # 网络相关配置
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-images')  # 禁用图片加载
            
            # 反检测配置
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # 用户代理
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
            selected_ua = random.choice(user_agents)
            chrome_options.add_argument(f'--user-agent={selected_ua}')
            
            # 禁用图片和CSS加载以提高速度
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.notifications": 2,
                "profile.managed_default_content_settings.stylesheets": 2
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # 执行反检测脚本
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # 设置页面加载超时
            self.driver.set_page_load_timeout(self.page_load_timeout)
            self.driver.implicitly_wait(self.implicit_wait)
            
            logging.info("WebDriver初始化成功")
            
        except Exception as e:
            logging.error(f"WebDriver初始化失败: {e}")
            raise
    
    def get_page_content(self, url, max_retries=None):
        """获取页面内容"""
        if max_retries is None:
            max_retries = self.max_retries
            
        for attempt in range(max_retries):
            try:
                logging.info(f"正在访问: {url} (尝试 {attempt + 1}/{max_retries})")
                self.driver.get(url)
                
                # 模拟人类行为
                self.simulate_human_behavior()
                
                # 等待页面加载
                time.sleep(self.delay)
                
                # 获取页面源码
                html_content = self.driver.page_source
                
                if html_content and len(html_content) > 100:
                    logging.info(f"成功获取页面内容，长度: {len(html_content)}")
                    return html_content
                else:
                    logging.warning(f"页面内容过短或为空: {len(html_content) if html_content else 0}")
                    
            except TimeoutException:
                logging.warning(f"页面加载超时: {url} (尝试 {attempt + 1}/{max_retries})")
            except WebDriverException as e:
                logging.warning(f"WebDriver错误: {e} (尝试 {attempt + 1}/{max_retries})")
            except Exception as e:
                logging.error(f"获取页面内容时出错: {e} (尝试 {attempt + 1}/{max_retries})")
            
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                logging.info(f"等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
        
        logging.error(f"获取页面内容失败，已尝试 {max_retries} 次: {url}")
        return None
    
    def init_mongodb(self):
        """初始化MongoDB连接"""
        try:
            self.mongo_client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
            # 测试连接
            self.mongo_client.admin.command('ping')
            self.db = self.mongo_client['sehuatang_crawler']
            self.collection = self.db['thread_details']
            logger.info(f"MongoDB连接成功: {self.mongo_uri}")
        except Exception as e:
            logger.error(f"MongoDB连接失败: {e}")
            self.mongo_client = None

    def simulate_human_behavior(self):
        """模拟人类浏览行为 - 基础版本"""
        # 基础的人类行为模拟
        time.sleep(random.uniform(0.5, 2.0))
    
    def close_driver(self):
        """关闭浏览器驱动"""
        if self.driver:
            try:
                self.driver.quit()
                logging.info("WebDriver已关闭")
            except Exception as e:
                logging.error(f"关闭WebDriver时出错: {e}")
            finally:
                self.driver = None