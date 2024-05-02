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
WRITERAW_TO_DB_THREADS: int = 10
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

write_tags_to_db_m(10)


a=1