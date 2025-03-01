import asyncio
from playwright.async_api import async_playwright
import playwright.async_api
from tqdm.asyncio import tqdm



# standard-libs
import inspect
import json
import logging
import os
import sqlite3
import sys
import threading
import traceback
from urllib import parse
import time

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
# 日志初始化
logger = logging.getLogger('logger')
handler = logging.StreamHandler()
logger.setLevel(logging.DEBUG)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "[%(asctime)s %(name)s %(thread)d %(funcName)s] %(levelname)s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


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




async def fetch_tag(session: playwright.async_api.APIRequestContext, tag: str, retries=5) -> tuple[str, dict]:
    encoded_tag = parse.quote(tag, safe = '')
    url = f"https://www.pixiv.net/ajax/search/tags/{encoded_tag}?lang=zh"
    for attempt in range(retries):
        try:
            response = await session.get(url)
            
            if response.status == 429:
                wait_time = 2 ** (attempt + 1)
                tqdm.write(f"触发限流 [{tag}]，等待 {wait_time} 秒后重试...")
                await asyncio.sleep(wait_time)
                continue
                
            return (tag, await response.json())
            
        except Exception as e:
            tqdm.write(f"请求失败 [{tag}]: {sys.exc_info()}")
            if attempt == retries - 1:  # 达到最大重试次数
                return (tag, {"error": sys.exc_info()})
            await asyncio.sleep(0.5 * (attempt + 1))

async def fetch_tag_worker(session: playwright.async_api.APIRequestContext, queue: asyncio.Queue, results: list, pbar: tqdm):
    while True:
        jptag = await queue.get()
        try:
            pbar.set_description(f"Processing {jptag[:10]}...")
            result: tuple[str, dict] = await fetch_tag(session, jptag)
            results.append(result)
            pbar.update(1)
        except Exception as e:
            print(sys.exc_info())
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
                        SELECT * FROM tags WHERE transtag is NULL
                        ''')

            for r in res:
                jptag = r[0]
                jptags.append(jptag)
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
            
            with tqdm(total=len(jptags), desc="采集进度") as pbar:
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
                    tqdm.write(f'INFO 无tag {tag} 的翻译')
                    # result = {tag: 'None'}
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
                        tqdm.write(f'INFO tag {tag} 无目标语言的翻译 & 可用的语言 {av}')
                        result = {tag: tag}
                    else:
                        result = {tag: transtag}
                translation_results.append(result)
                
        return translation_results, tags_caught_exception
    except Exception as e:
        return handle_exception(logger, inspect.currentframe().f_code.co_name)

def fetch_translated_tag_gather(retry = 10):
    '''
    ## 获取并整合翻译tag
    '''
    count = 0
    trans, not_trans = asyncio.run(fetch_translated_tag_main())
    while count < retry:
        if not_trans == []:
            break
        else:
            logger.info(f'在翻译过程中出现了错误，共 {len(not_trans)} 个')
            logger.info(f'重试...({count + 1}/{retry})')
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

