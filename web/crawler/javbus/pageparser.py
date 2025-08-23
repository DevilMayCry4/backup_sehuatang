#!/usr/bin/env python
#-*-coding:utf-8-*-

from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re
import os
import requests
from database import db_manager

headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.javbus.com/'
        }

def _get_cili_url(soup):
    """get_cili(soup).get the ajax url and Referer url of request"""

    # ajax_get_cili_url = 'https://www.javbus5.com/ajax/uncledatoolsbyajax.php?lang=zh'
    ajax_get_cili_url = 'https://www.javbus.com/ajax/uncledatoolsbyajax.php?lang=zh'

    '''
    0:
    '\n   var gid = 60013997586'
    1:
    '\r\n\tvar uc = 0'
    2:
    "\r\n\tvar img = '/pics/cover/apwc_b.jpg'"
    '''
    
    # ajax_data = soup.select('script')[9].text
    # for l in ajax_data.split(';')[:-1]:
    #     ajax_get_cili_url += '&%s' % l[7:].replace("'","").replace(' ','')

    html = soup.prettify()
    '''获取img'''
    img_pattern = re.compile(r"var img = '.*?'")
    match = img_pattern.findall(html)
    img=match[0].replace("var img = '","").replace("'","")

    '''获取uc'''
    uc_pattern = re.compile(r"var uc = .*?;")
    match = uc_pattern.findall(html)
    uc = match[0].replace("var uc = ", "").replace(";","")

    '''获取gid'''
    gid_pattern = re.compile(r"var gid = .*?;")
    match = gid_pattern.findall(html)
    gid = match[0].replace("var gid = ", "").replace(";","")

    ajax_get_cili_url = ajax_get_cili_url + '&gid=' + gid + '&img=' + img + '&uc=' + uc
    return ajax_get_cili_url


def _parser_magnet(html):
    """parser_magnet(html),get all magnets from a html and return the str of magnet"""

    #存放磁力的字符串
    magnet = ''
    soup = BeautifulSoup(html,"html.parser")
    # for td in soup.select('td[width="70%"]'):
        # magnet += td.a['href'] + '\n'
    
    avdist={'title':'','magnet':'','size':'','date':''}
    for tr in soup.find_all('tr'):
        i=0
        for td in tr:
            if(td.string):
                continue
            i=i+1
            avdist['magnet']=td.a['href']
            if (i%3 == 1):
                avdist['title'] = td.a.text.replace(" ", "").replace("\t", "").replace("\r\n","").replace("\n","")
            if (i%3 == 2):
                avdist['size'] = td.a.text.replace(" ", "").replace("\t", "").replace("\r\n","").replace("\n","")
            if (i%3 == 0):
                avdist['date'] = td.a.text.replace(" ", "").replace("\t", "").replace("\r\n","").replace("\n","")
        # print(avdist)
        magnet += '%s\n' % avdist

    return magnet

def get_next_page_url(entrance, html):
    """get_next_page_url(entrance, html),return the url of next page if exist"""
    print("done the page.......")
    parsed_entrance = urlparse(entrance)
    soup = BeautifulSoup(html, "html.parser")
    next_page = soup.select('a[id="next"]')
    if next_page:
        next_page_link = next_page[0]['href'].split('/')[-2:]
        next_page_link = '/'+'/'.join(next_page_link)
        next_page_url = f'{parsed_entrance.scheme}://{parsed_entrance.netloc}{parsed_entrance.path.rsplit("/", 2)[0]}' + next_page_link
        print("next page is %s" % next_page[0]['href'].split('/')[-1])
        return next_page_url
    return None


def parser_homeurl(html):
    """parser_homeurl(html),parser every url on every page and yield the url"""

    soup = BeautifulSoup(html,"html.parser")
    for url in soup.select('a[class="movie-box"]'):
        yield url['href']

# 添加图片下载函数
def download_image(image_url, save_path, filename,code_name,remove=False):
    """下载图片到本地"""
    try:
        # 创建保存目录
        os.makedirs(save_path, exist_ok=True)
        file_path = os.path.join(save_path, filename)
        if(os.path.exists(file_path)):
            if(remove):
                db_manager.remove_failed_image(image_url)


            print(f'文件已存在:{file_path}')
            return file_path
        else:
            print(f'开始下载图片:{image_url} 路径:{file_path}')
        # 设置请求头
        
        
        # 下载图片
        response = requests.get(image_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # 保存图片
        
        with open(file_path, 'wb') as f:
            f.write(response.content)
        
        print(f"图片已保存: {file_path}")
        return file_path
    except Exception as e:
        db_manager.record_failed_image_download(image_url, str(e),code_name)
         
        return None

def get_file_extension(url):
    """从URL获取文件扩展名"""
    parsed = urlparse(url)
    path = parsed.path
    if '.' in path:
        return path.split('.')[-1].lower()
    return 'jpg'  # 默认扩展名

def parser_content(html):
    """parser_content(html),parser page's content of every url and yield the dict of content"""

    soup = BeautifulSoup(html, "html.parser")
 
    categories = {}

    # 使用正则表达式解析識別碼 - 通用模式，不依赖语言
    code_patterns = [
        r'<span class="header">識別碼:</span>\s*<span[^>]*style="color:#CC0000;">([^<]+)</span>',
        r'<span class="header">品番:</span>\s*<span[^>]*style="color:#CC0000;">([^<]+)</span>',
        r'<span class="header">識別碼:</span>\s*<span[^>]*>([^<]+)</span>'
    ]
    code_name = ''
    for pattern in code_patterns:
        code_match = re.search(pattern, html)
        if code_match:
            code_name = code_match.group(1).strip()
            break
    
    categories['識別碼'] = code_name
    if code_name == '':
        return

    # 使用正则表达式解析發行日期 - 支持多种语言
    date_patterns = [
        r'<span class="header">發行日期:</span>\s*([0-9-]+)',
        r'<span class="header">発売日:</span>\s*([0-9-]+)',
        r'<span class="header">Release Date:</span>\s*([0-9-]+)'
    ]
    date_issue = ''
    for pattern in date_patterns:
        date_match = re.search(pattern, html)
        if date_match:
            date_issue = date_match.group(1).strip()
            break
    categories['發行日期'] = date_issue

    # 使用正则表达式解析長度 - 支持多种语言
    duration_patterns = [
        r'<span class="header">長度:</span>\s*([^<]+)',
        r'<span class="header">収録時間:</span>\s*([^<]+)',
        r'<span class="header">Runtime:</span>\s*([^<]+)'
    ]
    duration = ''
    for pattern in duration_patterns:
        duration_match = re.search(pattern, html)
        if duration_match:
            duration = duration_match.group(1).strip()
            break
    categories['長度'] = duration

    # 使用正则表达式解析導演 - 支持多种语言
    director_patterns = [
        r'<span class="header">導演:</span>\s*<a[^>]*>([^<]+)</a>',
        r'<span class="header">監督:</span>\s*<a[^>]*>([^<]+)</a>',
        r'<span class="header">Director:</span>\s*<a[^>]*>([^<]+)</a>'
    ]
    director = ''
    for pattern in director_patterns:
        director_match = re.search(pattern, html)
        if director_match:
            director = director_match.group(1).strip()
            break
    categories['導演'] = director

    # 使用正则表达式解析製作商 - 支持多种语言
    manufacturer_patterns = [
        r'<span class="header">製作商:</span>\s*<a[^>]*href="([^"]*)">([^<]+)</a>',
        r'<span class="header">メーカー:</span>\s*<a[^>]*href="([^"]*)">([^<]+)</a>',
        r'<span class="header">Studio:</span>\s*<a[^>]*href="([^"]*)">([^<]+)</a>'
    ]
    manufacturer = ''
    is_uncensored = 0
    for pattern in manufacturer_patterns:
        manufacturer_match = re.search(pattern, html)
        if manufacturer_match:
            manufacturer_href = manufacturer_match.group(1)
            manufacturer = manufacturer_match.group(2).strip()
            is_uncensored = 1 if 'uncensored' in manufacturer_href else 0
            break
    categories['製作商'] = manufacturer
    categories['無碼'] = is_uncensored

    # 使用正则表达式解析發行商 - 支持多种语言
    publisher_patterns = [
        r'<span class="header">發行商:</span>\s*<a[^>]*>([^<]+)</a>',
        r'<span class="header">レーベル:</span>\s*<a[^>]*>([^<]+)</a>',
        r'<span class="header">Label:</span>\s*<a[^>]*>([^<]+)</a>'
    ]
    publisher = ''
    for pattern in publisher_patterns:
        publisher_match = re.search(pattern, html)
        if publisher_match:
            publisher = publisher_match.group(1).strip()
            break
    categories['發行商'] = publisher

    # 使用正则表达式解析系列 - 支持多种语言
    series_patterns = [
        r'<span class="header">系列:</span>\s*<a[^>]*>([^<]+)</a>',
        r'<span class="header">シリーズ:</span>\s*<a[^>]*>([^<]+)</a>',
        r'<span class="header">Series:</span>\s*<a[^>]*>([^<]+)</a>'
    ]
    series = ''
    for pattern in series_patterns:
        series_match = re.search(pattern, html)
        if series_match:
            series = series_match.group(1).strip()
            break
    categories['系列'] = series

    # 使用正则表达式解析類別 - 通用模式
    genre_pattern = r'<span class="genre"><label><input[^>]*><a[^>]*>([^<]+)</a></label></span>'
    genre_matches = re.findall(genre_pattern, html)
    genre_text = '\n'.join(genre.strip() for genre in genre_matches)
    categories['類別'] = genre_text

    # 使用正则表达式解析演員 - 通用模式
    # 匹配带有onmouseover属性的span标签中的链接文本
    actor_pattern = r'<span[^>]*onmouseover[^>]*>\s*<a[^>]*>([^<]+)</a>\s*</span>'
    actor_matches = re.findall(actor_pattern, html)
    actor_text = '\n'.join(actor.strip() for actor in actor_matches)
    categories['演員'] = actor_text
    
    # 使用正则表达式解析网址 - 通用模式
    url_pattern = r'<link rel="canonical" href="([^"]+)"'
    url_match = re.search(url_pattern, html)
    url = url_match.group(1) if url_match else ''
    categories['URL'] = url

    # 将磁力链接加入字典
    is_subtitle = False
    try:
        magnet_html = get_html(_get_cili_url(soup), Referer_url=url)
        magnet = _parser_magnet(magnet_html)
        categories['磁力链接'] = magnet
        is_subtitle = magnet.find('字幕') != -1
    except:
        categories['磁力链接'] = ''

    # 使用正则表达式解析封面链接 - 通用模式
    cover_pattern = r'<a[^>]*class="bigImage"[^>]*><img[^>]*src="([^"]+)"'
    cover_match = re.search(cover_pattern, html)
    if cover_match:
        bigimage_url = cover_match.group(1)
        if bigimage_url.startswith('/'):
            parsed = urlparse(url)
            bigimage_url = parsed.scheme + '://' + parsed.netloc + bigimage_url
        categories['封面'] = bigimage_url
        
        # 下载封面图片
        if bigimage_url and categories.get('識別碼'):
            code_name = categories['識別碼']
            save_dir = os.path.join('/server/static/images', 'covers', code_name)
            cover_filename = f"{code_name}_cover.jpg"
            try:
                download_image(bigimage_url, save_dir, cover_filename, code_name)
            except:
                pass
    
    # 使用正则表达式解析標題 - 通用模式
    title_pattern = r'<title>([^<]+)</title>'
    title_match = re.search(title_pattern, html)
    if title_match:
        title = title_match.group(1).strip().replace(" - JavBus", "")
        categories['標題'] = title
    is_single = len(actor_matches) == 1 
    categories['is_single'] = is_single
    categories['is_subtitle'] = is_subtitle 
    print(categories)
    return categories


def get_html(url, Referer_url=None, max_retries=5):
    '''get_html(url),download and return html'''
    if Referer_url==None:
        Referer_url = url

    if Referer_url:
        headers['Referer'] = Referer_url

    if max_retries<1:
        max_retries = 1

    for i in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                break
            elif response.status_code == 404:
                response.raise_for_status() # raise an HTTPError exception at once, if 404 err happens

        except Exception as err:
            # print(err)
            if i == (max_retries -1):
               raise     # other exceptions raised after max_retries attempts

    html = response.content
    soup = BeautifulSoup(html.decode('utf-8', errors='ignore'), 'html.parser')
    html = soup.prettify()
    return html

