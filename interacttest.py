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
from difflib import get_close_matches

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
        '''
        s = string.strip('"').replace('\\', '').replace('\"', '"').strip()
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

map_result = mapping()


logger.info('数据操作全部完成')
logger.info('进入交互模式')


def _help():
    print('''
这是交互模式的使用说明
`help`: 显示帮助
`exit`: 退出交互模式
`search`: 搜索关键词
`list`: 列出所有关键词(危险操作)
`hot`: 列出出现最多的10个关键词
          ''')
def _search():
    key = ''
    while key == '':
        print('输入关键词以进行查询:')
        key = input()
        
        keys = list(map_result.keys())
        target_keys = get_close_matches(key, keys, n = 8, cutoff = 0.1)
        if len(target_keys) > 1:
            print(f'可能的结果: {target_keys}')
            target_key = input('请选择其中一个结果: ')
            while not target_key in target_keys:
                print('未匹配, 请重新选择: ')
            print(f'pids: {map_result[target_key]}')
        else:
            target_key = target_keys[0]
            print(f'pids: {map_result[target_key]}')
def _exit():
    logger.info('程序执行完成')
    exit()
def _list():
    for r in map_result:
        print(r)
def _hot():
    i = 0
    count = {}
    for r in map_result:
        count[r] = len(map_result[r])
    counts = sorted(count.values(), reverse = True)[:9]
    
    for k in count.keys():
        v = count[k]
        if i < 10:
            if v in counts:
                print(f'{k}: {v}')
                i+=1
        else:
            break


reserve_words = {'help': '_help()', 'exit': '_exit()', 'search': '_search()', 'list': '_list()', 'hot': '_hot()'}

_help()
while True:
    print('>>>', end = '')
    search = input()
    if search in reserve_words:
        eval(reserve_words[search])
    else:
        print('未知的指令')

