#!/usr/bin/env python
#-*-coding:utf-8-*-

  
import pageparser
import re
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError
import controler_selenium 
import db_manger

base_url = 'https://www.javbus.com'


 
 
 
def download_actress_image(image_url, actress_code, actress_name):
    """下载演员头像到本地"""
    try:
        if not image_url or not actress_code:
            return None
            
        # 创建保存目录
        save_dir = '/root/backup_sehuatang/images/actresses'
        os.makedirs(save_dir, exist_ok=True)
        
        # 获取文件扩展名
        file_extension = '.jpg'  # 默认为jpg
        if '.' in image_url:
            file_extension = '.' + image_url.split('.')[-1].split('?')[0]
        
        # 构建文件名：演员编码_演员名称.扩展名
        safe_name = actress_name.replace('/', '_').replace('\\', '_') if actress_name else 'unknown'
        filename = f"{actress_code}_{safe_name}{file_extension}"
        file_path = os.path.join(save_dir, filename)
        
        # 如果文件已存在，跳过下载
        if os.path.exists(file_path):
            print(f"头像已存在: {filename}")
            return file_path
        
        # 下载图片
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.5112.102 Safari/537.36',
            'Referer': 'https://www.javbus.com/actresses'
        }
        
        response = requests.get(image_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # 保存图片
        with open(file_path, 'wb') as f:
            f.write(response.content)
        
        print(f"✓ 头像下载成功: {filename}")
        return file_path
        
    except Exception as e:
        print(f"✗ 头像下载失败 {actress_code}: {e}")
        return None

# 修改actresses_handler函数中的相关部分
def actresses_handler(url):
    """女优ページを爬取して女优情報を抽出し、データベースに保存する"""
  
    
    # 女优数据库初始化
    db_manger.create_actress_db()
    
    # actresses ページのHTMLを取得
    entrance_html = controler_selenium.get_html_with_selenium(url)
    print(entrance_html)
    # BeautifulSoupでHTMLを解析
    soup = BeautifulSoup(entrance_html, 'html.parser')
    
    # 女优情報を格納するリスト
    actresses_data = []
    success_count = 0
    error_count = 0
    
    # waterfall div内のすべての女优アイテムを取得
    waterfall = soup.find('div', id='waterfall')
    if waterfall:
        items = waterfall.find_all('div', class_='item')
        
        for item in items:
            avatar_box = item.find('a', class_='avatar-box')
            if avatar_box:
                # 詳細URLを取得
                detail_url = avatar_box.get('href')
                
                # 女优編码を抽出 (URLの最後の部分)
                actress_code = None
                if detail_url:
                    match = re.search(r'/star/([^/]+)$', detail_url)
                    if match:
                        actress_code = match.group(1)
                
                # 画像情報を取得
                img_tag = avatar_box.find('img')
                if img_tag:
                    img_src = img_tag.get('src')
                    actress_name = img_tag.get('title')
                    
                    # 构建完整的图片URL
                    full_image_url = f"https://www.javbus.com{img_src}" if img_src and not img_src.startswith('http') else img_src
                    
                    # 下载演员头像到本地
                    download_actress_image(full_image_url, actress_code, actress_name)
                    
                    # 女优データを辞書として保存
                    actress_info = {
                        'name': actress_name,
                        'code': actress_code,
                        'image_url': full_image_url,
                    }
                    
                    db_manger.write_actress_data(actress_info)
                    actresses_data.append(actress_info)
                    
                     
    
    print(f"\n=== 女优数据处理完成 ===")
    print(f"总计: {len(actresses_data)} 人")
    print(f"成功保存: {success_count} 人")
    print(f"保存失败: {error_count} 人")
    
 
    
    return actresses_data

def crawl_actresses():
    max = 250
    for i in range(11, max):
        url = f"{base_url}/actresses/{i}"
        actresses_handler(url)

def craw_star():
    result = controler_selenium.process_actress_page('reg',max_pages=1000)

if __name__ == '__main__':
     
    #crawl_actresses()
      
    craw_star()
    #homeurl_handler('https://www.javbus.com')
    # homeurl_handler('https://www.javbus.com/ja/page/38')
    #homeurl_handler('https://www.javbus.com/ja/uncensored')
    # homeurl_handler('https://www.javbus.com/ja/SDJS-271') # 1 + 5
    # singleurl_handler('https://www.javbus.com/ja/SDJS-271')
    # singleurl_handler('https://www.javbus.com/ja/SP-1000') # test 404 error
    # singleurl_handler('https://www.javbus.com/ja/page/6') # test err url
    # singleurl_handler('https://www.javbus.com/ja/HEYZO-3379') # test uncensored
    # singleurl_handler('https://www.javbus.com/ja/EZD-269') # test bad page
    # singleurl_handler('https://www.javbus.com/ja/SDDL-478')
    # singleurl_handler('https://www.javbus.com/ja/BIG-054')
    # singleurl_handler('https://www.javbus.com/ja/FAA-250')
    # singleurl_handler('https://www.javbus.com/ja/STCV-036')
    # homeurl_handler(sys.argv[1])
    # singleurl_handler(sys.argv[1])
	# singleurl_handler('https://www.javbus.com/ja/' + sys.argv[1])

