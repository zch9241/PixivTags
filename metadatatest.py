import json
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import logging
import threading
from concurrent.futures import ThreadPoolExecutor,wait,ALL_COMPLETED,FIRST_COMPLETED, as_completed

from decrypt import *


UID :str = '71963925'


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




URLs = ['https://www.pixiv.net/ajax/user/71963925/illusts/bookmarks?tag=&offset=0&limit=5&rest=show&lang=zh', 
        'https://www.pixiv.net/ajax/user/71963925/illusts/bookmarks?tag=&offset=5&limit=5&rest=show&lang=zh', 
        'https://www.pixiv.net/ajax/user/71963925/illusts/bookmarks?tag=&offset=10&limit=5&rest=show&lang=zh', 
        'https://www.pixiv.net/ajax/user/71963925/illusts/bookmarks?tag=&offset=15&limit=5&rest=show&lang=zh']


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
    logger.debug('接口所有元素加载完毕，准备解析...')
    
    # 解析每张插画的信息，添加到列表
    resp: dict = json.loads(
        driver.find_element(
            By.CSS_SELECTOR, 'body > pre'
            ).text
        )
    for ildata in resp['body']['works']:
        illustdata.append(ildata)

    return illustdata

# l = analyse_illusts_i()

def analyse_illusts_m(th_count) -> list:
    '''
    analyse_illusts_i的主线程, 整合信息
    - `th_count`: 线程数量
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
if __name__ == '__main__':
     i = analyse_illusts_m(2)
