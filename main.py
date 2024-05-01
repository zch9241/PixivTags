import json
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import logging
from concurrent.futures import ThreadPoolExecutor,wait,ALL_COMPLETED

from decrypt import *


UID :str = '71963925'
ANALYSE_ILLUST_THREADS: int = 10

logger = logging.getLogger('logger')

handler = logging.StreamHandler()

logger.setLevel(logging.DEBUG)
handler.setLevel(logging.DEBUG)

formatter = logging.Formatter("[%(asctime)s %(name)s %(thread)d %(funcName)s] %(levelname)s %(message)s")
handler.setFormatter(formatter)

logger.addHandler(handler)


# 解密cookies
logger.info(f'正在解密cookies---[更新cookies: {update_cookies}]')

cookie = []
cookies = query_cookie("www.pixiv.net")
for data in cookies:
    cookie.append({'name': data[1], 'value': chrome_decrypt(data[2]), 'domain': data[0]})

cookies = query_cookie(".pixiv.net")
for data in cookies:
    cookie.append({'name': data[1], 'value': chrome_decrypt(data[2]), 'domain': data[0]})

logger.info(f'解密完成，数量 {len(cookie)}')
# 

def analyse_bookmarks(rest_flag = 2, limit = 100) -> list:
    '''
    # 解析收藏接口
    - 接口名称: https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset=&limit=&rest=&lang=
    - `:return`: 所有需要调用的接口
    - `rest_flag`: 可见设置 (= 0,1,2),分别对应show(公开),hide(不公开),show+hide [默认为2]
    - `limit`: 每次获取的pid数目 (= 1,2,3,...,100) [默认为100(最大)]
    '''
    rest_dict = {0: ['show'],1: ['hide'], 2: ['show', 'hide']}
    rest = rest_dict[rest_flag]
    
    offset = 0
    limit = 100

    # 解析作品数量
    def analyse_total():
        testurl_show = f'https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset=0&limit=1&rest=show&lang=zh'
        testurl_hide = f'https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset=0&limit=1&rest=hide&lang=zh'
        
        logger.debug('创建driver实例')

        options = webdriver.ChromeOptions()
        options.add_argument('log-level=3')
        options.add_argument('--disable-gpu')
        options.add_argument('--headless')
        driver = webdriver.Chrome(options = options)


        logger.debug('访问rest=show')
        driver.get(testurl_show)
        
        logger.debug('添加cookies')
        for cok in cookie:
            driver.add_cookie(cok)
        driver.refresh()
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located)
        logger.debug('接口所有元素加载完毕，准备解析...')

        resp: dict = json.loads(
            driver.find_element(
                By.CSS_SELECTOR, 'body > pre'
                ).text
            )
        total_show = resp['body']['total']

        
        logger.debug('访问rest=hide')
        driver.get(testurl_hide)
        
        logger.debug('添加cookies')
        for cok in cookie:
            driver.add_cookie(cok)
        driver.refresh()
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located)
        logger.debug('接口所有元素加载完毕，准备解析...')

        resp: dict = json.loads(
            driver.find_element(
                By.CSS_SELECTOR, 'body > pre'
                ).text
            )
        total_hide = resp['body']['total']
        driver.close()

        logger.info(f'解析total字段完成, show数量: {total_show}, hide数量: {total_hide}')
        
        return total_show, total_hide
    total_show, total_hide = analyse_total()

    # 格式化URLs
    urls = []
    for r in rest:
        if r == 'show':
            total = total_show
            k = total//limit            # 整步步数
            l = total - k*limit + 1     # 剩余部分对应的limit
            s = 0                       # 计数器
            while k > s:
                urls.append(f'https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset={s*limit}&limit={limit}&rest=show&lang=zh')
                s+=1
            urls.append(f'https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset={s*limit}&limit={l}&rest=show&lang=zh')
        elif r == 'hide':
            total = total_hide
            k = total//limit            # 整步步数
            l = total - k*limit + 1     # 剩余部分对应的limit
            s = 0                       # 计数器
            while k > s:
                urls.append(f'https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset={s*limit}&limit={limit}&rest=hide&lang=zh')
                s+=1
            urls.append(f'https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset={s*limit}&limit={l}&rest=hide&lang=zh')
    
    logger.info(f'解析接口URL完成, 数量: {len(urls)}')
    #print(urls)
    return urls

def analyse_illusts_i(url) -> list:
    '''
    解析所有插画的信息
    - i就是individual的意思, 子线程
    -  `url`: 接口URL
    - `:return`: 插画信息的列表
    '''
    illustdata = []
    
    options = webdriver.ChromeOptions()
    options.add_argument('log-level=3')
    options.add_argument('--disable-gpu')
    options.add_argument('--headless')
    driver = webdriver.Chrome(options = options)
    
    driver.get(url)
    for cok in cookie:
        driver.add_cookie(cok)
    driver.refresh()
    
    WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located)
    #logger.debug('接口所有元素加载完毕，准备解析...')
    
    # 解析每张插画的信息，添加到列表
    resp: dict = json.loads(
        driver.find_element(
            By.CSS_SELECTOR, 'body > pre'
            ).text
        )
    for ildata in resp['body']['works']:
        illustdata.append(ildata)

    return illustdata

def analyse_illusts_m(th_count) -> list:
    '''
    analyse_illusts_i的主线程, 整合信息
    - `th_count`: 线程数量
    - 需要URLs变量
    '''
    illdata = []
    all_th = []
    logger.info(f'创建线程池，线程数量: {th_count}')
    with ThreadPoolExecutor(max_workers = th_count) as pool:
        for u in URLs:
            all_th.append(pool.submit(analyse_illusts_i, u))
            
        wait(all_th, return_when=ALL_COMPLETED)
        logger.info('所有线程运行完成')
        # 获取各线程返回值
        for t_res in all_th:
            illdata.extend(t_res.result())
        logger.info(f'所有插画信息获取完成, 长度: {len(illdata)}')

    return illdata

#URLs = analyse_bookmarks()
URLs = ['https://www.pixiv.net/ajax/user/71963925/illusts/bookmarks?tag=&offset=0&limit=5&rest=show&lang=zh']
illdata = analyse_illusts_m(ANALYSE_ILLUST_THREADS)
a=1




