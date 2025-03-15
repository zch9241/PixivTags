# PixivTags
# 
# Copyright (c) 2024-2025 zch9241. All rights reserved.
# 
# 本软件受以下使用条款约束：
# 1. 仅限个人及教育用途，禁止商业使用
# 2. 禁止未经授权的营利性传播
# 3. 完整条款详见项目根目录LICENSE文件
# 
# 如有疑问请联系：[zch2426936965@gmail.com]
# 

# TODO:
# 优化查询功能
# 为插画添加更多元数据


# done:
# 爬虫函数使用session，提高效率
# 部分爬虫改为异步，提高效率
# 修改版权声明
# 数据库结构修改
# 数据库交互函数修改（单线程）


# standard-libs
import asyncio
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
from playwright.async_api import async_playwright
import playwright.async_api
from playwright.sync_api import sync_playwright
import psutil
from tqdm import tqdm
from tqdm.asyncio import tqdm as async_tqdm
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
with sqlite3.connect(SQLPATH) as conn:
    cursor = conn.cursor()  

    # 作品主表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS illusts (
        pid INTEGER PRIMARY KEY,
        author_id INTEGER,
        title TEXT,
        created_at TEXT DEFAULT (datetime('now', 'localtime')),
        is_private INTEGER DEFAULT 0
    )''')

    # 标签字典表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tags (
        tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
        jptag TEXT UNIQUE,
        transtag TEXT
    )''')

    # 作品-标签关联表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS illust_tags (
        pid INTEGER,
        tag_id INTEGER,
        FOREIGN KEY(pid) REFERENCES illusts(pid),
        FOREIGN KEY(tag_id) REFERENCES tags(tag_id),
        UNIQUE(pid, tag_id)
    )''')

    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_jptag ON tags(jptag)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_transtag ON tags(transtag)')
    conn.commit()
    cursor.close()




def handle_exception(logger: logging.Logger, func_name: str = None, in_bar = True, async_ = False):
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
    
    if in_bar is True and async_ is False:
        tqdm.write(f'ERROR {exc_type.__name__}: {exc_value}')
        tqdm.write(f'ERROR {ex}')
    elif in_bar is True and async_ is True:
        async_tqdm.write(f'ERROR {exc_type.__name__}: {exc_value}')
        async_tqdm.write(f'ERROR {ex}')
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
    logger.info('验证cookie有效性')
    
    with open(COOKIE_TIME_PATH, 'r') as f:
        data = f.read()
        if data != '':
            modify_time = float(data)
        else:
            modify_time = 0
    relative_time = time.time() - modify_time
    
    if (relative_time < rtime and 
        relative_time > 0 and 
        forced is False):
        
        logger.info(f'无需更新cookies: 距上次更新 {relative_time} 秒')
    
    else:
        logger.info(f'需要更新cookies: 距上次更新 {relative_time} 秒')

        # 判断Google Chrome是否在运行，如果在chrome运行时使用playwright将会报错
        def find_process(name):
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if name.lower() in proc.info['name'].lower():
                        return proc
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            return None

        def kill_process(name):
            proc = find_process(name)
            while proc:
                logger.info(f"找到 chrome 进程 (name: {proc.info['name']}, PID: {proc.info['pid']})")
                logger.info("请结束进程，否则cookies无法正常获取")
                
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
            if (many is True 
                and type(params) == list 
                and all(isinstance(item, tuple) for item in params)):   # 验证list[tuple]
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
    """解析用户bookmarks接口URL

    接口名称: https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag={}&offset={}&limit={}&rest={}&lang={}
    
    Args:
        rest_flag (int, optional): 插画的可见性 (0=公开, 1=不公开, 2=全部). Defaults to 2.
        limit (int, optional): 一个接口URL截取的插画数目, 实测最大值为100. Defaults to 100.

    Returns:
        list: 接口URL
    """

    logger.info('正在运行')

    try:
        rest_dict = {0: ['show'], 1: ['hide'], 2: ['show', 'hide']}
        rest = rest_dict[rest_flag]

        # 解析用户bookmark的插画数量
        url_show = f'https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset=0&limit=1&rest=show&lang=zh'
        url_hide = f'https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset=0&limit=1&rest=hide&lang=zh'

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True,executable_path=CHROME_PATH)
            context = browser.new_context(storage_state=COOKIE_PATH)
            session = context.request
            
            resp = session.get(url_show).json()
            total_show = resp['body']['total']

            resp = session.get(url_hide).json()
            total_hide = resp['body']['total']
            
            browser.close()

        logger.info(f'解析bookmarks完成, 公开数量: {total_show}, 不公开数量: {total_hide}')


        # 计算请求URL
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

    except Exception:
        urls = handle_exception(logger, inspect.currentframe().f_code.co_name)
    return urls


async def analyse_illusts_worker(session: playwright.async_api.APIRequestContext, 
                                 queue: asyncio.Queue, 
                                 illdatas: list,
                                 ignores: list, 
                                 pbar: async_tqdm, 
                                 retries = 5):
    while True:
        url = await queue.get()
        try:
            for attempt in range(retries):
                try:
                    resp = await session.get(url)
                    if resp.status == 429:
                        wait_time = 2 ** (attempt + 1)
                        async_tqdm.write(f"触发限流 [{url}]，等待 {wait_time} 秒后重试...")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    resp = await resp.json()
                    illdata_ = resp['body']['works']     # 一个接口url所获取到的所有插画信息
                    for illdata in illdata_:
                        if illdata['isMasked'] is True:
                            ignores.append(illdata['id'])
                        else:
                            illdatas.append(illdata)    # 汇总到主列表
                    break
                except Exception as e:
                    async_tqdm.write(f"请求失败 [{url}]: {sys.exc_info()}")
                    await asyncio.sleep(0.5 * (attempt + 1))

            pbar.update(1)
        except Exception as e:
            async_tqdm.write(sys.exc_info())
        finally:
            queue.task_done()
    
async def analyse_illusts_main(bookmark_urls: list, max_concurrency = 3):
    """获取bookmark中每张插画的数据

    Args:
        bookmark_urls (list): 用户的全部bookmark的接口url
        max_concurrency (int, optional): 顾名思义. Defaults to 3.

    Returns:
        list: 每张插画的数据
    """
    logger.info('正在运行')
    
    illdatas = []    # 包含插画信息的列表
    ignores = []     # 因故无法获取插画信息的计数器(以列表形式存储)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=CHROME_PATH
        )
        
        context = await browser.new_context(storage_state=COOKIE_PATH)
        session = context.request
        
        queue = asyncio.Queue()
        for url in bookmark_urls:
            await queue.put(url)
        
        with async_tqdm(total = len(bookmark_urls), desc = '获取插画信息') as pbar:
            workers = [
                asyncio.create_task(analyse_illusts_worker(session, queue, illdatas, ignores, pbar))
                for _ in range(min(max_concurrency, len(bookmark_urls)))
            ]

            await queue.join()
            for w in workers:
                w.cancel()
        await context.close()
        await browser.close()
        
    logger.info(f'所有插画信息获取完成，长度: {len(illdatas)} 忽略数量: {len(ignores)}')
    return illdatas


def commit_illust_data(illdatas: list):
    """提交插画基本数据

    Args:
        illdatas (list): 插画数据，由analyse_illusts获取
    """
    logger.info('正在运行')

    # 插画基本信息 (除了tags)
    basic_illdatas = [(int(illdata['id']),
                 int(illdata['userId']),
                 illdata['title'], 
                 int(illdata['bookmarkData']['private'])   # 此数据原本是布尔值
                 )
                for illdata in illdatas]
    
    sql = '''
    INSERT INTO illusts (pid, author_id, title, is_private) VALUES (?, ?, ?, ?)
    ON CONFLICT(pid) DO UPDATE
    SET 
        author_id = excluded.author_id,
        title = excluded.title,
        is_private = excluded.is_private;
    '''
    
    
    with sqlite3.connect(SQLPATH) as conn:
        cursor = conn.cursor()
        cursor.executemany(sql, basic_illdatas)
        
        # 插入插画tags
        for illdata in illdatas:
            pid = int(illdata['id'])
            for tag in illdata['tags']:
                cursor.execute('INSERT OR IGNORE INTO tags (jptag) VALUES (?)', (tag,))
                # 获取tag_id
                cursor.execute('SELECT tag_id FROM tags WHERE jptag = (?)', (tag,))
                tag_id = cursor.fetchone()[0]
                # 插入关联关系
                cursor.execute('INSERT OR IGNORE INTO illust_tags (pid, tag_id) VALUES (?, ?)', (pid, tag_id))

        conn.commit()
        cursor.close()

    logger.info('提交完成')


async def fetch_tag(session: playwright.async_api.APIRequestContext, tag: str, retries=5) -> tuple[str, dict]:
    encoded_tag = parse.quote(tag, safe = '')
    url = f"https://www.pixiv.net/ajax/search/tags/{encoded_tag}?lang=zh"
    for attempt in range(retries):
        try:
            response = await session.get(url)
            
            if response.status == 429:
                wait_time = 2 ** (attempt + 1)
                async_tqdm.write(f"触发限流 [{tag}]，等待 {wait_time} 秒后重试...")
                await asyncio.sleep(wait_time)
                continue
                
            return (tag, await response.json())
            
        except Exception as e:
            async_tqdm.write(f"请求失败 [{tag}]: {sys.exc_info()}")
            if attempt == retries - 1:  # 达到最大重试次数
                return (tag, {"error": sys.exc_info()})
            await asyncio.sleep(0.5 * (attempt + 1))

async def fetch_tag_worker(session: playwright.async_api.APIRequestContext, queue: asyncio.Queue, results: list, pbar: async_tqdm):
    while True:
        jptag = await queue.get()
        try:
            pbar.set_description(f"Processing {str(jptag)[:10]}...")
            result: tuple[str, dict] = await fetch_tag(session, jptag)
            results.append(result)
            pbar.update(1)
        except Exception as e:
            handle_exception(logger, inspect.currentframe().f_code.co_name, in_bar=True, async_=True)
        finally:
            queue.task_done()

async def fetch_translated_tag_main(jptags: list = [], priority: list = [], max_concurrency = 20) -> tuple[list, list]:
    """
    ## 获取pixiv上的tag翻译
    
    ### args:
    - jptags: 要获取翻译的原始tag列表
    - priority: 翻译语言优先级列表（优先级递减）
    - max_concurrency: 最大协程数量
    
    ### returns:
    (tuple)包含一个jptag-transtag的字典的列表，以及一个未翻译成功的tag的列表
    """
    priority = ['zh', 'en', 'zh_tw']
    logger.info('正在运行')
    #signature = inspect.signature(fetch_translated_tag_m)
    #for param in signature.parameters.values():
    #    if var_check(eval(param.name)) == 1:
    #        raise ValCheckError
    try:
        if jptags == []:
            # 只找出未翻译的tag
            res = dbexecute('''
                        SELECT jptag FROM tags WHERE transtag is NULL
                        ''')

            jptags = [r[0] for r in res]
            logger.info(f'已从数据库获取 {len(jptags)} 个tag')
        else:   # 这行本来不用，为了便于理解就加上了，有传入说明是此次调用为重试
            jptags = jptags
            logger.info(f'已从参数中获取 {len(jptags)} 个tag')
    
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                executable_path=CHROME_PATH
            )
            
            context = await browser.new_context(storage_state=COOKIE_PATH)
            session = context.request
            
            queue = asyncio.Queue()
            for jptag in jptags:
                await queue.put(jptag)
            
            results = []
            
            with async_tqdm(total=len(jptags), desc="采集进度") as pbar:
                workers = [
                    asyncio.create_task(fetch_tag_worker(session, queue, results, pbar))
                    for _ in range(min(max_concurrency, len(jptags)))
                ]

                await queue.join()
                
                for w in workers:
                    w.cancel()
            
            await context.close()
            await browser.close()
        
        translation_results = []
        tags_caught_exception = []
        for tag, resp in results:
            if resp['error'] is not False:
                tags_caught_exception.append(tag)
            else:
                tagTranslation = resp['body']['tagTranslation']
                transtag = ''
                if tagTranslation == []:
                    # print(tagTranslation)
                    # logger.info(f'无tag {tag} 的翻译')
                    result = {tag: tag}
                else:
                    trans: dict = tagTranslation[tag]  # 包含所有翻译语言的dict
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
                        # logger.info(f'tag {tag} 无目标语言的翻译 & 可用的语言 {av}')
                        result = {tag: tag}
                    else:
                        result = {tag: transtag}
                translation_results.append(result)
                
        return translation_results, tags_caught_exception
    except Exception as e:
        return handle_exception(logger, inspect.currentframe().f_code.co_name)

def fetch_translated_tag_gather(retries = 10):
    '''
    ## 获取并整合翻译tag
    
    ### args:
    - retries: 重试次数
    
    ### returns:
    (list)包含一个jptag-transtag的字典的列表
    '''
    count = 0
    trans, not_trans = asyncio.run(fetch_translated_tag_main())
    while count < retries:
        if not_trans == []:
            break
        else:
            logger.info(f'在翻译过程中出现了错误，共 {len(not_trans)} 个')
            logger.info(f'重试...({count + 1}/{retries})')
            trans_, not_trans = asyncio.run(fetch_translated_tag_main(not_trans))
            trans.append(trans_)
        count += 1
    if not_trans != []:     # 重试后还是未能获取
        with open(TAG_LOG_PATH, 'a', encoding = 'utf-8') as f:
            f.write(str(time.strftime("%b %d %Y %H:%M:%S", time.localtime())))
            f.write(f'请求tag {not_trans}')
            f.write('\n')
        logger.warning('达到最大重试次数，但仍有部分tag未能翻译，失败的结果已写入log')
    logger.info(f'INFO 翻译完成，成功:{len(trans)}  失败:{len(not_trans)}')
    return trans


def commit_translated_tags(translated_tags: list):
    """提交翻译后的tags

    Args:
        translated_tags (list): fetch_translated_tags获取的翻译后tag列表
    """
    logger.info('正在运行')
    jpTags_transTags = [(list(jptag_transtag.keys())[0], 
                         list(jptag_transtag.values())[0])
                        for jptag_transtag in translated_tags]  # 转换tag翻译对应关系为元组
    with sqlite3.connect(SQLPATH) as conn:
        cursor = conn.cursor()
        cursor.executemany('UPDATE OR IGNORE tags SET transtag = ? WHERE jptag = ?', jpTags_transTags)
        cursor.execute("UPDATE tags SET transtag = NULL WHERE transtag == 'None'")
        conn.commit()
        cursor.close()
    
    logger.info('翻译后的tag已提交')



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
                        SELECT jptag,transtag FROM tags
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
            resp0 = dbexecute('SELECT pid,jptag FROM illusts')
            
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

            
            illdatas = asyncio.run(analyse_illusts_main(URLs))

            # debug:
            #illdata = [{'id': '79862254', 'title': 'タシュケント♡', 'illustType': 0, 'xRestrict': 0, 'restrict': 0, 'sl': 2, 'url': 'https://i.pximg.net/c/250x250_80_a2/img-master/img/2020/03/03/09/31/57/79862254_p0_square1200.jpg', 'description': '', 'tags': ['タシュケント', 'アズールレーン', 'タシュケント(アズールレーン)', 'イラスト', '鯛焼き', 'アズールレーン10000users入り'], 'userId': '9216952', 'userName': 'AppleCaramel', 'width': 1800, 'height': 2546, 'pageCount': 1, 'isBookmarkable': True, 'bookmarkData': {'id': '25192310391', 'private': False}, 'alt': '#タシュケント タシュケント♡ - AppleCaramel的插画', 'titleCaptionTranslation': {'workTitle': None, 'workCaption': None}, 'createDate': '2020-03-03T09:31:57+09:00', 'updateDate': '2020-03-03T09:31:57+09:00', 'isUnlisted': False, 'isMasked': False, 'aiType': 0, 'profileImageUrl': 'https://i.pximg.net/user-profile/img/2022/10/24/02/12/49/23505973_7d9aa88560c5115b85cc29749ed40e28_50.jpg'},
            #{'id': '117717637', 'title': 'おしごと終わりにハグしてくれる天使', 'illustType': 0, 'xRestrict': 0, 'restrict': 0, 'sl': 4, 'url': 'https://i.pximg.net/c/250x250_80_a2/custom-thumb/img/2024/04/10/17/30/02/117717637_p0_custom1200.jpg', 'description': '', 'tags': ['オリジナル', '女の子', '緑髪', '天使', 'ハグ', '巨乳', 'ぱんつ', 'オリジナル1000users入り'], 'userId': '29164302', 'userName': '緑風マルト🌿', 'width': 1296, 'height': 1812, 'pageCount': 1, 'isBookmarkable': True, 'bookmarkData': {'id': '25109862018', 'private': False}, 'alt': '#オリジナル おしごと終わりにハグしてくれる天使 - 緑風マルト🌿的插画', 'titleCaptionTranslation': {'workTitle': None, 'workCaption': None}, 'createDate': '2024-04-10T17:30:02+09:00', 'updateDate': '2024-04-10T17:30:02+09:00', 'isUnlisted': False, 'isMasked': False, 'aiType': 1, 'profileImageUrl': 'https://i.pximg.net/user-profile/img/2024/01/25/15/56/10/25434619_c70d86172914664ea2b15cec94bc0afd_50.png'},
            #{'id': '84450882', 'title': 'ネコ耳墨ちゃん🐈', 'illustType': 0, 'xRestrict': 0, 'restrict': 0, 'sl': 2, 'url': 'https://i.pximg.net/c/250x250_80_a2/img-master/img/2020/09/18/19/44/35/84450882_p0_square1200.jpg', 'description': '', 'tags': ['彼女、お借りします', 'かのかり', '桜沢墨', '猫', '猫耳', '制服', '白ニーソ', '拾ってください', '彼女、お借りします5000users入り'], 'userId': '38436050', 'userName': 'ゆきうなぎ＠土曜東ス88a', 'width': 2894, 'height': 4093, 'pageCount': 1, 'isBookmarkable': True, 'bookmarkData': {'id': '24948220443', 'private': False}, 'alt': '#彼女、お借りします ネコ耳墨ちゃん🐈 - ゆきうなぎ＠土曜東ス88a的插画', 'titleCaptionTranslation': {'workTitle': None, 'workCaption': None}, 'createDate': '2020-09-18T19:44:35+09:00', 'updateDate': '2020-09-18T19:44:35+09:00', 'isUnlisted': False, 'isMasked': False, 'aiType': 0, 'profileImageUrl': 'https://i.pximg.net/user-profile/img/2020/02/22/00/11/25/17966339_a51ca7e8a3aca581fc87021488e21479_50.jpg'},
            #]


            commit_illust_data(illdatas)


            trans = fetch_translated_tag_gather()
            # debug:
            # trans = [{'オリジナル': '原创'}, {'拾ってください': 'None'}, {'鯛焼き': 'None'}, {'かのかり': 'Rent-A-Girlfriend'}, {'彼女、お借りします5000users入り': '租借女友5000收藏'}, {'女の子': '女孩子'}, {'桜沢墨': '樱泽墨'}, {'緑髪': 'green hair'}, {'猫耳': 'cat ears'}, {'猫': 'cat'}, {'天使': 'angel'}, {'白ニーソ': '白色过膝袜'}, {'制服': 'uniform'}, {'彼女、お借りします': 'Rent-A-Girlfriend'}, {'アズールレーン': '碧蓝航线'}, {'ぱんつ': '胖次'}, {'オリジナル1000users入り': '原创1000users加入书籤'}, {'タシュケント': '塔什干'}, {'ハグ': '拥抱'}, {'タシュケント(アズールレーン)': '塔什干（碧蓝航线）'}, {'アズールレーン10000users入り': '碧蓝航线10000收藏'}, {'巨乳': 'large breasts'}, {'イラスト': '插画'}]


            commit_translated_tags(trans)

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