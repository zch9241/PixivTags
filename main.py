import json
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import logging
from concurrent.futures import ThreadPoolExecutor,wait,ALL_COMPLETED
from time import sleep
from urllib import parse

from decrypt import *

ANALYSE_ILLUST_THREADS: int = 10
WRITERAW_TO_DB_THREADS: int = 10
WRITE_TAGS_TO_DB_THREADS: int = 10
FETCH_TRANSLATED_TAG_THREADS: int = 10
WRITE_TRANSTAGS_TO_DB_THREADS: int = 10
UID :str = '71963925'

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

    sleep(0.1)
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

def writeraw_to_db_i(illdata) -> list:
    '''
    `:return`: 状态
    '''
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
        status = ['0']
    elif olddata[0] == newdata:
        logger.debug('数据重复，无需添加')
        status = ['1']
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
            status = ['2']
    con.close()
    return status

def writeraw_to_db_m(th_count):
    '''
    将所有tag提交至数据库
    - 需要`illdata`
    '''
    all_th = []
    result = []
    logger.info(f'创建线程池，线程数量: {th_count}')
    with ThreadPoolExecutor(max_workers = th_count) as pool:
        while len(illdata) > 0:
            i = illdata.pop(0)
            all_th.append(pool.submit(writeraw_to_db_i, i))
        wait(all_th, return_when=ALL_COMPLETED)
        for th in all_th:
            result.extend(th.result())
            if th.exception():
                logger.error(f'运行时出现错误: {th.exception()}')
        logger.info(f"所有线程运行完成, 添加: {result.count('0')}  修改: {result.count('2')}  跳过: {result.count('1')}")

def write_tags_to_db_i(tag) -> list:
    '''
    提交所有未翻译的jptag
    `:return`: 状态
    '''
    con = sqlite3.connect(SQLPATH)
    cur = con.cursor()
    # 提交元素
    try:
        cur.execute(f'''
                INSERT INTO tags VALUES ('{tag}','')
                ''')
        con.commit()
        status = ['0']
    except sqlite3.IntegrityError as e:
        #logger.debug(f'出现重复tag: {e}', exc_info = True)
        status = ['1']
        pass
    con.close()
    return status

def write_tags_to_db_m(th_count):
    '''
    提交原始tags
    '''
    logger.info(f'创建线程池，线程数量: {th_count}')
    with ThreadPoolExecutor(max_workers = th_count) as pool:
        tags = []
        all_th = []
        result = []
        
        con = sqlite3.connect(SQLPATH)
        cur = con.cursor()
        
        cur.execute('''
                SELECT * FROM illusts WHERE is_translated = 0
                ''')
        res = cur.fetchall()    # 数据结构: [(行1), (行2), ...], 每行: (值1, ...)
        con.close()
        for r in res:
            il_tag = eval(r[1]) # 单双引号问题, 不能用json.loads()
            tags.extend(il_tag)
        # 移除重复元素
        tags = list(set(tags))
        
        while len(tags) > 0:
            tag = tags.pop(0)
            all_th.append(pool.submit(write_tags_to_db_i, tag))
        wait(all_th, return_when = ALL_COMPLETED)
        for th in all_th:
            result.extend(th.result())
            
            if th.exception():
                logger.error(f'运行时出现错误: {th.exception()}')
        logger.info(f"所有线程运行完成, 添加: {result.count('0')}  跳过: {result.count('1')}")

def fetch_translated_tag_i(j, priority = None) -> dict:
    '''
    发送请求获取翻译后的tag
    - `j`: tag的名称
    - `priority`: 语言优先级
    - `:return` dict : {'原tag': '翻译后的tag'}
    '''
    priority = ['zh', 'en', 'zh_tw']
    jf = parse.quote(j) # 转为URL编码
    
    options = webdriver.ChromeOptions()
    options.add_argument('log-level=3')
    options.add_argument('--disable-gpu')
    options.add_argument('--headless')
    driver = webdriver.Chrome(options = options)
    driver.get(f'https://www.pixiv.net/ajax/search/tags/{jf}?lang=zh')
    for cok in cookie:
        driver.add_cookie(cok)
    driver.refresh()
    WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located)

    resp: dict = json.loads(
        driver.find_element(
            By.CSS_SELECTOR, 'body > pre'
            ).text
        )
    try:
        trans: dict = resp['body']['tagTranslation'][j]   #包含所有翻译语言的dict
        lans = trans.keys()
        for l in priority:
            if l in lans and trans[l] != '':
                transtag = trans[l]
                break
        result = {j: transtag}

    except UnboundLocalError as e:
        logger.info('无此tag的翻译')
        result = {j: 'None'}
    return result

def fetch_translated_tag_m(th_count) -> list:
    jptags = []
    result = []
    
    con = sqlite3.connect(SQLPATH)
    cur = con.cursor()
    # 只找出未翻译的tag
    cur.execute('''
                SELECT * FROM tags WHERE transtag == ''
                ''')
    res = cur.fetchall()
    cur.close()

    for r in res:
        (jptag, _) = r
        jptags.append(jptag)
    logger.info(f'已从数据库获取 {len(jptags)} 个tag')
    logger.info(f'创建线程池，线程数量: {th_count}')

    with ThreadPoolExecutor(max_workers = th_count) as pool:
        all_th = []
        for j in jptags:
            all_th.append(pool.submit(fetch_translated_tag_i, j))

        wait(all_th, return_when = ALL_COMPLETED)
        for th in all_th:
            if th.result != None:
                result.append(th.result())
            if th.exception():
                logger.error(f'运行时出现错误: {th.exception()}')
        s = 0
        for r in result:
            if list(r.values())[0] == 'None':
                s += 1
        logger.info(f'tag翻译获取完成, 共 {len(result)} 个, 无翻译 {s} 个')
    return result

def write_transtags_to_db_i(tran: dict):
    '''
    `tran`: 需要提交的tags (jp:tr)
    '''
    con = sqlite3.connect(SQLPATH)
    cur = con.cursor()
    cur.execute(f'''
                UPDATE tags SET transtag = '{list(tran.values())[0]}' WHERE jptag = '{list(tran.keys())[0]}'
                ''')
    con.commit()
    con.close()

def write_transtags_to_db_m(th_count):
    '''
    将翻译后的tags提交至数据库tags
    - 需要trans变量
    '''
    all_th = []
    logger.info(f'创建线程池，线程数量: {th_count}')
    with ThreadPoolExecutor(max_workers = th_count) as pool:
        for t in trans:
            all_th.append(pool.submit(write_transtags_to_db_i, t))
        wait(all_th, return_when = ALL_COMPLETED)
        for th in all_th:
            if th.exception():
                logger.error(f'运行时出现错误: {th.exception()}')
    logger.info('翻译后的tag已提交')



URLs = analyse_bookmarks()
#debug:
#URLs = ['https://www.pixiv.net/ajax/user/71963925/illusts/bookmarks?tag=&offset=0&limit=5&rest=show&lang=zh']


illdata = analyse_illusts_m(ANALYSE_ILLUST_THREADS)
#debug:
#illdata = [{'id': '79862254', 'title': 'タシュケント♡', 'illustType': 0, 'xRestrict': 0, 'restrict': 0, 'sl': 2, 'url': 'https://i.pximg.net/c/250x250_80_a2/img-master/img/2020/03/03/09/31/57/79862254_p0_square1200.jpg', 'description': '', 'tags': ['タシュケント', 'アズールレーン', 'タシュケント(アズールレーン)', 'イラスト', '鯛焼き', 'アズールレーン10000users入り'], 'userId': '9216952', 'userName': 'AppleCaramel', 'width': 1800, 'height': 2546, 'pageCount': 1, 'isBookmarkable': True, 'bookmarkData': {'id': '25192310391', 'private': False}, 'alt': '#タシュケント タシュケント♡ - AppleCaramel的插画', 'titleCaptionTranslation': {'workTitle': None, 'workCaption': None}, 'createDate': '2020-03-03T09:31:57+09:00', 'updateDate': '2020-03-03T09:31:57+09:00', 'isUnlisted': False, 'isMasked': False, 'aiType': 0, 'profileImageUrl': 'https://i.pximg.net/user-profile/img/2022/10/24/02/12/49/23505973_7d9aa88560c5115b85cc29749ed40e28_50.jpg'},
#{'id': '117717637', 'title': 'おしごと終わりにハグしてくれる天使', 'illustType': 0, 'xRestrict': 0, 'restrict': 0, 'sl': 4, 'url': 'https://i.pximg.net/c/250x250_80_a2/custom-thumb/img/2024/04/10/17/30/02/117717637_p0_custom1200.jpg', 'description': '', 'tags': ['オリジナル', '女の子', '緑髪', '天使', 'ハグ', '巨乳', 'ぱんつ', 'オリジナル1000users入り'], 'userId': '29164302', 'userName': '緑風マルト🌿', 'width': 1296, 'height': 1812, 'pageCount': 1, 'isBookmarkable': True, 'bookmarkData': {'id': '25109862018', 'private': False}, 'alt': '#オリジナル おしごと終わりにハグしてくれる天使 - 緑風マルト🌿的插画', 'titleCaptionTranslation': {'workTitle': None, 'workCaption': None}, 'createDate': '2024-04-10T17:30:02+09:00', 'updateDate': '2024-04-10T17:30:02+09:00', 'isUnlisted': False, 'isMasked': False, 'aiType': 1, 'profileImageUrl': 'https://i.pximg.net/user-profile/img/2024/01/25/15/56/10/25434619_c70d86172914664ea2b15cec94bc0afd_50.png'},
#{'id': '84450882', 'title': 'ネコ耳墨ちゃん🐈', 'illustType': 0, 'xRestrict': 0, 'restrict': 0, 'sl': 2, 'url': 'https://i.pximg.net/c/250x250_80_a2/img-master/img/2020/09/18/19/44/35/84450882_p0_square1200.jpg', 'description': '', 'tags': ['彼女、お借りします', 'かのかり', '桜沢墨', '猫', '猫耳', '制服', '白ニーソ', '拾ってください', '彼女、お借りします5000users入り'], 'userId': '38436050', 'userName': 'ゆきうなぎ＠土曜東ス88a', 'width': 2894, 'height': 4093, 'pageCount': 1, 'isBookmarkable': True, 'bookmarkData': {'id': '24948220443', 'private': False}, 'alt': '#彼女、お借りします ネコ耳墨ちゃん🐈 - ゆきうなぎ＠土曜東ス88a的插画', 'titleCaptionTranslation': {'workTitle': None, 'workCaption': None}, 'createDate': '2020-09-18T19:44:35+09:00', 'updateDate': '2020-09-18T19:44:35+09:00', 'isUnlisted': False, 'isMasked': False, 'aiType': 0, 'profileImageUrl': 'https://i.pximg.net/user-profile/img/2020/02/22/00/11/25/17966339_a51ca7e8a3aca581fc87021488e21479_50.jpg'},
#]


writeraw_to_db_m(WRITERAW_TO_DB_THREADS)
write_tags_to_db_m(WRITE_TAGS_TO_DB_THREADS)


trans = fetch_translated_tag_m(FETCH_TRANSLATED_TAG_THREADS)
#debug:
#trans = [{'オリジナル': '原创'}, {'拾ってください': 'None'}, {'鯛焼き': 'None'}, {'かのかり': 'Rent-A-Girlfriend'}, {'彼女、お借りします5000users入り': '租借女友5000收藏'}, {'女の子': '女孩子'}, {'桜沢墨': '樱泽墨'}, {'緑髪': 'green hair'}, {'猫耳': 'cat ears'}, {'猫': 'cat'}, {'天使': 'angel'}, {'白ニーソ': '白色过膝袜'}, {'制服': 'uniform'}, {'彼女、お借りします': 'Rent-A-Girlfriend'}, {'アズールレーン': '碧蓝航线'}, {'ぱんつ': '胖次'}, {'オリジナル1000users入り': '原创1000users加入书籤'}, {'タシュケント': '塔什干'}, {'ハグ': '拥抱'}, {'タシュケント(アズールレーン)': '塔什干（碧蓝航线）'}, {'アズールレーン10000users入り': '碧蓝航线10000收藏'}, {'巨乳': 'large breasts'}, {'イラスト': '插画'}]


write_transtags_to_db_m(WRITE_TRANSTAGS_TO_DB_THREADS)


a=1




