#!/usr/bin/env python
#-*-coding:utf-8-*-

import os
import sys
import time
import random
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
from dotenv import load_dotenv
from urllib.parse import urljoin
import requests
import json
import re
from bs4 import BeautifulSoup

# 添加上级目录到路径以导入 database 模块
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from database import db_manager
# 导入 MongoDB 操作模块
 # 在文件开头添加
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from selenium_base import BaseSeleniumController


# 加载环境变量
load_dotenv('/root/backup_sehuatang/copy.env')
 

# 大模型API配置
llm_api_url = os.getenv('LLM_API_URL', 'https://open.bigmodel.cn/api/paas/v4/chat/completions')
llm_api_key = os.getenv('LLM_API_KEY', '')
llm_model = os.getenv('LLM_MODEL', 'glm-4.5-flash')
jav_base_url = 'https://www.javbus.com'
 
logger = logging.getLogger(__name__)

class JavBusSeleniumController(BaseSeleniumController):
     
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
                
        return page_source
    
    
    
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
        """关闭浏览器驱动"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver已关闭")
            except Exception as e:
                logger.error(f"关闭WebDriver时出错: {e}")
            finally:
                self.driver = None



controller = JavBusSeleniumController()

# Selenium 版本的特殊功能
def get_html_with_selenium(url, headless=True, delay=3):
    """使用 Selenium 获取 HTML 内容"""
    try:
        html_content = controller.get_page_content(url)
        return html_content
    finally:
        controller.close_driver()

def parse_html_with_selenium(url, parser_func, headless=True, delay=3):
    """使用 Selenium 获取页面并用自定义解析函数处理"""
    try:
        html_content = controller.get_page_content(url)
        if html_content:
            soup = BeautifulSoup(html_content, 'html.parser')
            return parser_func(soup)
        return None
    finally:
        controller.close_driver()
  




def parse_actress_info(html_content, base_url=None):
    """解析演员个人信息"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 查找演员信息区域
        avatar_box = soup.find('div', class_='avatar-box')
        if not avatar_box:
            logger.info("未找到演员信息区域")
            return None
            
        actress_info = {}
        
        # 获取演员头像
        photo_frame = avatar_box.find('div', class_='photo-frame')
        if photo_frame:
            img = photo_frame.find('img')
            if img:
                img_src = img.get('src', '')
                # 构建完整的图片URL
                if base_url and img_src:
                    actress_info['image_url'] = urljoin(base_url, img_src)
                else:
                    actress_info['image_url'] = img_src
                actress_info['name'] = img.get('title', '')
        
        # 获取演员详细信息
        photo_info = avatar_box.find('div', class_='photo-info')
        if photo_info:
            # 获取演员名称（如果头像中没有获取到）
            if not actress_info.get('name'):
                name_span = photo_info.find('span', class_='pb10')
                if name_span:
                    actress_info['name'] = name_span.get_text(strip=True)
            
            # 获取身体数据
            info_paragraphs = photo_info.find_all('p')
            for p in info_paragraphs:
                text = p.get_text(strip=True)
                if '身高:' in text:
                    actress_info['height'] = text.replace('身高:', '').strip()
                elif '罩杯:' in text:
                    actress_info['cup_size'] = text.replace('罩杯:', '').strip()
                elif '胸圍:' in text:
                    actress_info['bust'] = text.replace('胸圍:', '').strip()
                elif '腰圍:' in text:
                    actress_info['waist'] = text.replace('腰圍:', '').strip()
                elif '臀圍:' in text:
                    actress_info['hip'] = text.replace('臀圍:', '').strip()
                elif '愛好:' in text:
                    actress_info['hobby'] = text.replace('愛好:', '').strip()
        
        return actress_info
        
    except Exception as e:
        logger.info(f"解析演员信息时出错: {e}")
        return None

def parse_actress_movies(html_content):
    """解析演员的影片列表"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        movies = []
        
        # 查找所有影片项目
        movie_items = soup.find_all('div', class_='item')
        
        for item in movie_items:
            # 跳过演员信息区域
            if item.find('div', class_='avatar-box'):
                continue
                
            movie_box = item.find('a', class_='movie-box')
            if not movie_box:
                continue
                
            movie_info = {}
            
            # 获取影片链接
            movie_info['url'] = movie_box.get('href', '')
            
            # 获取封面图片
            photo_frame = movie_box.find('div', class_='photo-frame')
            if photo_frame:
                img = photo_frame.find('img')
                if img:
                    movie_info['cover_url'] = img.get('src', '')
                    movie_info['title'] = img.get('title', '')
            
            # 获取影片详细信息
            photo_info = movie_box.find('div', class_='photo-info')
            if photo_info:
                # 获取标题（如果封面中没有获取到）
                if not movie_info.get('title'):
                    span = photo_info.find('span')
                    if span:
                        title_text = span.get_text(strip=True)
                        # 移除标签信息，只保留标题
                        if '<br' in str(span):
                            title_text = title_text.split('\n')[0] if '\n' in title_text else title_text
                        movie_info['title'] = title_text
                
                # 获取标签信息
                item_tags = photo_info.find('div', class_='item-tag')
                tags = []
                if item_tags:
                    buttons = item_tags.find_all('button')
                    for button in buttons:
                        tag_text = button.get_text(strip=True)
                        if tag_text:
                            tags.append(tag_text)
                movie_info['tags'] = tags
                
                # 获取识别码和发行日期
                date_elements = photo_info.find_all('date')
                if len(date_elements) >= 2:
                    movie_info['code'] = date_elements[0].get_text(strip=True)
                    movie_info['release_date'] = date_elements[1].get_text(strip=True)
                elif len(date_elements) == 1:
                    # 尝试从文本中分离识别码和日期
                    date_text = date_elements[0].get_text(strip=True)
                    if '/' in date_text:
                        parts = date_text.split('/')
                        movie_info['code'] = parts[0].strip()
                        if len(parts) > 1:
                            movie_info['release_date'] = parts[1].strip()
                    else:
                        movie_info['code'] = date_text
            
            if movie_info.get('url'):  # 确保有有效的URL
                movies.append(movie_info)
        
        return movies
        
    except Exception as e:
        logger.info(f"解析演员影片列表时出错: {e}")
        return []

def get_next_page_url_actress(current_url, html_content):
    """获取演员页面的下一页URL"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 查找下一页链接
        next_link = soup.find('a', id='next')
        if next_link and next_link.get('href'):
            next_href = next_link.get('href')
            
            # 构建完整的URL
            from urllib.parse import urljoin, urlparse
            parsed_current = urlparse(current_url)
            
            # 如果是相对路径，构建完整URL
            if next_href.startswith('/'):
                next_url = f"{parsed_current.scheme}://{parsed_current.netloc}{next_href}"
            elif next_href.startswith('http'):
                next_url = next_href
            else:
                # 相对路径处理
                next_url = urljoin(current_url, next_href)
            
            return next_url
        
        return None
        
    except Exception as e:
        logger.info(f"获取下一页URL时出错: {e}")
        return None

def update_actress_data(actress_info,code):

    print('========---------')
    """更新演员数据到数据库"""
    try:
        # 准备演员数据
        actress_data = {
            'name': actress_info.get('name', ''),
            'code': code,
            'detail_url': actress_info.get('detail_url', ''),
            'image_url': actress_info.get('image_url', ''),
            'height': actress_info.get('height', ''),
            'cup_size': actress_info.get('cup_size', ''),
            'bust': actress_info.get('bust', ''),
            'waist': actress_info.get('waist', ''),
            'hip': actress_info.get('hip', ''),
            'hobby': actress_info.get('hobby', '')
        }
        print("============")
        print(actress_data)
        # 写入数据库
        return db_manager.write_actress_data(actress_data)
        
    except Exception as e:
        logger.info(f"更新演员数据时出错: {e}")
        return False

def process_actress_page(code, max_pages=None):
    """处理演员页面，获取演员信息和所有影片"""
    try:
        logger.info(f"开始处理演员页面: {code}")
        current_url = (f'{jav_base_url}/star/{code}')
         
        page_count = 0
        total_movies = []
        actress_info = None
        
        while current_url and (max_pages is None or page_count < max_pages):
            logger.info(f"正在处理第 {page_count + 1} 页: {current_url}")
            
            # 获取页面内容
            html_content = controller.get_page_content(current_url)
            if not html_content:
                logger.info(f"无法获取页面内容: {current_url}")
                break
            
            # 第一页时解析演员信息
            if page_count == 0:
                actress_info = parse_actress_info(html_content, jav_base_url)
                if actress_info:
                    actress_info['detail_url'] = current_url
                    logger.info(f"解析到演员信息: {actress_info.get('name', 'Unknown')}")
                    # 更新演员数据到数据库
                    update_actress_data(actress_info,code)
                else:
                    logger.info("未能解析到演员信息")
            
            # 解析影片列表
            movies =  parse_actress_movies(html_content)
            logger.info(f"第 {page_count + 1} 页找到 {len(movies)} 部影片")
             
            for movie in movies: 
                code = movie['code'] 
                if code and db_manager.is_movie_crawed(code) == False:
                    try:
                        # 获取影片详细页面
                        movie_html =  controller.get_page_content(movie['url']) 
                        if movie_html:
                            # 使用pageparser解析影片详细信息
                            import pageparser
                            movie_detail = pageparser.parser_content(movie_html)
                            if movie_detail:
                                # 写入数据库
                                db_manager.write_jav_movie(movie_detail)
                                logger.info(f"✓ 已保存影片: {movie_detail.get('識別碼', 'Unknown')}")
                            else:
                                logger.error(f"✗ 无法解析影片详情: {movie['url']}")
                                db_manager.add_retry_url(movie['url'], 'parse_error', '无法解析影片详情')
                        else:
                            logger.error(f"✗ 无法获取影片页面: {movie['url']}")
                            db_manager.add_retry_url(movie['url'], 'fetch_error', '无法获取影片页面')
                    except Exception as e:
                        logger.error(f"✗ 处理影片时出错 {movie['url']}: {e}")
                        db_manager.add_retry_url(movie['url'], 'process_error', str(e))
                else:
                    logger.info(f"跳过已处理的影片: {movie['url']}")
            total_movies.extend(movies)
            
            # 获取下一页URL
            next_url =  get_next_page_url_actress(current_url, html_content)
            if next_url:
                logger.info(f"找到下一页: {next_url}")
                current_url = next_url
                page_count += 1
                
                # 添加延迟避免请求过快
                import time
                time.sleep(2)
            else:
                logger.info("没有更多页面")
                break
        
        logger.info(f"演员页面处理完成，共处理 {page_count + 1} 页，{len(total_movies)} 部影片")
        
        return {
            'actress_info': actress_info,
            'total_movies': len(total_movies),
            'total_pages': page_count + 1,
            'movies': total_movies
        }
        
    except Exception as e:
        logger.info(f"处理演员页面时出错: {e}")
        return None

# 使用示例
if __name__ == "__main__":
    # 测试 Selenium 控制器
    try:
        # 测试获取页面内容
        html = controller.get_page_content("https://www.javbus.com")
        if html:
            logger.info("成功获取页面内容")
            logger.info(f"页面长度: {len(html)} 字符")
        else:
            logger.info("获取页面内容失败")
    finally:
        controller.close_driver()
# 在文件末尾添加以下方法
def retry_failed_urls(max_retries=3):
    """重试失败的URL"""
    pending_urls = db_manager.get_pending_retry_urls()
    
    for url_info in pending_urls:
        url = url_info['url']
        retry_count = url_info.get('retry_count', 0)
        
        if retry_count >= max_retries:
            db_manager.update_retry_status(url, False, retry_count)
            continue
            
        try:
            # 这里调用原来的处理方法
            html = controller.get_page_content(url)
            if html:
                movie_detail = parser_content(html)
                if movie_detail:
                    db_manager.write_jav_movie(movie_detail)
                    db_manager.update_retry_status(url, True, retry_count)
                    continue
            
            # 如果重试失败
            db_manager.update_retry_status(url, False, retry_count)
            
        except Exception as e:
            logger.error(f"重试失败 {url}: {e}")
            db_manager.update_retry_status(url, False, retry_count)