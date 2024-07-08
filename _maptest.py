import json
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import logging
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED
from time import sleep
from urllib import parse
import sys
import traceback
import re

from decrypt import *

ANALYSE_ILLUST_THREADS: int = 10
WRITERAW_TO_DB_THREADS: int = 10
WRITE_TAGS_TO_DB_THREADS: int = 10
FETCH_TRANSLATED_TAG_THREADS: int = 10
WRITE_TRANSTAGS_TO_DB_THREADS: int = 10
TRANSTAG_RETURN_THREADS: int = 10
UID: str = '71963925'

CWD = os.getcwd()
SQLPATH = CWD + '\src\illdata.db'

logger = logging.getLogger('logger')

handler = logging.StreamHandler()

logger.setLevel(logging.DEBUG)
handler.setLevel(logging.DEBUG)

formatter = logging.Formatter("[%(asctime)s %(name)s %(thread)d %(funcName)s] %(levelname)s %(message)s")
handler.setFormatter(formatter)

logger.addHandler(handler)



def mapping() -> dict:
    '''
    将illust表中存储的数据转换为tag对pid的映射
    '''
    logger.info('开始构建tag对pid的映射')
    
    con = sqlite3.connect(SQLPATH)
    cur = con.cursor()
    cur.execute('SELECT pid,transtag FROM illusts')
    res = cur.fetchall()
    con.close()
    
    pid__tag = []   # pid对应的tag
    tag__pid = {}   # tag对应的pid
    
    def formater(pid, string:str) -> dict:
        '''
        将数据库中的数据格式化
        来自文心一言
        '''
        s = string.strip('"').replace('\\', '').replace('\"', '"') 
        matches = re.findall(r'"([^"]+?)"', s)
        return {pid: matches}
    for r in res:
        pid__tag.append(formater(r[0], r[1]))
        
    logger.info(f'从数据库获取的数据解析完成，共有 {len(pid__tag)} 个pid')

    for p in pid__tag:
        for key, value_list in p.items():
            for value in value_list:
                if value in tag__pid:
                    # 如果值已经存在，将原字典的键添加到该值的列表中
                    tag__pid[value].append(key)
                else:
                    # 如果值不存在，创建一个新的列表并添加原字典的键
                    tag__pid[value] = [key]
    logger.info(f'映射构建完成，共 {len(tag__pid)} 对')
    return tag__pid
mapping()

