import json
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import logging
from concurrent.futures import ThreadPoolExecutor,wait,ALL_COMPLETED
from urllib import parse


from decrypt import *


UID :str = '71963925'
ANALYSE_ILLUST_THREADS: int = 10
WRITERAW_TO_DB_THREADS: int = 10
WRITE_TAGS_TO_DB_THREADS: int = 10
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

trans = fetch_translated_tag_m(10)
#trans = [{'オリジナル': '原创'}, {'拾ってください': 'None'}, {'鯛焼き': 'None'}, {'かのかり': 'Rent-A-Girlfriend'}, {'彼女、お借りします5000users入り': '租借女友5000收藏'}, {'女の子': '女孩子'}, {'桜沢墨': '樱泽墨'}, {'緑髪': 'green hair'}, {'猫耳': 'cat ears'}, {'猫': 'cat'}, {'天使': 'angel'}, {'白ニーソ': '白色过膝袜'}, {'制服': 'uniform'}, {'彼女、お借りします': 'Rent-A-Girlfriend'}, {'アズールレーン': '碧蓝航线'}, {'ぱんつ': '胖次'}, {'オリジナル1000users入り': '原创1000users加入书籤'}, {'タシュケント': '塔什干'}, {'ハグ': '拥抱'}, {'タシュケント(アズールレーン)': '塔什干（碧蓝航线）'}, {'アズールレーン10000users入り': '碧蓝航线10000收藏'}, {'巨乳': 'large breasts'}, {'イラスト': '插画'}]
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
write_transtags_to_db_m(10)

