#!/usr/bin/env python
#-*-coding:utf-8-*-

from bs4 import BeautifulSoup
from urllib.parse import urlparse
import downloader
import re
import os
import requests
from urllib.parse import urljoin

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


#!/usr/bin/env python
#-*-coding:utf-8-*-

from bs4 import BeautifulSoup
from urllib.parse import urlparse
import downloader
import re
import os
import requests
from urllib.parse import urljoin

# 添加图片下载函数
def download_image(image_url, save_path, filename):
    """下载图片到本地"""
    try:
        # 创建保存目录
        os.makedirs(save_path, exist_ok=True)
        
        # 设置请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.javbus.com/'
        }
        
        # 下载图片
        response = requests.get(image_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # 保存图片
        file_path = os.path.join(save_path, filename)
        with open(file_path, 'wb') as f:
            f.write(response.content)
        
        print(f"图片已保存: {file_path}")
        return file_path
    except Exception as e:
        print(f"下载图片失败 {image_url}: {e}")
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
    print("sssss")
    '''获取lang'''
    lang_pattern = re.compile(r"var lang = '.*?'")
    match = lang_pattern.findall(soup.prettify())
    lang=match[0].replace("var lang = '","").replace("'","")

    categories = {}

    if lang == 'zh':
        code_name_doc = soup.find('span', text=re.compile("識別碼:"))
        code_name = code_name_doc.parent.contents[3].text.strip() if code_name_doc else ''
        categories['識別碼'] = code_name
        #code_name = soup.find('span', text="識別碼:").parent.contents[2].text if soup.find('span', text="識別碼:") else ''
        if code_name == '':
            return

        date_issue_doc = soup.find('span', text=re.compile("發行日期:"))
        date_issue = date_issue_doc.parent.contents[2].strip() if date_issue_doc else ''
        categories['發行日期'] = date_issue
        #date_issue = soup.find('span', text="發行日期:").parent.contents[1].strip() if soup.find('span', text="發行日期:") else ''

        duration_doc = soup.find('span', text=re.compile("長度:"))
        duration = duration_doc.parent.contents[2].strip() if duration_doc else ''
        categories['長度'] = duration
        #duration = soup.find('span', text="長度:").parent.contents[1].strip() if soup.find('span', text="長度:") else ''

        director_doc = soup.find('span', text=re.compile("導演:"))
        if hasattr(director_doc,'parent'):
            if len(director_doc.parent.contents) > 3:
                director = director_doc.parent.contents[3].text.strip() if director_doc else ''
            else:
                director = ''
        else:
            director = ''
        categories['導演'] = director
        #director = soup.find('span', text="導演:").parent.contents[2].text if soup.find('span', text="導演:") else ''

        manufacturer_doc = soup.find('span', text=re.compile("製作商:"))
        manufacturer = manufacturer_doc.parent.contents[3].text.strip() if manufacturer_doc else ''
        categories['製作商'] = manufacturer
        #manufacturer = soup.find('span', text="製作商:").parent.contents[2].text if soup.find('span', text="製作商:") else ''
        if hasattr(manufacturer_doc,'parent'):
            is_uncensored = 1 if 'uncensored' in manufacturer_doc.parent.contents[3]['href'] else 0
        else:
            is_uncensored = 0
        categories['無碼'] = is_uncensored

        publisher_doc = soup.find('span', text=re.compile("發行商:"))
        publisher = publisher_doc.parent.contents[3].text.strip()  if publisher_doc else ''
        categories['發行商'] = publisher
        #publisher = soup.find('span', text="發行商:").parent.contents[2].text if soup.find('span', text="發行商:") else ''

        series_doc = soup.find('span', text=re.compile("系列:"))
        series = series_doc.parent.contents[3].text.strip()  if series_doc else ''
        categories['系列'] = series
        #series = soup.find('span', text="系列:").parent.contents[2].text if soup.find('span', text="系列:") else ''

        genre_doc = soup.select_one('p[class=header]', text=re.compile('類別:'))
        genre =(i.text.strip() for i in genre_doc.find_next('p').select('a')) if genre_doc else ''
        #genre =(i.text.strip() for i in soup.find('p', text="類別:").find_next('p').select('span')) if soup.find('p', text="類別:") else ''
        genre_text = ''
        for tex in genre:
            # genre_text += '%s   ' % tex 
            genre_text += '%s\n' % tex 
        categories['類別'] = genre_text

        actor_doc = soup.select('span[onmouseover^="hoverdiv"]')
        actor = (i.text.strip() for i in actor_doc) if actor_doc else ''
        #actor = (i.text.strip() for i in soup.select('span[onmouseover^="hoverdiv"]')) if soup.select('span[onmouseover^="hoverdiv"]') else ''
        actor_text = ''
        for tex in actor:
            # actor_text += '%s   ' % tex 
            actor_text += '%s\n' % tex 
        categories['演員'] = actor_text
        
        #网址加入字典
        url = soup.select('link[hreflang="zh"]')[0]['href']
        categories['URL'] = url
    elif lang == 'ja':
        code_name_doc = soup.find('span', text=re.compile("品番:"))
        code_name = code_name_doc.parent.contents[3].text.strip() if code_name_doc else ''
        categories['識別碼'] = code_name
        #code_name = soup.find('span', text="識別碼:").parent.contents[2].text if soup.find('span', text="識別碼:") else ''
        if code_name == '':
            return
        
        date_issue_doc = soup.find('span', text=re.compile("発売日:"))
        date_issue = date_issue_doc.parent.contents[2].strip() if date_issue_doc else ''
        categories['發行日期'] = date_issue
        #date_issue = soup.find('span', text="發行日期:").parent.contents[1].strip() if soup.find('span', text="發行日期:") else ''

        duration_doc = soup.find('span', text=re.compile("収録時間:"))
        duration = duration_doc.parent.contents[2].strip() if duration_doc else ''
        categories['長度'] = duration
        #duration = soup.find('span', text="長度:").parent.contents[1].strip() if soup.find('span', text="長度:") else ''

        director_doc = soup.find('span', text=re.compile("監督:"))
        if hasattr(director_doc,'parent'):
            if len(director_doc.parent.contents) > 3:
                director = director_doc.parent.contents[3].text.strip() if director_doc else ''
            else:
                director = ''
        else:
            director = ''
        categories['導演'] = director
        #director = soup.find('span', text="導演:").parent.contents[2].text if soup.find('span', text="導演:") else ''

        manufacturer_doc = soup.find('span', text=re.compile("メーカー:"))
        manufacturer = manufacturer_doc.parent.contents[3].text.strip() if manufacturer_doc else ''
        categories['製作商'] = manufacturer
        #manufacturer = soup.find('span', text="製作商:").parent.contents[2].text if soup.find('span', text="製作商:") else ''
        if hasattr(manufacturer_doc,'parent'):
            is_uncensored = 1 if 'uncensored' in manufacturer_doc.parent.contents[3]['href'] else 0
        else:
            is_uncensored = 0
        categories['無碼'] = is_uncensored

        publisher_doc = soup.find('span', text=re.compile("レーベル:"))
        publisher = publisher_doc.parent.contents[3].text.strip()  if publisher_doc else ''
        categories['發行商'] = publisher
        #publisher = soup.find('span', text="發行商:").parent.contents[2].text if soup.find('span', text="發行商:") else ''

        series_doc = soup.find('span', text=re.compile("シリーズ:"))
        series = series_doc.parent.contents[3].text.strip()  if series_doc else ''
        categories['系列'] = series
        #series = soup.find('span', text="系列:").parent.contents[2].text if soup.find('span', text="系列:") else ''

        genre_doc = soup.select_one('p[class=header]', text=re.compile('ジャンル:'))
        genre =(i.text.strip() for i in genre_doc.find_next('p').select('a')) if genre_doc else ''
        #genre =(i.text.strip() for i in soup.find('p', text="類別:").find_next('p').select('span')) if soup.find('p', text="類別:") else ''
        genre_text = ''
        for tex in genre:
            # genre_text += '%s   ' % tex 
            genre_text += '%s\n' % tex 
        categories['類別'] = genre_text

        actor_doc = soup.select('span[onmouseover^="hoverdiv"]')
        actor = (i.text.strip() for i in actor_doc) if actor_doc else ''
        #actor = (i.text.strip() for i in soup.select('span[onmouseover^="hoverdiv"]')) if soup.select('span[onmouseover^="hoverdiv"]') else ''
        actor_text = ''
        for tex in actor:
            # actor_text += '%s   ' % tex 
            actor_text += '%s\n' % tex 
        categories['演員'] = actor_text
        
        #网址加入字典
        url = soup.select('link[hreflang="ja"]')[0]['href']
        categories['URL'] = url      

    #将磁力链接加入字典
    magnet_html = downloader.get_html(_get_cili_url(soup), Referer_url=url)
    magnet = _parser_magnet(magnet_html)
    categories['磁力链接'] = magnet

    #封面链接加入字典
    if soup.select_one('a[class="bigImage"]').find('img')['src'][0] == '/':
        parsed = urlparse(url)
        bigimage_url = parsed.scheme+'://'+parsed.netloc+soup.select_one('a[class="bigImage"]').find('img')['src']
    else:
        bigimage_url = soup.select_one('a[class="bigImage"]').find('img')['src']
    categories['封面'] = bigimage_url
    
    # 下载封面图片
    if bigimage_url and categories.get('識別碼'):
        code_name = categories['識別碼']
        # 创建基于识别码的文件夹
        save_dir = os.path.join('images', 'covers', code_name)
        ext = get_file_extension(bigimage_url)
        cover_filename = f"{code_name}_cover.{ext}"
        
        # 下载封面
        local_cover_path = download_image(bigimage_url, save_dir, cover_filename)
        if local_cover_path:
            categories['本地封面路径'] = local_cover_path
 

    #標題加入字典
    title = soup.find('title').text.strip().replace(" - JavBus","")
    categories['標題'] = title
    
    return categories


