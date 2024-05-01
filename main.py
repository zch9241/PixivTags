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
CWD = os.getcwd()
SQLPATH = CWD + '\src\illdata.db'

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
def writeraw_to_db_i(illdata):
    # 一个线程对应一个connection
    con = sqlite3.connect(SQLPATH)
    cursor = con.cursor()
    # 新数据
    pid = int(illdata['id'])
    jptag = str(illdata['tags'])
    transtag = '0'
    is_translated = 0
    is_private_b = illdata['bookmarkData']['private']
    if is_private_b == False:
        is_private = 0
    elif is_private_b == True:
        is_private = 1
    
    newdata = (pid, jptag, transtag, is_translated, is_private)
    data_to_modify = [0,0,0,0,0]
    var = {0:['pid',pid], 1:['jptag',jptag], 2:['transtag',transtag], 
           3:['is_translated',is_translated], 4:['is_private',is_private]}
    
    # 先查询已有信息，再判断是否需要修改
    cursor.execute(f'''
                   SELECT * FROM illusts WHERE pid = {pid}
                   ''')
    olddata: list = cursor.fetchall()
    # 比较信息, 将不同之处添加至修改位置列表
    if olddata == []:     # 无信息
        logger.debug('添加新信息')
        cursor.execute(f'''
                       INSERT INTO illusts VALUES ({pid},"{jptag}",{transtag},{is_translated},{is_private})
                       ''')
        con.commit()
    elif olddata[0] == newdata:
        logger.debug('数据重复，无需添加')
        pass
    else:
        for i in range(len(olddata[0])):
            if olddata[0][i] != newdata[i]:
                data_to_modify[i] = 1
        for i in range(len(data_to_modify)):
            if data_to_modify[i] == 1 and i == 1:    #只修改jptag和is_private值
                # logger.debug('更新jptag数据, 修改is_translated值')
                # 下面这里要加个""才行
                cursor.execute(f'''
                                UPDATE illusts SET {var[1][0]} = "{var[1][1]}" where pid = {pid}
                                ''')
                con.commit()
                cursor.execute(f'''
                                UPDATE illusts SET {var[3][0]} = {var[3][1]} where pid = {pid}
                                ''')
                con.commit()
                
            elif data_to_modify[i] == 1 and i == 4:
                #logger.debug('更新is_privated数据')
                cursor.execute(f'''
                                UPDATE illusts SET {var[4][0]} = {var[4][1]} where pid = {pid}
                                ''')
                con.commit()

    con.close()


def writeraw_to_db_m(th_count):
    '''
    将所有tag提交至数据库
    '''
    all_th = []
    logger.info(f'创建线程池，线程数量: {th_count}')
    with ThreadPoolExecutor(max_workers = th_count) as pool:
        while len(illdata) > 0:
            i = illdata.pop(0)
            all_th.append(pool.submit(writeraw_to_db_i, i))
        wait(all_th, return_when=ALL_COMPLETED)
        for th in all_th:
            if th.exception():
                logger.warning(f'运行时出现错误: {th.exception()}')
        logger.info('所有线程运行完成')

writeraw_to_db_m(10)
a=1




