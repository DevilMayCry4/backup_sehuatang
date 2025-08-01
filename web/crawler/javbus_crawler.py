import requests
from bs4 import BeautifulSoup
import json
import time
from urllib.parse import urljoin, urlparse
import re

class JavBusCrawler:
    def __init__(self, base_url="https://www.javbus.com"):
        self.base_url = base_url
        self.session = requests.Session()
        # 设置请求头，模拟浏览器访问
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def parse_pagination(self, html_content):
        """
        解析分页信息，返回下一页链接
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        pagination_info = {
            'has_next': False,
            'next_url': None,
            'current_page': 1,
            'total_pages': 1,
            'all_page_urls': []
        }
        
        # 查找分页容器
        pagination = soup.find('ul', class_='pagination')
        if not pagination:
            return pagination_info
        
        # 查找下一页链接
        next_link = pagination.find('a', id='next')
        if next_link and next_link.get('href'):
            pagination_info['has_next'] = True
            pagination_info['next_url'] = urljoin(self.base_url, next_link.get('href'))
        
        # 获取所有页面链接
        page_links = pagination.find_all('a')
        page_numbers = []
        
        for link in page_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # 跳过"下一頁"链接
            if text in ['下一頁', 'Next', '下一页']:
                continue
                
            # 提取页码
            if text.isdigit():
                page_num = int(text)
                page_numbers.append(page_num)
                pagination_info['all_page_urls'].append({
                    'page': page_num,
                    'url': urljoin(self.base_url, href)
                })
        
        if page_numbers:
            pagination_info['total_pages'] = max(page_numbers)
            
            # 确定当前页码
            active_page = pagination.find('li', class_='active')
            if active_page:
                active_link = active_page.find('a')
                if active_link and active_link.get_text(strip=True).isdigit():
                    pagination_info['current_page'] = int(active_link.get_text(strip=True))
        
        return pagination_info
    
    def parse_movie_items(self, html_content):
        """
        解析HTML内容，提取电影项目信息
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        movie_items = []
        
        # 查找所有的电影项目
        items = soup.find_all('div', class_='item')
        
        for item in items:
            try:
                # 提取电影链接
                movie_box = item.find('a', class_='movie-box')
                if not movie_box:
                    continue
                    
                movie_url = movie_box.get('href', '')
                
                # 提取图片信息
                img_tag = movie_box.find('img')
                if not img_tag:
                    continue
                    
                img_src = img_tag.get('src', '')
                img_title = img_tag.get('title', '')
                
                # 提取电影编号和日期
                photo_info = item.find('div', class_='photo-info')
                movie_code = ''
                release_date = ''
                
                if photo_info:
                    date_tags = photo_info.find_all('date')
                    if len(date_tags) >= 2:
                        movie_code = date_tags[0].get_text(strip=True)
                        release_date = date_tags[1].get_text(strip=True)
                    elif len(date_tags) == 1:
                        movie_code = date_tags[0].get_text(strip=True)
                
                # 检查是否有高清和字幕标签
                has_hd = bool(item.find('button', class_='btn-primary'))
                has_subtitle = bool(item.find('button', class_='btn-warning'))
                
                # 构建完整的URL
                full_movie_url = urljoin(self.base_url, movie_url) if movie_url else ''
                full_img_url = urljoin(self.base_url, img_src) if img_src else ''
                
                movie_data = {
                    'title': img_title,
                    'movie_url': full_movie_url,
                    'image_url': full_img_url,
                    'movie_code': movie_code,
                    'release_date': release_date,
                    'has_hd': has_hd,
                    'has_subtitle': has_subtitle
                }
                
                movie_items.append(movie_data)
                
            except Exception as e:
                print(f"解析项目时出错: {e}")
                continue
        
        return movie_items
    
    def crawl_from_file(self, file_path):
        """
        从本地HTML文件解析电影信息和分页信息
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            movie_items = self.parse_movie_items(html_content)
            pagination_info = self.parse_pagination(html_content)
            
            return {
                'movies': movie_items,
                'pagination': pagination_info
            }
            
        except Exception as e:
            print(f"读取文件时出错: {e}")
            return {'movies': [], 'pagination': {'has_next': False}}
    
    def crawl_from_url(self, url, max_pages=None, max_retries=3):
        """
        从网站URL爬取电影信息，支持多页爬取和重试机制
        """
        all_movies = []
        current_url = url
        page_count = 0
        
        while current_url and (max_pages is None or page_count < max_pages):
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    print(f"正在爬取第 {page_count + 1} 页: {current_url} (尝试 {retry_count + 1}/{max_retries})")
                    
                    # 增加更长的超时时间和重试间隔
                    response = self.session.get(current_url, timeout=30)
                    response.raise_for_status()
                    response.encoding = 'utf-8'
                    
                    # 解析当前页面
                    movie_items = self.parse_movie_items(response.text)
                    pagination_info = self.parse_pagination(response.text)
                    
                    # 添加页面信息到每个电影项目
                    for movie in movie_items:
                        movie['page_number'] = page_count + 1
                        movie['source_url'] = current_url
                    
                    all_movies.extend(movie_items)
                    
                    print(f"第 {page_count + 1} 页找到 {len(movie_items)} 个电影项目")
                    
                    # 检查是否有下一页
                    if pagination_info['has_next']:
                        current_url = pagination_info['next_url']
                        page_count += 1
                        
                        # 增加延迟避免请求过快
                        time.sleep(2)
                    else:
                        print("已到达最后一页")
                        break
                        
                    success = True
                    
                except requests.exceptions.ConnectionError as e:
                    retry_count += 1
                    print(f"连接错误 (尝试 {retry_count}/{max_retries}): {e}")
                    if retry_count < max_retries:
                        wait_time = retry_count * 5  # 递增等待时间
                        print(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                    else:
                        print(f"第 {page_count + 1} 页连接失败，跳过")
                        break
                        
                except requests.exceptions.Timeout as e:
                    retry_count += 1
                    print(f"请求超时 (尝试 {retry_count}/{max_retries}): {e}")
                    if retry_count < max_retries:
                        wait_time = retry_count * 3
                        print(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                    else:
                        print(f"第 {page_count + 1} 页请求超时，跳过")
                        break
                        
                except Exception as e:
                    retry_count += 1
                    print(f"爬取第 {page_count + 1} 页时出错 (尝试 {retry_count}/{max_retries}): {e}")
                    if retry_count < max_retries:
                        time.sleep(2)
                    else:
                        print(f"第 {page_count + 1} 页爬取失败，跳过")
                        break
            
            if not success:
                break
        
        return {
            'movies': all_movies,
            'total_pages_crawled': page_count + 1,
            'total_movies': len(all_movies)
        }
    
    def crawl_all_pages_from_file(self, file_path, base_series_url=None):
        """
        从本地文件开始，然后爬取所有相关页面
        """
        # 先解析本地文件
        local_result = self.crawl_from_file(file_path)
        all_movies = local_result['movies']
        
        # 为本地文件的电影添加页面信息
        for movie in all_movies:
            movie['page_number'] = 1
            movie['source_url'] = 'local_file'
        
        pagination_info = local_result['pagination']
        
        print(f"本地文件找到 {len(all_movies)} 个电影项目")
        
        # 如果有下一页且提供了基础URL，继续爬取
        if pagination_info['has_next'] and base_series_url:
            print("检测到有下一页，开始爬取网络页面...")
            
            # 从第2页开始爬取
            next_url = pagination_info['next_url']
            if not next_url.startswith('http'):
                next_url = urljoin(base_series_url, next_url)
            
            web_result = self.crawl_from_url(next_url)
            
            # 合并结果
            all_movies.extend(web_result['movies'])
            
            return {
                'movies': all_movies,
                'total_pages_crawled': web_result['total_pages_crawled'] + 1,
                'total_movies': len(all_movies),
                'local_movies': len(local_result['movies']),
                'web_movies': len(web_result['movies'])
            }
        
        return {
            'movies': all_movies,
            'total_pages_crawled': 1,
            'total_movies': len(all_movies),
            'local_movies': len(all_movies),
            'web_movies': 0
        }
    
    def save_to_json(self, result, filename='movie_data.json'):
        """
        将电影数据保存为JSON文件
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"数据已保存到 {filename}")
        except Exception as e:
            print(f"保存文件时出错: {e}")
    
    def print_movie_info(self, movies):
        """
        打印电影信息
        """
        for i, movie in enumerate(movies, 1):
            print(f"\n=== 电影 {i} ===")
            print(f"标题: {movie['title']}")
            print(f"电影链接: {movie['movie_url']}")
            print(f"图片地址: {movie['image_url']}")
            print(f"电影编号: {movie['movie_code']}")
            print(f"发布日期: {movie['release_date']}")
            print(f"高清: {'是' if movie['has_hd'] else '否'}")
            print(f"字幕: {'是' if movie['has_subtitle'] else '否'}")
            if 'page_number' in movie:
                print(f"页面: 第{movie['page_number']}页")
    
    def print_summary(self, result):
        """
        打印爬取结果摘要
        """
        print(f"\n=== 爬取结果摘要 ===")
        print(f"总共爬取页面数: {result.get('total_pages_crawled', 1)}")
        print(f"总共找到电影: {result.get('total_movies', len(result['movies']))}")
        
        if 'local_movies' in result:
            print(f"本地文件电影数: {result['local_movies']}")
        if 'web_movies' in result:
            print(f"网络爬取电影数: {result['web_movies']}")
    def search_movies(self, series_name):
        """
        搜索指定系列的电影
        """
        url = f"{self.base_url}/series/{series_name}"
        return self.crawl_from_url(url, max_pages=10)['movies']

# 使用示例
if __name__ == "__main__":
    crawler = JavBusCrawler()
    url = "https://www.javbus.com/series/onl"  # 示例URL
    web_result = crawler.crawl_from_url(url, max_pages=10)  # 限制爬取3页
    if web_result['movies']:
        crawler.print_summary(web_result)
        crawler.save_to_json(web_result, 'javbus_web_movies.json')