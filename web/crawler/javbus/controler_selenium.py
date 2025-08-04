#!/usr/bin/env python
#-*-coding:utf-8-*-

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
from dotenv import load_dotenv
from urllib.parse import urljoin
import requests
import json
import re
from bs4 import BeautifulSoup

# 加载环境变量
load_dotenv('/root/backup_sehuatang/copy.env')

# MongoDB 配置
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://192.168.100.227:38234/')
MONGO_DB = os.getenv('MONGO_DB', 'javbus_crawler')
# 大模型API配置
llm_api_url = os.getenv('LLM_API_URL', 'https://open.bigmodel.cn/api/paas/v4/chat/completions')
llm_api_key = os.getenv('LLM_API_KEY', '')
llm_model = os.getenv('LLM_MODEL', 'glm-4.5-flash')

# 全局 MongoDB 客户端
_mongo_client = None
_mongo_db = None

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 在 SeleniumControler 类中添加大模型处理方法
class SeleniumControler:
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
            
            logger.info("Selenium WebDriver初始化成功")
            
        except Exception as e:
            logger.error(f"Selenium WebDriver初始化失败: {e}")
            self.driver = None
    
    def get_page_content(self, url, max_retries=None):
        """使用Selenium获取页面内容，支持重试机制"""
        if not self.driver:
            logger.error("WebDriver未初始化")
            return None
        
        if max_retries is None:
            max_retries = self.max_retries
            
        for attempt in range(max_retries):
            try:
                # 随机延时，避免被检测
                if attempt > 0:
                    wait_time = (attempt + 1) * 5 + random.uniform(2, 5)
                    logger.info(f"第{attempt + 1}次重试，等待{wait_time:.1f}秒...")
                    time.sleep(wait_time)
                
                logger.info(f"正在访问: {url}")
                
                # 设置页面加载超时
                self.driver.set_page_load_timeout(self.page_load_timeout)
                
                self.driver.get(url)
                
                # 等待页面加载完成
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # 检查是否遇到验证页面
                page_source = self.driver.page_source
                 
                if '验证您是否是真人' in page_source or 'security check' in page_source.lower():
                    logger.warning(f"遇到安全验证页面: {url}")
                    if attempt < max_retries - 1:
                        time.sleep(random.uniform(10, 20))
                        continue
                
                # 模拟人类行为
                while(self.simulate_human_behavior()):
                    print(self.driver.page_source) 
                    # 添加延时
                    time.sleep(self.delay)
                
                
                return self.driver.page_source
                
            except TimeoutException:
                logger.error(f"页面加载超时: {url} (尝试{attempt + 1}/{max_retries})")
            except WebDriverException as e:
                if "ERR_CONNECTION_REFUSED" in str(e):
                    logger.error(f"连接被拒绝: {url} (尝试{attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        logger.info("可能是网络问题或反爬虫机制，等待更长时间后重试...")
                        time.sleep(random.uniform(30, 60))
                        continue
                else:
                    logger.error(f"WebDriver异常: {url} (尝试{attempt + 1}/{max_retries}): {e}")
            except Exception as e:
                logger.error(f"获取页面失败: {url} (尝试{attempt + 1}/{max_retries}): {e}")
                
            if attempt == max_retries - 1:
                return None
                
        return None
    
    
    
    def call_llm_for_driving_test(self, questions_html):
        """使用大模型分析驾驶证考试题并返回答案"""
        try:
            # 构造提示词 
            prompt = f"""
    你是一个专业的驾驶证考试专家。请分析以下HTML中的驾驶证考试题，并为每道题选择正确答案。
    
    请按照以下格式返回答案：
    {{
        "userAnswers[题目编号]": "正确选项字母",
        "userAnswers[题目编号]": "正确选项字母"
    }}
    
    注意：
    1. 只返回JSON格式的答案，不要其他解释
    2. 选项字母必须是A、B、C、D中的一个
    3. 题目编号从HTML的name属性中提取
    
    HTML内容：
    {questions_html}
    """
        
            # 调用大模型API
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {llm_api_key}"
            }
            
            data = {
                "model": llm_model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.1,  # 降低温度以获得更稳定的答案
                "top_p": 0.8
            }
            
            response = requests.post(
                 llm_api_url,
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # 尝试解析JSON答案
                try:
                    # 提取JSON部分
                    json_match = re.search(r'\{[^}]+\}', content)
                    if json_match:
                        answers_json = json_match.group()
                        answers = json.loads(answers_json)
                        logger.info(f"大模型返回答案: {answers}")
                        return answers
                    else:
                        logger.warning("大模型返回内容中未找到有效JSON")
                        return None
                except json.JSONDecodeError as e:
                    logger.warning(f"解析大模型返回的JSON失败: {e}")
                    return None
            else:
                logger.error(f"大模型API调用失败: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"调用大模型处理驾驶证考试题失败: {e}")
            return None
    
    def extract_questions_from_page(self):
        """从页面中提取考试题内容，格式化为适合大模型处理的字符串"""
        try:
            # 获取页面HTML
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # 查找包含题目的表单
            form = soup.find('form')
            if not form:
                logger.warning("未找到包含题目的表单")
                return None
            
            # 提取所有题目
            questions = []
            question_items = form.find_all('li')
            
            for item in question_items:
                label = item.find('label')
                if not label:
                    continue
                    
                # 提取问题文本（第一个文本节点，去掉<br>标签）
                question_text = ""
                for content in label.contents:
                    if hasattr(content, 'name') and content.name == 'br':
                        break
                    if hasattr(content, 'strip'):
                        question_text += content.strip()
                
                if not question_text:
                    continue
                
                # 提取选项
                options = []
                radio_inputs = item.find_all('input', {'type': 'radio'})
                
                for radio in radio_inputs:
                    # 获取选项的name属性（包含题目编号）
                    name_attr = radio.get('name', '')
                    value_attr = radio.get('value', '')
                    
                    # 获取选项文本（radio后面的文本）
                    option_text = ""
                    next_sibling = radio.next_sibling
                    if next_sibling and hasattr(next_sibling, 'strip'):
                        option_text = next_sibling.strip()
                        # 移除开头的选项字母和点号
                        if option_text.startswith(f"{value_attr}."):
                            option_text = option_text[2:].strip()
                    
                    if option_text:
                        options.append({
                            'value': value_attr,
                            'text': option_text,
                            'name': name_attr
                        })
                
                if options:
                    # 从第一个选项的name属性中提取题目编号
                    question_id = ""
                    if options[0]['name']:
                        import re
                        match = re.search(r'userAnswers\[(\d+)\]', options[0]['name'])
                        if match:
                            question_id = match.group(1)
                    
                    questions.append({
                        'id': question_id,
                        'question': question_text,
                        'options': options
                    })
            
            if not questions:
                logger.warning("未找到有效的考试题目")
                return None
            
            # 格式化为适合大模型处理的字符串
            formatted_questions = self.format_questions_for_llm(questions)
            return formatted_questions
                
        except Exception as e:
            logger.error(f"提取页面题目失败: {e}")
            return None
    
    def format_questions_for_llm(self, questions):
        """将提取的题目格式化为适合大模型处理的字符串"""
        formatted_text = "驾驶证考试题目：\n\n"
        
        for i, q in enumerate(questions, 1):
            formatted_text += f"题目{i}（编号：{q['id']}）：\n"
            formatted_text += f"问题：{q['question']}\n"
            formatted_text += "选项：\n"
            
            for option in q['options']:
                formatted_text += f"  {option['value']}. {option['text']}\n"
            
            formatted_text += "\n"
        
        formatted_text += "请为每道题选择正确答案，返回格式如下：\n"
        formatted_text += "{\n"
        for q in questions:
            formatted_text += f'  "userAnswers[{q["id"]}]": "正确选项字母",\n'
        formatted_text += "}"
        
        return formatted_text
    
    def simulate_human_behavior(self):
        """模拟人类浏览行为"""
        try:
            # 检查是否遇到年龄确认页面
            page_source = self.driver.page_source
            
            # 检测多种年龄验证页面模式
            age_verification_patterns = [
                '满18岁，请点此进入',
                'If you are over 18，please click here',
                '你是否已经成年',
                'Age Verification',
                '我已经成年',
                '我已經成年'
            ]
            
            # 检测驾驶证考试题验证页面
            driving_test_patterns = [
                '所在地區年齡檢測',
                '你必須通過年齡測驗',
                '实习期内驾驶人驾驶机动车',
                '初次申领机动车驾驶证',
                '机动车驾驶人逾期不参加审验',
                '隐瞒有关情况或提供虚假材料申请机动车驾驶证',
                'driver-verify.php',
                'userAnswers['
            ]
            
            has_age_verification = any(pattern in page_source for pattern in age_verification_patterns)
            has_driving_test = any(pattern in page_source for pattern in driving_test_patterns)
            
            # 处理驾驶证考试题验证（使用大模型）
            if has_driving_test:
                logger.info("检测到驾驶证考试题验证页面，正在使用大模型处理...")
                
                try:
                    # 提取页面题目
                    questions_html = self.extract_questions_from_page()
                    print("-------------------============")
                    print(questions_html)
                    print("---#########-----============")
                    if not questions_html:
                        logger.warning("无法提取页面题目，使用备用答案")
                        # 使用预设的备用答案
                        correct_answers = {
                            'userAnswers[19]': 'C',
                            'userAnswers[7]': 'A',
                            'userAnswers[2]': 'A',
                            'userAnswers[3]': 'B',
                            'userAnswers[14]': 'B'
                        }
                    else:
                        # 使用大模型分析题目

 
                        correct_answers = self.call_llm_for_driving_test(questions_html)
                        
                        # 如果大模型调用失败，使用备用答案
                        if not correct_answers:
                            logger.warning("大模型调用失败，使用备用答案")
                            correct_answers = {
                                'userAnswers[19]': 'C',
                                'userAnswers[7]': 'A',
                                'userAnswers[2]': 'A',
                                'userAnswers[3]': 'B',
                                'userAnswers[14]': 'B'
                            }
                    
                    # 选择答案
                    for question_name, correct_value in correct_answers.items():
                        try:
                            # 构造选择器
                            radio_selector = f"input[name='{question_name}'][value='{correct_value}']"
                            radio_button = WebDriverWait(self.driver, 5).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, radio_selector))
                            )
                            
                            # 点击正确答案
                            if not radio_button.is_selected():
                                radio_button.click()
                                logger.info(f"已选择题目 {question_name} 的答案: {correct_value}")
                                time.sleep(random.uniform(0.5, 1.5))
                                
                        except Exception as e:
                            logger.warning(f"选择题目 {question_name} 失败: {e}")
                            continue
                    
                    # 提交答案
                    submit_selectors = [
                        "button[type='submit'][name='submit'][value='question']",
                        "button.submit.btn.btn-success",
                        "input[type='submit'][name='submit']",
                        "button[type='submit']"
                    ]
                    
                    submit_clicked = False
                    for selector in submit_selectors:
                        try:
                            submit_btn = WebDriverWait(self.driver, 5).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                            submit_btn.click()
                            logger.info(f"已提交驾驶证考试题答案: {selector}")
                            submit_clicked = True
                            break
                        except Exception:
                            continue
                    
                    if submit_clicked:
                        # 等待页面跳转
                        time.sleep(random.uniform(3, 6))
                        logger.info("驾驶证考试题验证处理完成")
                        return True
                    else:
                        logger.warning("未能找到提交按钮")
                        
                except Exception as e:
                    logger.warning(f"处理驾驶证考试题验证失败: {e}")
                    
                    # 备用方案：使用JavaScript和预设答案
                    try:
                        backup_answers = {
                            'userAnswers[19]': 'C',
                            'userAnswers[7]': 'A',
                            'userAnswers[2]': 'A',
                            'userAnswers[3]': 'B',
                            'userAnswers[14]': 'B'
                        }
                        
                        # 使用JavaScript选择答案并提交
                        js_script = f"""
                        var answers = {json.dumps(backup_answers)};
                        
                        for (var questionName in answers) {{
                            var correctValue = answers[questionName];
                            var radio = document.querySelector('input[name="' + questionName + '"][value="' + correctValue + '"]');
                            if (radio && !radio.checked) {{
                                radio.checked = true;
                                radio.dispatchEvent(new Event('change'));
                            }}
                        }}
                        
                        setTimeout(function() {{
                            var submitBtn = document.querySelector('button[type="submit"][name="submit"][value="question"]');
                            if (submitBtn) {{
                                submitBtn.click();
                            }} else {{
                                var form = document.querySelector('form');
                                if (form) {{
                                    form.submit();
                                }}
                            }}
                        }}, 1000);
                        """
                        
                        self.driver.execute_script(js_script)
                        logger.info("使用JavaScript备用方案处理驾驶证考试题")
                        time.sleep(random.uniform(4, 7))
                        return True
                        
                    except Exception as js_e:
                        logger.warning(f"JavaScript备用方案也失败: {js_e}")
            
            # 处理普通年龄验证页面（原有逻辑）
            elif has_age_verification:
                logger.info("检测到年龄确认页面，正在处理...")
                
                try:
                    # 方法1: 处理模态框形式的年龄验证（如 hint.html 中的形式）
                    # 先尝试找到并勾选复选框
                    checkbox_selectors = [
                        "input[type='checkbox']",
                        "#ageVerify input[type='checkbox']",
                        ".modal input[type='checkbox']"
                    ]
                    
                    checkbox_found = False
                    for selector in checkbox_selectors:
                        try:
                            checkbox = WebDriverWait(self.driver, 3).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                            if not checkbox.is_selected():
                                checkbox.click()
                                logger.info(f"已勾选年龄确认复选框: {selector}")
                                checkbox_found = True
                                time.sleep(random.uniform(0.5, 1.5))
                                break
                        except Exception:
                            continue
                    
                    # 然后尝试点击确认按钮
                    submit_selectors = [
                        "#submit",
                        "input[type='submit']",
                        "button[type='submit']",
                        ".submit",
                        "input[value='確認']",
                        "input[value='確認']",
                        "button:contains('確認')",
                        "button:contains('確認')",
                        ".btn-success"
                    ]
                    
                    submit_clicked = False
                    for selector in submit_selectors:
                        try:
                            submit_btn = WebDriverWait(self.driver, 3).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                            submit_btn.click()
                            logger.info(f"已点击年龄确认提交按钮: {selector}")
                            submit_clicked = True
                            break
                        except Exception:
                            continue
                    
                    # 方法2: 处理简单链接形式的年龄验证
                    if not submit_clicked:
                        link_selectors = [
                            ".enter-btn",
                            "a:contains('进入')",
                            "a:contains('確認')",
                            "a:contains('Enter')"
                        ]
                        
                        for selector in link_selectors:
                            try:
                                enter_link = WebDriverWait(self.driver, 3).until(
                                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                                )
                                enter_link.click()
                                logger.info(f"已点击年龄确认链接: {selector}")
                                submit_clicked = True
                                break
                            except Exception:
                                continue
                    
                    if checkbox_found or submit_clicked:
                        # 等待页面跳转
                        time.sleep(random.uniform(2, 5))
                        logger.info("年龄验证处理完成")
                        return True
                    else:
                        logger.warning("未能找到有效的年龄验证元素")
                        
                except Exception as e:
                    logger.warning(f"处理年龄确认页面失败: {e}")
                    
                    # 备用方案：尝试使用 JavaScript 直接提交表单
                    try:
                        # 勾选复选框
                        self.driver.execute_script("""
                            var checkboxes = document.querySelectorAll('input[type="checkbox"]');
                            for (var i = 0; i < checkboxes.length; i++) {
                                if (!checkboxes[i].checked) {
                                    checkboxes[i].checked = true;
                                    checkboxes[i].dispatchEvent(new Event('change'));
                                }
                            }
                        """)
                        
                        time.sleep(1)
                        
                        # 启用并点击提交按钮
                        self.driver.execute_script("""
                            var submitBtn = document.getElementById('submit');
                            if (submitBtn) {
                                submitBtn.disabled = false;
                                submitBtn.click();
                            } else {
                                var forms = document.querySelectorAll('form');
                                if (forms.length > 0) {
                                    forms[0].submit();
                                }
                            }
                        """)
                        
                        logger.info("使用 JavaScript 备用方案处理年龄验证")
                        time.sleep(random.uniform(2, 4))
                        return True
                        
                    except Exception as js_e:
                        logger.warning(f"JavaScript 备用方案也失败: {js_e}")
            
            # 随机滚动页面（原有逻辑）
            try:
                scroll_height = self.driver.execute_script("return document.body.scrollHeight")
                scroll_position = random.randint(0, min(scroll_height, 1000))
                self.driver.execute_script(f"window.scrollTo(0, {scroll_position});")
                
                # 随机停留时间
                time.sleep(random.uniform(1, 3))
            except Exception as e:
                logger.debug(f"页面滚动失败: {e}")
                
        except Exception as e:
            logger.debug(f"模拟人类行为失败: {e}")
        return False
    
    def close_driver(self):
        """关闭 WebDriver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("Selenium WebDriver已关闭")

# MongoDB 连接函数
def get_mongo_connection():
    """获取 MongoDB 连接"""
    global _mongo_client, _mongo_db
    if _mongo_client is None:
        _mongo_client = MongoClient(MONGO_URI)
        _mongo_db = _mongo_client[MONGO_DB]
    return _mongo_db

def create_db():
    """创建数据库和集合索引（如果不存在）"""
    try:
        db = get_mongo_connection()
        collection = db.javbus_data
        
        # 创建索引以提高查询性能
        collection.create_index("URL", unique=True)
        collection.create_index("識別碼")
        collection.create_index("標題")
        
        print("MongoDB collection and indexes created successfully")
        return True
    except Exception as e:
        print(f"Error creating MongoDB collection: {e}")
        return False

def write_data(dict_jav):
    """写入数据到 MongoDB"""
    try:
        db = get_mongo_connection()
        collection = db.javbus_data
        
        # 准备文档数据
        document = {
            'URL': dict_jav.get('URL', ''),
            '識別碼': dict_jav.get('識別碼', ''),
            '標題': dict_jav.get('標題', ''),
            '封面': dict_jav.get('封面', ''),
            '樣品圖像': dict_jav.get('樣品圖像', ''),
            '發行日期': dict_jav.get('發行日期', ''),
            '長度': dict_jav.get('長度', ''),
            '導演': dict_jav.get('導演', ''),
            '製作商': dict_jav.get('製作商', ''),
            '發行商': dict_jav.get('發行商', ''),
            '系列': dict_jav.get('系列', ''),
            '演員': dict_jav.get('演員', ''),
            '類別': dict_jav.get('類別', ''),
            '磁力链接': dict_jav.get('磁力链接', ''),
            '無碼': dict_jav.get('無碼', 0)
        }
        
        # 使用 upsert 操作，如果 URL 已存在则更新，否则插入
        result = collection.update_one(
            {'URL': document['URL']},
            {'$set': document},
            upsert=True
        )
        
        if result.upserted_id:
            print(f"Inserted new document with URL: {document['URL']}")
        elif result.modified_count > 0:
            print(f"Updated existing document with URL: {document['URL']}")
            
        return True
        
    except Exception as e:
        print(f"Error writing data to MongoDB: {e}")
        return False

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
            'local_image_path': local_image_path or actress_info.get('local_image_path', '')
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

# Selenium 版本的特殊功能
def get_html_with_selenium(url, headless=True, delay=3):
    """使用 Selenium 获取 HTML 内容"""
    controller = SeleniumControler(headless=headless, delay=delay)
    try:
        html_content = controller.get_page_content(url)
        return html_content
    finally:
        controller.close_driver()

def parse_html_with_selenium(url, parser_func, headless=True, delay=3):
    """使用 Selenium 获取页面并用自定义解析函数处理"""
    controller = SeleniumControler(headless=headless, delay=delay)
    try:
        html_content = controller.get_page_content(url)
        if html_content:
            soup = BeautifulSoup(html_content, 'html.parser')
            return parser_func(soup)
        return None
    finally:
        controller.close_driver()

# 在程序退出时自动关闭连接
import atexit
atexit.register(close_connection)

# 使用示例
if __name__ == "__main__":
    # 测试 Selenium 控制器
    controller = SeleniumControler(headless=True, delay=3)
    try:
        # 测试获取页面内容
        html = controller.get_page_content("https://www.javbus.com")
        if html:
            print("成功获取页面内容")
            print(f"页面长度: {len(html)} 字符")
        else:
            print("获取页面内容失败")
    finally:
        controller.close_driver()