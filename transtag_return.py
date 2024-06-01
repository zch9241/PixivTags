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


def transtag_return_i(r0):
    con = sqlite3.connect(SQLPATH)
    cur = con.cursor()


    pid, jptag0, transtag0, is_translated0, is_private0 = r0
    jptags = eval(jptag0)
    l = [''] * len(jptags)
    for i in range(len(jptags)):
        cur.execute('''
                    SELECT * FROM tags
                    ''')
        resp = cur.fetchall()
        for r in resp:
            jptag, transtag = r
            if jptag == jptags[i]:
                l[i] = transtag
    cur.execute(f'''
                UPDATE illusts SET transtag = "{l}" WHERE pid = {pid}
                ''')
    con.commit()
    # logger.debug(l)
def transtag_return_m(th_count):
    '''
    上传翻译后的tags至illust表
    '''
    all_th = []
    logger.info(f'创建线程池，线程数量: {th_count}')
    with ThreadPoolExecutor(max_workers = th_count) as pool:
        con = sqlite3.connect(SQLPATH)
        cur = con.cursor()
        cur.execute('''
                    SELECT * FROM illusts
                    ''')
        resp0 = cur.fetchall()
        for r0 in resp0:
            all_th.append(pool.submit(transtag_return_i, r0))
        
        wait(all_th, return_when = ALL_COMPLETED)
        for th in all_th:
            if th.exception():
                logger.error(f'运行时出现错误: {th.exception()}')
    logger.info('翻译后的tag已提交')

transtag_return_m(10)
