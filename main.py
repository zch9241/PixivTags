# PixivTags Version 1.0
# 
# AUTHOR: zch9241
# 
# COPYRIGHT NOTICE  
# 
# Copyright (c) 2024-2025, zch9241. All rights reserved.  
# 
# This source code is provided "AS IS" without any warranty of any kind.  
# You may use this source code for any purpose, provided that you do not violate any applicable laws or regulations. 
# This software is for personal and educational use only and may not be used for any commercial purpose. Without the express written consent of the author, no one is permitted to sell or lease this software or its derivative works in any form.  
#  
# If you have any questions or need further clarification, please contact:  
# [zch2426936965@gmail.com]
# 

# TODO:
# 优化查询功能
# 为插画添加更多元数据
# 异步


# standard-libs
import base64
from concurrent.futures import ThreadPoolExecutor, wait, as_completed, ALL_COMPLETED
import datetime
from difflib import get_close_matches
import inspect
import json
import logging
import os
import pdb
import re
import shutil
import sqlite3
import sys
import threading
import time
import traceback
from urllib import parse

# site-packages
import pandas as pd
from playwright.sync_api import sync_playwright
import psutil
from tqdm import tqdm
from win10toast import ToastNotifier



from src import config


# 常量初始化
ANALYSE_ILLUST_THREADS = config.ANALYSE_ILLUST_THREADS
WRITERAW_TO_DB_THREADS = config.WRITERAW_TO_DB_THREADS
WRITE_TAGS_TO_DB_THREADS = config.WRITE_TAGS_TO_DB_THREADS
FETCH_TRANSLATED_TAG_THREADS = config.FETCH_TRANSLATED_TAG_THREADS
WRITE_TRANSTAGS_TO_DB_THREADS = config.WRITE_TRANSTAGS_TO_DB_THREADS
TRANSTAG_RETURN_THREADS = config.TRANSTAG_RETURN_THREADS
UID = config.UID
CHROME_PATH = config.CHROME_PATH
COOKIE_EXPIRED_TIME = config.COOKIE_EXPIRED_TIME

CWD = os.getcwd()
SQLPATH = CWD + r'\src\illdata.db'
COOKIE_PATH = CWD + r'\src\cookies.json'
COOKIE_TIME_PATH = CWD + r'\src\cookies_modify_time'
TAG_LOG_PATH = CWD + r'\logs\tag\content.log'

# 交互模式
mode_select = """
请选择模式: 
1 = 更新tags至本地数据库
2 = 基于本地数据库进行插画搜索
3 = 向本地数据库提交历史运行时备份的有效数据(在程序报错时使用)
4 = 退出
"""
reserve_words = {'help': '_help()', 'exit': '_exit()',
                 'search': '_search()', 'list': '_list()', 'hot': '_hot()',
                 'debug': '_debug()'}
help_text = """
这是交互模式的使用说明
`help`: 显示帮助
`exit`: 退出主程序
`search`: 搜索tags
`list`: 列出所有tags(危险操作)
`hot`: 列出出现最多的tags
"""

# 日志初始化
logger = logging.getLogger('logger')
handler = logging.StreamHandler()
logger.setLevel(logging.DEBUG)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "[%(asctime)s %(name)s %(thread)d %(funcName)s] %(levelname)s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# Toast初始化
toaster = ToastNotifier()

# 数据库初始化
conn = sqlite3.connect(SQLPATH)  
cursor = conn.cursor()  
cursor.execute('''
CREATE TABLE IF NOT EXISTS "illusts" (
	"pid"	INTEGER,
	"jptag"	TEXT,
	"transtag"	TEXT,
	"is_translated"	INTEGER,
	"is_private"	INTEGER,
	PRIMARY KEY("pid")
)
               ''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS "removed" (
	"pid"	INTEGER UNIQUE
)
               ''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS "tags" (
	"jptag"	TEXT,
	"transtag"	TEXT,
	UNIQUE("jptag")
)
               ''')
conn.commit()
cursor.close()
conn.close()

def handle_exception(logger: logging.Logger, func_name: str = None, in_bar = True):
    """对抛出错误的通用处理

    Args:
        logger (logging.Logger): logger
        func_name (str, optional): 抛出错误的函数名(配合var_check()使用). Defaults to None.
        in_bar(bool, optional): 原函数中是否打印进度条(tqdm)，防止输出错乱. Defaults to True.
    """
    exc_type, exc_value, tb = sys.exc_info()
    # 获取完整的堆栈跟踪信息
    tb_list = traceback.format_tb(tb)
    ex = "".join(tb_list)
    
    if in_bar == True:
        tqdm.write(f'ERROR {exc_type.__name__}: {exc_value}')
        tqdm.write(f'ERROR {ex}')
    else:
        logger.error(f'{exc_type.__name__}: {exc_value}')
        logger.error(ex)

    if func_name:
        return f'ERROR {func_name}'

# 获取cookies
def get_cookies(rtime: int, forced = False):
    """获取Google Chrome的cookies

    Args:
        rtime (int): cookie更新间隔
        forced (bool): 是否强制更新
    """
    # 判断是否需要更新cookies
    with open(COOKIE_TIME_PATH, 'r') as f:
        data = f.read()
        if data != '':
            modify_time = float(data)
        else:
            modify_time = 0
    relative_time = time.time() - modify_time
    
    if relative_time < rtime and relative_time > 0 and forced is False:
        logger.info(f'无需更新cookies: 距上次更新 {relative_time} 秒')
    else:
        logger.info(f'需要更新cookies: 距上次更新 {relative_time} 秒')

        # 判断Google Chrome是否在运行，是则结束，否则会报错
        def find_process(name):
            "遍历所有进程，查找特定名称的进程"
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if name.lower() in proc.info['name'].lower():
                        return proc
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            return None

        def kill_process(name):
            "查找特定名称的进程并让用户结束"
            proc = find_process(name)
            while proc:
                logger.info(
                    f"找到进程：{proc.info['name']}, PID: {proc.info['pid']}, 请结束进程，否则cookies无法正常获取")
                os.system('pause')
                proc = find_process(name)
        kill_process("chrome.exe")

        # 获取cookies
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(headless=True,
                executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                user_data_dir=os.path.expanduser(
                    os.path.join(os.environ['LOCALAPPDATA'], r'Google\Chrome\User Data'))
                )
            
            with open(r'.\src\cookies.json','w') as f:
                state = {"cookies": browser.cookies('https://www.pixiv.net'), "origins": []}
                f.write(json.dumps(state))
            # 关闭浏览器
            browser.close()
        logger.info('cookies已获取')
        # 更新获取cookie的时间
        with open(COOKIE_TIME_PATH, "w") as f:
            f.write(str(time.time()))


# 数据库相关操作
db_lock = threading.Lock()
def dbexecute(query: str, params: tuple|list[tuple]=None, many=False):  
    """数据库操作

    Args:
        query (str): sql命令
        params (tuple|list[tuple], optional): 查询参数. Defaults to None.
        many (bool, optional): 是否对多行数据进行操作,若将参数设为True,请确保传入的params为list[tuple]类型. Defaults to False.

    Returns:
        list|None: 查询结果（若有）
    """
    res = ''
    with db_lock:  # 确保只有一个线程可以执行这个块  
        conn = sqlite3.connect(SQLPATH)  
        cursor = conn.cursor()  
        try:
            if many is True and type(params) == list and all(isinstance(item, tuple) for item in params):   # 验证list[tuple]
                cursor.executemany(query, params or ())
            elif type(params) == tuple or params is None:
                cursor.execute(query, params or ()) 
            else:
                 raise Exception("传入的params类型校验错误")
            conn.commit()  
            res = cursor.fetchall()
        except Exception:
            handle_exception(logger, inspect.currentframe().f_code.co_name)
            conn.rollback()  
        finally:  
            cursor.close()  
            conn.close()  
    if res != '':
        return res
    else:
        return None


# 获取pixiv上的tags并翻译
class ValCheckError(Exception):  
    def __init__(self):  
        super().__init__('参数校验错误: 上个函数在执行中出现错误')

def var_check(*args):
    '''
    # 检查上个函数执行是否正常
    '''
    for var in args:
        if str(var)[:5] == 'ERROR':
            position = str(var).split(' ')[1]
            logger.error(f'上个函数在执行中出现错误 所在函数:{position}')
            return True


def analyse_bookmarks(rest_flag=2, limit=100) -> list:
    '''
    # 解析收藏接口
    - 接口名称: https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset=&limit=&rest=&lang=
    - `:return`: 所有需要调用的接口
    - `cookie`: pixiv上的cookie
    - `rest_flag`: 可见设置 (= 0,1,2),分别对应show(公开),hide(不公开),show+hide [默认为2]
    - `limit`: 每次获取的pid数目 (= 1,2,3,...,100) [默认为100(最大)]
    '''
    logger.info('正在运行')
    signature = inspect.signature(analyse_bookmarks)
    for param in signature.parameters.values():
        if var_check(eval(param.name)) == 1:
            raise ValCheckError
    try:
        rest_dict = {0: ['show'], 1: ['hide'], 2: ['show', 'hide']}
        rest = rest_dict[rest_flag]

        offset = 0

        # 解析作品数量
        def analyse_total():
            url_show = f'https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset=0&limit=1&rest=show&lang=zh'
            url_hide = f'https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset=0&limit=1&rest=hide&lang=zh'

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True,executable_path=CHROME_PATH)
                context = browser.new_context(storage_state=COOKIE_PATH)
                page = context.new_page()
                
                page.goto(url_show)
                resp: dict = json.loads(
                    page.locator('body > pre').inner_text())
                total_show = resp['body']['total']
                
                page.goto(url_hide)
                resp: dict = json.loads(
                    page.locator('body > pre').inner_text())
                total_hide = resp['body']['total']
                
                browser.close()

            logger.info(f'解析bookmarks完成, 公开数量: {total_show}, 不公开数量: {total_hide}')

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
                    urls.append(
                        f'https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset={s*limit}&limit={limit}&rest=show&lang=zh')
                    s += 1
                urls.append(
                    f'https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset={s*limit}&limit={l}&rest=show&lang=zh')
            elif r == 'hide':
                total = total_hide
                k = total//limit            # 整步步数
                l = total - k*limit + 1     # 剩余部分对应的limit
                s = 0                       # 计数器
                while k > s:
                    urls.append(
                        f'https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset={s*limit}&limit={limit}&rest=hide&lang=zh')
                    s += 1
                urls.append(
                    f'https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset={s*limit}&limit={l}&rest=hide&lang=zh')

        logger.info(f'解析接口URL完成, 数量: {len(urls)}')
        # print(urls)
    except Exception:
        urls = handle_exception(logger, inspect.currentframe().f_code.co_name)
    return urls


def analyse_illusts_i(url) -> list:
    '''
    解析所有插画的信息
    - i就是individual的意思, 子线程
    - `url`: 接口URL
    - `:return`: 插画信息的列表, 忽略的插画数量
    '''
    try:
        illustdata = []
        ignores = 0
        def inner(count):
            nonlocal ignores, illustdata
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True,executable_path=CHROME_PATH)
                    context = browser.new_context(storage_state=COOKIE_PATH)
                    page = context.new_page()

                    page.goto(url)
                    # 解析每张插画的信息，添加到列表
                    resp: dict = json.loads(
                        page.locator('body > pre').inner_text())
                    
                    browser.close()

                idata = resp['body']['works']
                for ildata in idata:
                    if ildata['isMasked'] is True:
                        tqdm.write(f"INFO 此插画已被隐藏，忽略本次请求 pid = {ildata['id']}")
                        ignores += 1
                    else:
                        illustdata.append(ildata)
            except Exception:
                handle_exception(logger, inspect.currentframe().f_code.co_name)
                tqdm.write('INFO 重试')
                if count >= 1:
                    inner(count - 1)
                else:
                    tqdm.write('WARNING 达到最大递归深度')
        inner(10)
            
        return illustdata, ignores
    except Exception as e:
        handle_exception(logger, inspect.currentframe().f_code.co_name)
def analyse_illusts_m(th_count, urls) -> list:
    '''
    analyse_illusts_i的主线程, 整合信息
    - `th_count`: 线程数量
    - `urls`: 请求url列表
    - `cookie`: pixiv上的cookie
    '''
    logger.info('正在运行')
    signature = inspect.signature(analyse_illusts_m)
    for param in signature.parameters.values():
        if var_check(eval(param.name)) == 1:
            raise ValCheckError
    try:
        illdata = []
        all_th = {}
        ignores = 0
        
        logger.info(f'创建线程池，线程数量: {th_count}')
        with ThreadPoolExecutor(max_workers=th_count) as pool:
            for u in urls:
                all_th[u] = pool.submit(analyse_illusts_i, u)
            for _ in tqdm(as_completed(list(all_th.values())), total = len(list(all_th.values()))):
                pass
            logger.info('所有线程运行完成')
            # 获取各线程返回值
            for u, t_res in all_th.items():
                result = t_res.result()
                ill, ign = result
                illdata.extend(ill)
                ignores += ign
                
        logger.info(f'所有插画信息获取完成，长度: {len(illdata)} 忽略数量: {ignores}')
    except Exception:
        illdata = handle_exception(logger, inspect.currentframe().f_code.co_name)
    return illdata


def writeraw_to_db_i(illdata) -> list:
    '''
    `:return`: 状态
    '''
    try:
        # 新数据
        pid = int(illdata['id'])
        jptag = str(illdata['tags'])
        transtag = '0'
        is_translated = 0
        is_private = int(illdata['bookmarkData']['private'])

        # 先查询已有信息，再判断是否需要修改
        sql = f'''SELECT * FROM illusts WHERE pid = {pid}'''
        query_result: list = dbexecute(sql)
        # 比较信息, 将不同之处添加至修改位置列表
        if query_result == []:     # 无信息
            # logger.debug('添加新信息')
            
            #sql = f'''INSERT INTO illusts VALUES ({pid},"{jptag}",{transtag},{is_translated},{is_private})'''
            dbexecute(f"INSERT INTO illusts (pid, jptag, transtag, is_translated, is_private) VALUES (?, ?, ?, ?, ?)", (pid, jptag, transtag, is_translated, is_private))
            status = ['0']

        else:     # 有信息
            # 查询table_info，并从返回值中获取列名
            db_columns = [column_data[1] for column_data in dbexecute('PRAGMA table_info(illusts)')]
            necessary_columns = ['jptag', 'is_private']
            
            # 格式化数据
            newdata = {'jptag': jptag, 'is_private': is_private}
            olddata_ = {}
            olddata: tuple = query_result[0]
            for i in range(len(olddata)):
                if db_columns[i] in necessary_columns:
                    olddata_[db_columns[i]] = olddata[i]
            
            if newdata == olddata_:
                # logger.debug('数据重复，无需添加')
                status = ['1']
            else:
                if olddata_['jptag'] != newdata['jptag']:   # 插画添加了新的tag，删除旧的翻译，更新翻译状态
                    dbexecute('UPDATE illusts SET jptag = ?, transtag = ?, is_translated = ?, is_private = ? WHERE pid = ?',(jptag, '0', 0, is_private, pid))
                else:   # 用户修改了插画隐藏属性
                    dbexecute('UPDATE illusts SET is_private = ? WHERE pid = ?', (is_private, pid))
                status = ['2']

        return status
    except Exception as e:
        handle_exception(logger, inspect.currentframe().f_code.co_name)
def writeraw_to_db_m(th_count, illdata):
    """将插画tag,是否隐藏等属性提交至数据库

    Args:
        th_count (int): 线程数
        illdata (list): 插画详细信息
    """
    logger.info('正在运行')
    signature = inspect.signature(writeraw_to_db_m)
    for param in signature.parameters.values():
        if var_check(eval(param.name)) == 1:
            raise ValCheckError
    try:
        # 删除不在收藏中的插画信息
        pids = [int(i['id']) for i in illdata]
        old_pids = [p[0] for p in dbexecute("SELECT pid FROM illusts")]
        
        set_pids = set(pids)
        set_old_pids = set(old_pids)
        
        intersection = set_pids & set_old_pids # 求交集，交集内是要保留的pid
        set_delete_pids = set_old_pids - intersection
        delete_pids = list(set_delete_pids)
        delete_query = [(p,) for p in delete_pids]
        
        dbexecute('DELETE FROM illusts WHERE pid = ?', delete_query, many = True)
        dbexecute('INSERT INTO removed (pid) VALUES (?)', delete_query, many = True)
        logger.info(f"从数据库转移不在收藏中的插画 {len(delete_pids)} 张")
        
        all_th = []
        result = []
        logger.info(f'创建线程池，线程数量: {th_count}')
        with ThreadPoolExecutor(max_workers=th_count) as pool:
            while len(illdata) > 0:
                i = illdata.pop(0)
                all_th.append(pool.submit(writeraw_to_db_i, i))
            wait(all_th, return_when=ALL_COMPLETED)
            for th in tqdm(as_completed(all_th), total = len(all_th)):
                result.extend(th.result())
            logger.info(
                f"所有线程运行完成, 添加: {result.count('0')}  修改: {result.count('2')}  跳过: {result.count('1')}")
    except Exception:
        handle_exception(logger, inspect.currentframe().f_code.co_name)


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
                INSERT OR IGNORE INTO tags VALUES ('{tag}','')
                ''')
        con.commit()
        status = ['0']
    except sqlite3.IntegrityError as e:
        # logger.debug(f'出现重复tag: {e}', exc_info = True)
        status = ['1']
    except Exception:
        tqdm.write(f'ERROR 数据库操作错误，重试: {sys.exc_info()}')
        status = write_tags_to_db_i(tag)
    con.close()
    return status
def write_tags_to_db_m(th_count):
    '''
    # DEPRECATED
    提交原始tags
    
    能用，但是低效
    '''
    logger.info('正在运行')
    signature = inspect.signature(write_tags_to_db_m)
    for param in signature.parameters.values():
        if var_check(eval(param.name)) == 1:
            raise ValCheckError
    try:
        logger.info(f'创建线程池，线程数量: {th_count}')
        with ThreadPoolExecutor(max_workers=th_count) as pool:
            tags = []
            all_th = []
            result = []

            res = dbexecute('''
                    SELECT jptag FROM illusts
                    ''')

            [tags.extend(eval(r)) for r in res]     # 单双引号问题, 不能用json.loads()
            
            # 移除重复元素
            tags = list(set(tags))
            if len(tags) == 0:
                logger.info('没有需要写入的tag')

            while len(tags) > 0:
                tag = tags.pop(0)
                all_th.append(pool.submit(write_tags_to_db_i, tag))
            wait(all_th, return_when=ALL_COMPLETED)
            for th in tqdm(as_completed(all_th), total = len(all_th)):
                result.extend(th.result())

                if th.exception():
                    logger.error(f'运行时出现错误: {th.exception()}')
            logger.info(
                f"所有线程运行完成, 添加: {result.count('0')}  跳过: {result.count('1')}")
    except Exception:
        handle_exception(logger, inspect.currentframe().f_code.co_name)

def write_rawtags_to_db():
    """
    从数据库中获取所有插画的原始tag，并提交到tags的jptags列
    
    （仅新tag,即还未翻译的tag）
    """
    try:
        logger.info('正在运行')
        
        old_count = dbexecute('SELECT count(*) FROM tags')[0][0]
        
        illust_tags_raw: list[tuple] = dbexecute('SELECT jptag FROM illusts')
        illust_tags = []

        for raw in illust_tags_raw:
            # 由于每张插画都有tag，得把他们全都拆出来
            illust_tag = [tag for tag in eval(raw[0])]
            illust_tags.extend(illust_tag)
        
        # 去重
        illust_tags = list(set(illust_tags))
        illust_tags = [(tag,) for tag in illust_tags]
        logger.info(f'从表illust中获取到 {len(illust_tags)} 个tag(去重后)')

        sql = 'INSERT INTO tags(jptag) VALUES (?) ON CONFLICT DO NOTHING'
        dbexecute(sql, illust_tags, many = True)
        
        new_count = dbexecute('SELECT count(*) FROM tags')[0][0]
        
        logger.info(f'向数据库提交了未翻译的tag，增加了{new_count - old_count} 行')
    except Exception as e:
        handle_exception(logger, inspect.currentframe().f_code.co_name)

def fetch_translated_tag_i(j, priority=None):
    '''
    发送请求获取翻译后的tag
    
    最终将返回值写入.temp/result文件
    
    返回值为失败的tag or None
    
    - `j`: tag的名称
    - `priority`: 语言优先级
    '''
    priority = ['zh', 'en', 'zh_tw']
    get_exception = False
    # 转为URL编码, 一定需要加上safe参数, 因为pixiv有些tag有/, 比如: 挟まれたい谷間/魅惑の谷間
    jf = parse.quote(j, safe='')


    def get(count) -> dict | None:
        '''
        count: 规定最大递归深度
        '''
        nonlocal get_exception
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True,executable_path=CHROME_PATH)
                context = browser.new_context(storage_state=COOKIE_PATH)
                page = context.new_page()
                
                page.goto(f'https://www.pixiv.net/ajax/search/tags/{jf}?lang=zh')
                resp: dict = json.loads(
                    page.locator('body > pre').inner_text()
                )
                browser.close()

            # 运行到此处说明运行成功
            if get_exception is True:   # 函数处于递归中
                get_exception = False   # 重置状态
                tqdm.write(f'INFO tag {j} 重试成功')

            return resp
        except Exception:
            get_exception = True
            tqdm.write(f'ERROR tag {j} 请求tag接口时出错,重试 {sys.exc_info()}')
            time.sleep(1)
            if count >= 1:
                return get(count - 1)
            else:
                tqdm.write(f'WARNING tag {j} 达到最大递归深度, 放弃')
                return None
                
    resp = get(10)

    if resp is None:
        tqdm.write(f'WARNING 服务器返回值不正确 此次请求tag: {j}')
        with open(TAG_LOG_PATH, 'a', encoding = 'utf-8') as f:
            f.write(str(time.strftime("%b %d %Y %H:%M:%S", time.localtime())))
            f.write(f'请求tag {j}')
            f.write('\n')
            
        tqdm.write('INFO 失败的tag已写入日志')
        return j
    else:
        tagTranslation = resp['body']['tagTranslation']
        transtag = ''
        if tagTranslation == []:
            # print(tagTranslation)
            tqdm.write(f'INFO 无tag {j} 的翻译')
            # result = {j: 'None'}
            result = {j: j}
        else:
            trans: dict = tagTranslation[j]  # 包含所有翻译语言的dict
            lans = trans.keys()
            for l in priority:
                if l in lans and trans[l] != '':
                    transtag = trans[l]
                    break
            if transtag == '':
                av = []
                for available in trans.values():
                    if available != '':
                        # 是否有不用遍历的方法?
                        [av.append(_) for _ in trans.keys() if trans[_] == available]
                tqdm.write(f'INFO tag {j} 无目标语言的翻译 & 可用的语言 {av}')
                result = {j: j}
            else:
                result = {j: transtag}
        
        with open(CWD + '\\temp\\result', 'a', encoding = 'utf-8') as f:
            f.write(str(result) + '\n')
def fetch_translated_tag_m(th_count, jptags = []) -> tuple[list[dict], list[dict]] | str:
    """从pixiv上爬取tag翻译

    Args:
        th_count (int): _description_
        jptags (list): optional, 如果上次调用返回的not_translated_tags值不是空列表

    Raises:
        ValCheckError: _description_

    Returns:
        tuple[list[dict], list[dict]] | str: 第一个list是翻译好的tag列表，列表的元素为{'日文tag': '指定语言tag'}；
                                             第二个list是未翻译好的tag列表，元素就是'日文tag（未翻译）'
                                             返回str是出exception了
    """
    logger.info('正在运行')
    signature = inspect.signature(fetch_translated_tag_m)
    for param in signature.parameters.values():
        if var_check(eval(param.name)) == 1:
            raise ValCheckError
    try:
        if jptags == []:
            # 只找出未翻译的tag
            res = dbexecute('''
                        SELECT * FROM tags WHERE transtag is NULL
                        ''')

            for r in res:
                jptag = r[0]
                jptags.append(jptag)
            logger.info(f'已从数据库获取 {len(jptags)} 个tag')
        else:   # 这行本来不用，为了便于理解就加上了，有传入说明是此次调用为重试
            jptags = jptags
            logger.info(f'已从参数中获取 {len(jptags) }个tag')
        
        logger.info(f'创建线程池，线程数量: {th_count}')

        with ThreadPoolExecutor(max_workers=th_count) as pool:
            result = []
            tags_caught_exception = []
            read_file_exception = []


            # 初始化进度条（增加平滑参数）
            pbar = tqdm(total=len(jptags), smoothing=0.1)
            # 定义带异常处理的回调函数
            def handle_completion(future):
                try:
                    result = future.result()
                    if result is not None:
                        tags_caught_exception.append(result)
                finally:
                    pbar.update(1)  # 确保无论成功失败都更新进度
            # 批量提交任务
            futures = [pool.submit(fetch_translated_tag_i, j, len(jptags)) for j in jptags]
            # 绑定回调函数
            for future in futures:
                future.add_done_callback(handle_completion)
            # 等待所有任务完成（同时保持主线程活跃）
            while not all(f.done() for f in futures):
                time.sleep(0.1)  # 避免 CPU 空转
            pbar.close()

            # 读取文件
            logger.debug('tag翻译完成，从文件中读取结果')
            with open(CWD + '\\temp\\result', 'r', encoding = 'utf-8', errors = 'replace') as f:
                lines = f.readlines()
            for index, text in enumerate(lines):
                try:
                    result.append(eval(text))
                except Exception as e:
                    read_file_exception.append(index + 1)
                    tqdm.write(f'ERROR 读取文件内容时出现错误，已忽略(位于第 {index + 1} 行)')
                    tqdm.write(str(e))

            # 记录无翻译的tag和未翻译的tag
            # 无翻译指的是pixiv上没有对应的翻译，未翻译是程序出现错误
            s = 0
            translated_tags = []
            for r in result:
                r: dict
                if r is not None:
                    if list(r.keys()) == list(r.values()):  # 根据子线程出现无翻译时的操作进行判断
                        s += 1
                    translated_tags.append(list(r.keys())[0])     # key只有一个
            set_translated_tags = set(translated_tags)
            not_translated_tags = [jptag for jptag in jptags if jptag not in set_translated_tags]
            
            
            logger.info(f'tag翻译获取完成, 共 {len(jptags)} 个, 无翻译 {s} 个')
            if len(tags_caught_exception) > 0:
                logger.info(f'在线程运行时抛出exception的tag {tags_caught_exception}')
            if len(read_file_exception) > 0:
                logger.info(f"文件读取时发生错误的行 {read_file_exception}")
            if len(not_translated_tags) > 0:
                logger.info(f"总结: 未翻译的tag {not_translated_tags}")
                logger.info(f"总共 {len(not_translated_tags)} 个")

            if (len(not_translated_tags) == 0 
                and len(read_file_exception) == 0 
                and len(tags_caught_exception) == 0):
                logger.info('总结：翻译无异常')
            
            return result, not_translated_tags
    except Exception:
        return handle_exception(logger, inspect.currentframe().f_code.co_name)



def write_transtags_to_db_i(tran: dict):
    '''
    `tran`: 需要提交的tags (jp:tr)
    '''
    try:
        if tran is None:
            tqdm.write('ERROR 参数为NoneType类型，忽略')
        else:
            transtag = list(tran.values())[0]
            jptag = list(tran.keys())[0]
        # 注意sql语句transtag用双引号！
        # 否则执行sql时会有syntax error
        dbexecute(
            f'''UPDATE tags SET transtag = "{transtag}" WHERE jptag = "{jptag}"''')
    except Exception as e:
        tqdm.write(sys.exc_info())
        tqdm.write(f'函数传入参数: {tran}')
def write_transtags_to_db_m(th_count, trans):
    """提交翻译后的tags

    Args:
        th_count (int): 线程数
        trans (list): 包含原tag与翻译后tag字典的列表集合
    """
    logger.info('正在运行')
    signature = inspect.signature(write_transtags_to_db_m)
    for param in signature.parameters.values():
        if var_check(eval(param.name)) == 1:
            raise ValCheckError
    try:
        all_th = []
        logger.info(f'创建线程池，线程数量: {th_count}')
        with ThreadPoolExecutor(max_workers=th_count) as pool:
            for t in trans:
                exc = pool.submit(write_transtags_to_db_i, t)
                all_th.append(exc)
            for th in tqdm(as_completed(all_th), total=len(all_th)):
                if th.exception():
                    logger.error(f'运行时出现错误: {th.exception()}')
        logger.info('翻译后的tag已提交至表tags')
    except Exception:
        handle_exception(logger, inspect.currentframe().f_code.co_name)


def transtag_return_i(r0):
    try:
        pid, jptag0 = r0[0], r0[1]
        jptags = eval(jptag0)
        l = [''] * len(jptags)
        for i in range(len(jptags)):
            resp = dbexecute('''
                        SELECT * FROM tags
                        ''')
            for r in resp:
                jptag, transtag = r
                if jptag == jptags[i]:
                    l[i] = base64.b64encode(transtag.encode('utf-8'))
        dbexecute(f'''
                    UPDATE illusts SET transtag = "{l}" WHERE pid = {pid}
                    ''')
        dbexecute(f'''
                    UPDATE illusts SET is_translated = 1 WHERE pid = {pid}
                    ''')
        # logger.debug(l)
    except Exception as e:
        handle_exception(logger, inspect.currentframe().f_code.co_name)
def transtag_return_m(th_count):
    '''
    上传翻译后的tags至表illust
    '''
    logger.info('正在运行')
    signature = inspect.signature(transtag_return_m)
    for param in signature.parameters.values():
        if var_check(eval(param.name)) == 1:
            raise ValCheckError()
    try:
        logger.info(f'创建线程池，线程数量: {th_count}')
        with ThreadPoolExecutor(max_workers=th_count) as pool:
            resp0 = dbexecute('''
                        SELECT * FROM illusts
                        ''')
            
            all_th = [pool.submit(transtag_return_i, r0) for r0 in resp0]
            for th in tqdm(as_completed(all_th), total=len(all_th)):
                pass
        logger.info('翻译后的tag已提交至表illust')
    except Exception:
        handle_exception(logger, inspect.currentframe().f_code.co_name)


def mapping() -> dict:
    '''
    将illust表中存储的数据转换为tag对pid的映射
    '''
    logger.info('开始构建tag对pid的映射')
    res = dbexecute('SELECT pid,jptag,transtag FROM illusts')

    pid__tag = []   # pid对应的tag
    tag__pid = {}   # tag对应的pid

    def formatter(pid, string: str) -> dict:
        '''
        将数据库中的transtag值格式化 \n
        已弃用
        '''
        s = string.strip('"').replace('\\', '').replace('\"', '"').strip()
        matches = re.findall(r'"([^"]+?)"', s)
        return {pid: matches}
    for r in res:
        transtag_base64 = eval(r[2])
        transtag = []
        for tag_base64 in transtag_base64:
            tag = base64.b64decode(tag_base64).decode('utf-8')
            transtag.append(tag)
        
        pid__tag.append({r[0]: eval(r[1])})
        pid__tag.append({r[0]: transtag})

    logger.info(f'从数据库获取的数据解析完成，共有 {len(pid__tag) // 2} 个pid')

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
    
    # 补全空值，方便后续创建dataframe对象
    maxlen = 0
    for t in tag__pid:
        tmp = len(tag__pid[t])
        if tmp > maxlen:
            maxlen = tmp
    for t in tag__pid:
        tmp = len(tag__pid[t])
        if tmp < maxlen:
            tag__pid[t].extend([None]*(maxlen-tmp))
    logger.info('补齐空值完成')
    return tag__pid


def main():
    while True:
        # 备份并清空上次运行的结果(若有)
        timestamp = os.path.getmtime(CWD + '\\temp\\result').__round__(0)
        SrcModifyTime = datetime.datetime.fromtimestamp(timestamp)
        try:
            with open(CWD + '\\temp\\result', 'r', encoding = 'utf-8') as f:
                lines = f.readlines()
            if lines != []:
                logger.info('备份上次运行时fetch_translated_tag_i函数的返回值')

                shutil.copy(CWD + '\\temp\\result', CWD + '\\temp\\history\\' + str(SrcModifyTime).replace(':','-'))

                with open(CWD + '\\temp\\result', 'w', encoding = 'utf-8') as f:
                    f.write('')
        except UnicodeDecodeError:
            logger.error("读取文件时遇到编码错误")
            logger.info("直接复制文件")
            shutil.copy(CWD + '\\temp\\result', CWD + '\\temp\\history\\' + str(SrcModifyTime).replace(':','-'))

        print(mode_select)
        mode = input('模式 = ')
        if mode == '1':
            start = time.time()
            get_cookies(rtime=COOKIE_EXPIRED_TIME)
            URLs = analyse_bookmarks()
            
            # debug:
            # URLs = ['https://www.pixiv.net/ajax/user/71963925/illusts/bookmarks?tag=&offset=187&limit=1&rest=hide']

            
            illdata = analyse_illusts_m(ANALYSE_ILLUST_THREADS, URLs)
            # debug:
            #illdata = [{'id': '79862254', 'title': 'タシュケント♡', 'illustType': 0, 'xRestrict': 0, 'restrict': 0, 'sl': 2, 'url': 'https://i.pximg.net/c/250x250_80_a2/img-master/img/2020/03/03/09/31/57/79862254_p0_square1200.jpg', 'description': '', 'tags': ['タシュケント', 'アズールレーン', 'タシュケント(アズールレーン)', 'イラスト', '鯛焼き', 'アズールレーン10000users入り'], 'userId': '9216952', 'userName': 'AppleCaramel', 'width': 1800, 'height': 2546, 'pageCount': 1, 'isBookmarkable': True, 'bookmarkData': {'id': '25192310391', 'private': False}, 'alt': '#タシュケント タシュケント♡ - AppleCaramel的插画', 'titleCaptionTranslation': {'workTitle': None, 'workCaption': None}, 'createDate': '2020-03-03T09:31:57+09:00', 'updateDate': '2020-03-03T09:31:57+09:00', 'isUnlisted': False, 'isMasked': False, 'aiType': 0, 'profileImageUrl': 'https://i.pximg.net/user-profile/img/2022/10/24/02/12/49/23505973_7d9aa88560c5115b85cc29749ed40e28_50.jpg'},
            #{'id': '117717637', 'title': 'おしごと終わりにハグしてくれる天使', 'illustType': 0, 'xRestrict': 0, 'restrict': 0, 'sl': 4, 'url': 'https://i.pximg.net/c/250x250_80_a2/custom-thumb/img/2024/04/10/17/30/02/117717637_p0_custom1200.jpg', 'description': '', 'tags': ['オリジナル', '女の子', '緑髪', '天使', 'ハグ', '巨乳', 'ぱんつ', 'オリジナル1000users入り'], 'userId': '29164302', 'userName': '緑風マルト🌿', 'width': 1296, 'height': 1812, 'pageCount': 1, 'isBookmarkable': True, 'bookmarkData': {'id': '25109862018', 'private': False}, 'alt': '#オリジナル おしごと終わりにハグしてくれる天使 - 緑風マルト🌿的插画', 'titleCaptionTranslation': {'workTitle': None, 'workCaption': None}, 'createDate': '2024-04-10T17:30:02+09:00', 'updateDate': '2024-04-10T17:30:02+09:00', 'isUnlisted': False, 'isMasked': False, 'aiType': 1, 'profileImageUrl': 'https://i.pximg.net/user-profile/img/2024/01/25/15/56/10/25434619_c70d86172914664ea2b15cec94bc0afd_50.png'},
            #{'id': '84450882', 'title': 'ネコ耳墨ちゃん🐈', 'illustType': 0, 'xRestrict': 0, 'restrict': 0, 'sl': 2, 'url': 'https://i.pximg.net/c/250x250_80_a2/img-master/img/2020/09/18/19/44/35/84450882_p0_square1200.jpg', 'description': '', 'tags': ['彼女、お借りします', 'かのかり', '桜沢墨', '猫', '猫耳', '制服', '白ニーソ', '拾ってください', '彼女、お借りします5000users入り'], 'userId': '38436050', 'userName': 'ゆきうなぎ＠土曜東ス88a', 'width': 2894, 'height': 4093, 'pageCount': 1, 'isBookmarkable': True, 'bookmarkData': {'id': '24948220443', 'private': False}, 'alt': '#彼女、お借りします ネコ耳墨ちゃん🐈 - ゆきうなぎ＠土曜東ス88a的插画', 'titleCaptionTranslation': {'workTitle': None, 'workCaption': None}, 'createDate': '2020-09-18T19:44:35+09:00', 'updateDate': '2020-09-18T19:44:35+09:00', 'isUnlisted': False, 'isMasked': False, 'aiType': 0, 'profileImageUrl': 'https://i.pximg.net/user-profile/img/2020/02/22/00/11/25/17966339_a51ca7e8a3aca581fc87021488e21479_50.jpg'},
            #]


            writeraw_to_db_m(WRITERAW_TO_DB_THREADS, illdata)
            write_rawtags_to_db()

            count = 0
            trans, not_trans = fetch_translated_tag_m(FETCH_TRANSLATED_TAG_THREADS)
            while not_trans != [] and count <= 10:      # 若翻译出错，则重试
                logger.info(f'现在重试翻译tags {not_trans} ')
                trans_added, not_trans = fetch_translated_tag_m(FETCH_TRANSLATED_TAG_THREADS, not_trans)
                trans.append(trans_added)
            if not_trans != []:     # 重试之后还是不行
                logger.warning('达到最大重试次数，放弃')

            # debug:
            # trans = [{'オリジナル': '原创'}, {'拾ってください': 'None'}, {'鯛焼き': 'None'}, {'かのかり': 'Rent-A-Girlfriend'}, {'彼女、お借りします5000users入り': '租借女友5000收藏'}, {'女の子': '女孩子'}, {'桜沢墨': '樱泽墨'}, {'緑髪': 'green hair'}, {'猫耳': 'cat ears'}, {'猫': 'cat'}, {'天使': 'angel'}, {'白ニーソ': '白色过膝袜'}, {'制服': 'uniform'}, {'彼女、お借りします': 'Rent-A-Girlfriend'}, {'アズールレーン': '碧蓝航线'}, {'ぱんつ': '胖次'}, {'オリジナル1000users入り': '原创1000users加入书籤'}, {'タシュケント': '塔什干'}, {'ハグ': '拥抱'}, {'タシュケント(アズールレーン)': '塔什干（碧蓝航线）'}, {'アズールレーン10000users入り': '碧蓝航线10000收藏'}, {'巨乳': 'large breasts'}, {'イラスト': '插画'}]


            write_transtags_to_db_m(WRITE_TRANSTAGS_TO_DB_THREADS, trans)

            transtag_return_m(TRANSTAG_RETURN_THREADS)
            end = time.time()
            toaster.show_toast('PixivTags', '已更新tags至本地数据库', duration = 10)
            logger.info(f'总耗时: {end-start} 秒')
        elif mode == '2':
            map_result = mapping()
            df = pd.DataFrame(map_result)
            logger.info('数据操作全部完成')
            logger.info('进入交互模式')
            
            # 交互模式相关函数
            def _help():
                print(help_text)
            def _search():
                key = ''
                while key == '':
                    print('参数: -f 强制搜索此tag [-f tag]')
                    print('参数: -c 多tag搜索 [-c tag0 tag1 tag2]')
                    print('输入关键词以进行查询（只支持单个参数）:')
                    cmd_key = input()

                    keys = list(map_result.keys())
                    if len(cmd_key.split(' ')) == 1:
                        key = cmd_key
                        target_keys = get_close_matches(key, keys, n=3, cutoff=0.5)
                        
                        print(f'可能的结果: {target_keys}')
                        try:
                            target_key_index = int(input('输入元素索引: '))
                            print(f'pids: {set(list(df[target_keys[target_key_index]].dropna().astype(int).sort_values(ascending = False)))}')

                        except Exception as e:
                            handle_exception(logger)
                            continue

                    elif cmd_key.split(' ')[0] == '-f':
                        key = cmd_key.split(' ')[-1]
                        try:
                            print(f'pids: {set(list(df[key].dropna().astype(int).sort_values(ascending = False)))}')
                        except Exception:
                            handle_exception(logger)
                    elif cmd_key.split(' ')[0] == '-c':
                        plist = []      # 存放每次查询返回的结果集合
                        intersection = []   # 取得的交集
                        
                        keylist = cmd_key.split(' ')[1:]
                        
                        s = 1
                        l = len(keylist)
                        for k in keylist:
                            while True:
                                print(f'正在查询的key为第 {s} 个, 共 {l} 个')
                                target_keys = get_close_matches(k, keys, n=3, cutoff=0.5)
                                
                                print(f'可能的结果: {target_keys}')
                                try:
                                    target_key_index = int(input('输入元素索引: '))
                                    plist.extend(set(list(df[target_keys[target_key_index]].dropna().astype(int))))
                                    s += 1
                                    break
                                except Exception as e:
                                    handle_exception(logger)
                                    continue

                        for p in set(plist):
                            num = plist.count(p)
                            if num == l:
                                intersection.append(p)
                        print(f'pids: {sorted(intersection)}') 
                        key = 'done'
                    else:
                        print(f"未知的参数: {cmd_key.split(' ')[0]}")
            def _exit():
                logger.info('程序执行完成')
                exit()
            def _list():
                print(df)
            def _hot():
                print('获取的tags数目: ')
                num = int(input())
                ser = df.count().sort_values(ascending = False).head(num)
                print(ser)
            def _debug():
                print(eval(input('python>')))
            _help()
            while True:
                print('>>>', end='')
                search = input()
                if search in reserve_words:
                    eval(reserve_words[search])
                else:
                    print('未知的指令')
                    _help()
                print('\n')
        elif mode == '3':
            # 此段代码参考fetch_translated_tag_m函数
            result = []
            history_file_name = input('输入历史记录文件名(位于/history目录下，格式为: xxxx-xx-xx xx-xx-xx)')
            history_file_path = CWD + '\\temp\\history\\' + history_file_name
            if os.path.exists(history_file_path):
                with open(history_file_path, 'r', encoding = 'utf-8') as f:
                    lines = f.readlines()
                    for line in lines:
                        dic = eval(line)
                        result.append(dic)
            else:
                logger.warning(f'指定的文件不存在 {history_file_path}')
            
            s = 0
            for r in result:
                if r is not None:
                    r: dict
                    if list(r.keys()) == list(r.values()):
                        s += 1
            logger.info(f'tag翻译获取完成, 共 {len(result)} 个, 无翻译 {s} 个')
            write_transtags_to_db_m(WRITE_TRANSTAGS_TO_DB_THREADS, result)

            transtag_return_m(TRANSTAG_RETURN_THREADS)
            end = time.time()
            toaster.show_toast('PixivTags', '已更新tags至本地数据库', duration = 10)
        elif mode == '4':
            logger.info('程序退出')
            break
        else:
            print(f'未知的指令 {mode}')
        print('')

if __name__ == "__main__":
    main()