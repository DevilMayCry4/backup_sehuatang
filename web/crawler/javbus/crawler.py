#!/usr/bin/env python
#-*-coding:utf-8-*-

import sys
import controler
import downloader
import pageparser
import time
import re
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError
import controler_selenium

base_url = 'https://www.javbus.com'


def get_dict(url):
    """get the dict of the detail page and yield the dict"""

    url_html = downloader.get_html(url)
    for detail_url in pageparser.parser_homeurl(url_html):
        try:
            detail_page_html = downloader.get_html(detail_url)
            dict_jav = pageparser.parser_content(detail_page_html)
        # except Exception as err:
        #     with open('fail_url.txt', 'a') as fd:
        #         fd.write('%s %d: %s\n' % ('ERROR CODE', err.code, url))
        #     print("Fail to crawl %s\ncrawl next detail page......" % detail_url)
        #     continue
        except HTTPError as err:
            if err.response.status_code == 404:
                with open('404_url.txt', 'a') as fd:
                    fd.write('%s\n' % detail_url)
            else:
                with open('fail_url.txt', 'a') as fd:
                    fd.write('%s\n' % detail_url)
            print("Fail to crawl %s\ncrawl next detail page......" % detail_url)
            continue
        except Exception as err:
            with open('fail_url.txt', 'a') as fd:
                fd.write('%s\n' % detail_url)
            print("Fail to crawl %s\ncrawl next detail page......" % detail_url)
            continue

        yield dict_jav, detail_url


def get_data_single(url):
    """get the dict of the detail page and yield the dict"""

    try:
        detail_page_html = downloader.get_html(url)
        dict_jav = pageparser.parser_content(detail_page_html)
    except HTTPError as err:
        if err.response.status_code == 404:
            with open('404_url.txt', 'a') as fd:
                fd.write('%s\n' % url)
        else:
            with open('fail_url.txt', 'a') as fd:
                fd.write('%s\n' % url)
        print("Fail to crawl %s\ncrawl next detail page......" % url)
    except Exception as err:
        with open('fail_url.txt', 'a') as fd:
            fd.write('%s\n' % url)
        print("Fail to crawl %s\ncrawl next detail page......" % url)
    else:
        yield dict_jav

def join_db(url):
    """the detail_dict of the url join the db"""
    bango_in_page_cnt = 0
    for dict_jav_data, detail_url in get_dict(url):
        if controler.check_url_not_in_table(detail_url):
            print("detail_url = %s not exist" % detail_url)
            controler.write_data(dict_jav_data)
        else:
            if dict_jav_data['磁力链接'] == controler.read_magnets_from_table(detail_url)[0][0]:
                print("detail_url = %s exists" % detail_url)
                bango_in_page_cnt = bango_in_page_cnt + 1
                continue
                # print("it has updated over...window will be closed after 60s")
                # time.sleep(60)
                # exit()
            else:
                print("detail_url = %s updating" % detail_url)
                controler.refresh_data(dict_jav_data, detail_url)
    return bango_in_page_cnt

def join_db_single(url):
    """the detail_dict of the url join the db"""

    for dict_jav_data in get_data_single(url):
        if dict_jav_data == None:
            return

        if controler.check_url_not_in_table(url):
            print("detail_url = %s not exist" % url)
            controler.write_data(dict_jav_data)
        else:
            if dict_jav_data['磁力链接'] == controler.read_magnets_from_table(url)[0][0]:
                print("detail_url = %s exists" % url)
                continue
            else:
                print("detail_url = %s updating" % url)
                controler.refresh_data(dict_jav_data, url)

def homeurl_handler(entrance):
    if entrance[-1] =='/':
        entrance = entrance[:-1]
    #创建数据表
    controler.create_db()
    if join_db(entrance) == 30:
        print('done the incremental last page.......')
        return
    print('sssssssssssssssss')
    entrance_html = controler_selenium.get_html(entrance)
    next_page_url = pageparser.get_next_page_url(entrance, entrance_html)
    while True:
        if next_page_url != None:
            if join_db(next_page_url) == 30:
                print('done the incremental last page.......')
                break
        else:
            print('done the last page.......')
            break
        print('next_page_url = %s' % next_page_url)
        next_page_html = downloader.get_html(next_page_url)
        next_page_url = pageparser.get_next_page_url(entrance, next_page_html)

def singleurl_handler(entrance):
    if entrance[-1] =='/':
        entrance = entrance[:-1]
    #创建数据表
    controler.create_db()

    join_db_single(entrance)

# 在文件顶部添加必要的导入
import os
import requests
from urllib.parse import urljoin

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
    controler.create_actress_db()
    
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
                    
                    controler.write_actress_data(actress_info)
                    actresses_data.append(actress_info)
                    
                     
    
    print(f"\n=== 女优数据处理完成 ===")
    print(f"总计: {len(actresses_data)} 人")
    print(f"成功保存: {success_count} 人")
    print(f"保存失败: {error_count} 人")
    
 
    
    return actresses_data

def crawl_actresses():
    max = 3
    for i in range(2, max):
        url = f"{base_url}/actresses/{i}"
        actresses_handler(url)

if __name__ == '__main__':
    crawl_actresses()
   

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

