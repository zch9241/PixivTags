# PIXIVTAGS Version 1.0
# 
# 
# COPYRIGHT NOTICE  
# 
# Copyright (c) 2024, zch9241. All rights reserved.  
# 
# This source code is provided "AS IS" without any warranty of any kind.  
# You may use this source code for any purpose, provided that you do not violate any applicable laws or regulations. However, you are not authorized to distribute, modify, or sublicense this source code without the express written permission of the copyright owner.  
#  
# If you have any questions or need further clarification, please contact:  
# [zch2426936965@gmail.com]
# 

# standard-libs
import base64
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED
import datetime
from difflib import get_close_matches
import inspect
import json
import logging
import os
import re
import shutil
import sqlite3
import sys
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
from tkinter.font import Font
import time
import traceback
from urllib import parse

# site-packages
import pandas as pd
import psutil
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from win10toast import ToastNotifier


import decrypt
import decrypt_by_selenium
import config


# 常量初始化
ANALYSE_ILLUST_THREADS = config.ANALYSE_ILLUST_THREADS
WRITERAW_TO_DB_THREADS = config.WRITERAW_TO_DB_THREADS
WRITE_TAGS_TO_DB_THREADS = config.WRITE_TAGS_TO_DB_THREADS
FETCH_TRANSLATED_TAG_THREADS = config.FETCH_TRANSLATED_TAG_THREADS
WRITE_TRANSTAGS_TO_DB_THREADS = config.WRITE_TRANSTAGS_TO_DB_THREADS
TRANSTAG_RETURN_THREADS = config.TRANSTAG_RETURN_THREADS
UID = config.UID
COOKIE_EXPIRED_TIME = config.COOKIE_EXPIRED_TIME

CWD = os.getcwd()
SQLPATH = CWD + r'\src\illdata.db'
COOKIE_PATH = CWD + r'\src\cookies.py'
TAG_LOG_PATH = CWD + r'\logs\tag\content.log'
CHROME_DRIVER_PATH = CWD + r'\bin\chromedriver.exe' 

# 交互模式
reserve_words = {'help': '_help()', 'exit': '_exit()',
                 'search': '_search()', 'list': '_list()', 'hot': '_hot()'}
help_text = """
这是交互模式的使用说明
`help`: 显示帮助
`exit`: 退出主程序
`search`: 搜索tags
`list`: 列出所有tags(危险操作)
`hot`: 列出出现最多的tags
"""

# GUI初始化
root = tk.Tk()
font_ = Font(family="Consolas", size=8, weight="bold")
text_widget = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=120, height=30, font=font_)
text_widget.pack(fill=tk.BOTH, expand=True)
text_widget.config(state='disabled')  # 禁止直接编辑


# 日志初始化
## GUI日志
class TkinterLogHandler(logging.Handler):  
    def __init__(self, text_widget):  
        super().__init__()  
        self.text_widget = text_widget  
  
    def emit(self, record):  
        msg = self.format(record)  
        def append():  
            self.text_widget.config(state='normal')  
            self.text_widget.insert(tk.END, msg + '\n')  
            self.text_widget.yview(tk.END)  
            self.text_widget.config(state='disabled')  
          
        # 确保GUI更新在主线程中执行  
        self.text_widget.after(0, append)  

logger = logging.getLogger('guilogger')  
logger.setLevel(logging.DEBUG)

# 将TkinterLogHandler添加到日志器  
handler = TkinterLogHandler(text_widget)  
formatter = logging.Formatter(
    "[%(asctime)s %(name)s %(thread)d %(funcName)s] %(levelname)s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler) 


## 控制台日志
#logger = logging.getLogger('logger')
#handler = logging.StreamHandler()
#logger.setLevel(logging.DEBUG)
#handler.setLevel(logging.DEBUG)
#formatter = logging.Formatter(
#    "[%(asctime)s %(name)s %(thread)d %(funcName)s] %(levelname)s %(message)s")
#handler.setFormatter(formatter)
#logger.addHandler(handler)

# Toast初始化
toaster = ToastNotifier()


# 获取cookies
def get_cookies(rtime: int) -> list:
    """获取Google Chrome的cookies \n
    已弃用

    Args:
        rtime (int): cookie更新间隔

    Returns:
        (list): 包含所有pixiv的cookie的列表
    """
    global update_cookies
    cookie = []

    # 判断是否需要更新cookies
    mod_time = os.path.getmtime(COOKIE_PATH)
    relative_time = time.time() - mod_time
    if relative_time < rtime:
        update_cookies = False
        logger.info(f'无需更新cookies: 距上次更新 {relative_time} 秒')
    else:
        update_cookies = True
        logger.info(f'需要更新cookies: 距上次更新 {relative_time} 秒')

        # 判断Google Chrome是否在运行，是则结束
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

        # 复制文件
        logger.info('更新cookie文件')
        # 定义cookie、localstate、logindata三个文件的位置
        cookie_path = os.path.expanduser(os.path.join(
            os.environ['LOCALAPPDATA'], r'Google\Chrome\User Data\Default\Network\Cookies'))

        local_state_path = os.path.join(
            os.environ['LOCALAPPDATA'], r"Google\Chrome\User Data\Local State")

        login_data_path = os.path.expanduser(os.path.join(
            os.environ['LOCALAPPDATA'], r'Google\Chrome\User Data\Default\Login Data'))

        # 复制对应文件(后续debug用)
        shutil.copy(cookie_path, CWD + r'\src\Cookies')
        shutil.copy(local_state_path, CWD + r'\src\Local State')
        shutil.copy(login_data_path, CWD + r'\src\Login Data')

    # 解密cookies
    logger.info('正在解密cookies')

    cookies = decrypt.query_cookie("www.pixiv.net")
    for data in cookies:
        cookie.append(
            {'name': data[1], 'value': decrypt.chrome_decrypt(data[2]), 'domain': data[0]})
    cookies = decrypt.query_cookie(".pixiv.net")
    for data in cookies:
        cookie.append(
            {'name': data[1], 'value': decrypt.chrome_decrypt(data[2]), 'domain': data[0]})
    cookies = decrypt.query_cookie(".www.pixiv.net")
    for data in cookies:
        cookie.append(
            {'name': data[1], 'value': decrypt.chrome_decrypt(data[2]), 'domain': data[0]})

    logger.info(f'解密完成，数量 {len(cookie)}')
    return cookie

def get_cookies_by_selenium(rtime: int) -> list:
    """获取Google Chrome的cookies

    Args:
        rtime (int): cookie更新间隔

    Returns:
        (list): 包含所有pixiv的cookie的列表
    """
    global update_cookies
    cookie = []

    # 判断是否需要更新cookies
    mod_time = os.path.getmtime(COOKIE_PATH)
    relative_time = time.time() - mod_time
    if relative_time < rtime:
        update_cookies = False
        logger.info(f'无需更新cookies: 距上次更新 {relative_time} 秒')
    else:
        update_cookies = True
        logger.info(f'需要更新cookies: 距上次更新 {relative_time} 秒')

        # 判断Google Chrome是否在运行，是则结束
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

        logger.info('更新cookie文件')
        # 解密cookies
        logger.info('正在解密cookies')
        
        cookies = decrypt_by_selenium.decrypt()
        with open(COOKIE_PATH, 'w') as f:
            f.writelines(str(cookies))
            f.close()
        
        logger.info(f'解密完成，数量 {len(cookies)}')
    with open(COOKIE_PATH, 'r') as f:
        cookies = f.readlines()[0]
        f.close()

    return eval(cookies)

# 数据库相关操作
def dbexecute(sql):
    '''
    通用的数据库操作函数
    '''
    try:
        con = sqlite3.connect(SQLPATH)
        cur = con.cursor()
        cur.execute(sql)
        con.commit()
        res = cur.fetchall()
        cur.close()
        con.close()
    except Exception:
        logger.error(f'数据库操作错误，重试 {sys.exc_info()}')
        try:
            cur.close()
            con.close()
        except Exception:
            pass
        time.sleep(1)
        res = dbexecute(sql)
    return res


# 获取pixiv上的tags并翻译
class ValCheckError(Exception):  
    def __init__(self):  
        super().__init__('参数校验错误')

def var_check(*args):
    '''
    # 检查传入参数是否合法
    '''
    for var in args:
        if str(var)[:5] == 'ERROR':
            position = str(var).split(' ')[1]
            logger.error(f'传入参数错误，将跳过该函数执行 所在函数:{position}')
            return True
        

def analyse_bookmarks(cookie, rest_flag=2, limit=100) -> list:
    '''
    # 解析收藏接口
    - 接口名称: https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset=&limit=&rest=&lang=
    - `:return`: 所有需要调用的接口
    - `cookie`: pixiv上的cookie
    - `rest_flag`: 可见设置 (= 0,1,2),分别对应show(公开),hide(不公开),show+hide [默认为2]
    - `limit`: 每次获取的pid数目 (= 1,2,3,...,100) [默认为100(最大)]
    '''
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
            testurl_show = f'https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset=0&limit=1&rest=show&lang=zh'
            testurl_hide = f'https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset=0&limit=1&rest=hide&lang=zh'

            logger.debug('创建driver实例')

            options = Options()
            options.add_argument('--log-level=3')
            options.add_argument('--disable-gpu')
            options.add_argument('--headless')
            # 对chrome 129版本无头模式白屏的临时解决办法 (https://stackoverflow.com/questions/78996364/chrome-129-headless-shows-blank-window)
            options.add_argument("--window-position=-2400,-2400")
            service = Service(executable_path = CHROME_DRIVER_PATH)
            driver = webdriver.Chrome(options=options, service=service)

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
            driver.quit()

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
        logger.error(f'错误 {sys.exc_info()}')
        print(f'错误 {sys.exc_info()}')
        tb = sys.exc_info()[2]
        tb_list = traceback.format_tb(tb)
        ex = "".join(tb_list)
        logger.error(ex)
        print(ex)
        urls = f'ERROR {analyse_bookmarks.__name__}'
    return urls



def analyse_illusts_i(url, cookie) -> list:
    '''
    解析所有插画的信息
    - i就是individual的意思, 子线程
    - `url`: 接口URL
    - `cookie`: pixiv上的cookie
    - `:return`: 插画信息的列表, 忽略插画数量
    '''

    illustdata = []
    ignores = 0

    options = Options()
    options.add_argument('--log-level=3')
    options.add_argument('--disable-gpu')
    options.add_argument('--headless')
    options.add_argument("--window-position=-2400,-2400")
    service = Service(executable_path = CHROME_DRIVER_PATH)
    driver = webdriver.Chrome(options=options, service=service)

    driver.get(url)
    for cok in cookie:
        driver.add_cookie(cok)
    driver.refresh()

    WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located)
    logger.debug('接口所有元素加载完毕，准备解析...')

    # 解析每张插画的信息，添加到列表
    resp: dict = json.loads(
        driver.find_element(
            By.CSS_SELECTOR, 'body > pre'
        ).text
    )
    driver.quit()
    idata = resp['body']['works']
    for ildata in idata:
        if ildata['isMasked'] == True:
            logger.info(f"此插画已被隐藏，忽略本次请求 pid = {ildata['id']}")
            ignores += 1
        else:
            illustdata.append(ildata)

    time.sleep(0.1)
    return illustdata, ignores
def analyse_illusts_m(th_count, urls, cookie, recursion = 0) -> list:
    '''
    analyse_illusts_i的主线程, 整合信息
    - `th_count`: 线程数量
    - `urls`: 请求url列表
    - `cookie`: pixiv上的cookie
    - `recursion`: 判断递归次数
    '''
    signature = inspect.signature(analyse_illusts_m)
    for param in signature.parameters.values():
        if var_check(eval(param.name)) == 1:
            raise ValCheckError
    try:
        illdata = []
        all_th = {}
        retry_urls = []
        ignores = 0
        recursion += 1
        
        logger.info(f'创建线程池，线程数量: {th_count}')
        with ThreadPoolExecutor(max_workers=th_count) as pool:
            for u in urls:
                all_th[u] = pool.submit(analyse_illusts_i, u, cookie)
            wait(all_th.values(), return_when=ALL_COMPLETED)
            logger.info('所有线程运行完成')
            # 获取各线程返回值
            for u, t_res in all_th.items():
                result = t_res.result()
                if type(result) != type(None):
                    ill, ign = result
                    if not type(ill) == type(None):
                        illdata.extend(ill)
                        ignores += ign
                else:
                    logger.warning('线程池中某个函数返回了None, 在循环结束后将递归重试')
                    retry_urls.append(u)
            
        if retry_urls != [] and recursion <= 10:
            logger.info('出现重试可能为装饰器部分的问题，请检查装饰器是否打印了报错信息')
            logger.info(f'需要重试的url数量 {len(retry_urls)} 开始重试')
            retrydata = analyse_illusts_m(th_count, retry_urls, recursion)
            illdata.extend(retrydata)
            
        if recursion > 1:  
            logger.info(f'重试完成，总插画数量: {len(illdata)}，忽略数量: {ignores}，递归次数: {recursion}') 
        else:
            logger.info(f'所有插画信息获取完成，长度: {len(illdata)} 忽略数量: {ignores}')
    except Exception:
        logger.error(f'错误 {sys.exc_info()}')
        print(f'错误 {sys.exc_info()}')
        tb = sys.exc_info()[2]
        tb_list = traceback.format_tb(tb)
        ex = "".join(tb_list)
        logger.error(ex)
        print(ex)
        illdata = f'ERROR {analyse_illusts_m.__name__}'
    return illdata


def writeraw_to_db_i(illdata) -> list:
    '''
    `:return`: 状态
    '''
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
    data_to_modify = [0, 0, 0, 0, 0]
    var = {0: ['pid', pid], 1: ['jptag', jptag], 2: ['transtag', transtag],
           3: ['is_translated', is_translated], 4: ['is_private', is_private]}

    # 先查询已有信息，再判断是否需要修改
    sql = f'''SELECT * FROM illusts WHERE pid = {pid}'''
    olddata: list = dbexecute(sql)
    # 比较信息, 将不同之处添加至修改位置列表
    if olddata == []:     # 无信息
        # logger.debug('添加新信息')
        
        sql = f'''INSERT INTO illusts VALUES ({pid},"{jptag}",{transtag},{is_translated},{is_private})'''
        dbexecute(sql)
        status = ['0']
    elif olddata[0][1] == newdata[1]:
        # logger.debug('数据重复，无需添加')
        status = ['1']
    else:
        for i in range(len(olddata[0])):
            if olddata[0][i] != newdata[i]:
                data_to_modify[i] = 1
        for i in range(len(data_to_modify)):
            if data_to_modify[i] == 1 and i == 1:  # 只修改jptag和is_private值
                # logger.debug('更新jptag数据, 修改is_translated值')
                # 下面这里要加个""才行
                dbexecute(f'''
                                UPDATE illusts SET {var[1][0]} = "{var[1][1]}" where pid = {pid}
                                ''')
                dbexecute(f'''
                                UPDATE illusts SET {var[3][0]} = {var[3][1]} where pid = {pid}
                                ''')

            elif data_to_modify[i] == 1 and i == 4:
                # logger.debug('更新is_privated数据')
                dbexecute(f'''
                                UPDATE illusts SET {var[4][0]} = {var[4][1]} where pid = {pid}
                                ''')
            status = ['2']
    return status
def writeraw_to_db_m(th_count, illdata):
    """将所有tag提交至数据库

    Args:
        th_count (int): 线程数
        illdata (list): 插画详细信息
    """
    signature = inspect.signature(writeraw_to_db_m)
    for param in signature.parameters.values():
        if var_check(eval(param.name)) == 1:
            raise ValCheckError
    try:
        all_th = []
        result = []
        logger.info(f'创建线程池，线程数量: {th_count}')
        with ThreadPoolExecutor(max_workers=th_count) as pool:
            while len(illdata) > 0:
                i = illdata.pop(0)
                all_th.append(pool.submit(writeraw_to_db_i, i))
            wait(all_th, return_when=ALL_COMPLETED)
            for th in all_th:
                result.extend(th.result())
                if th.exception():
                    logger.error(f'运行时出现错误: {th.exception()}')
            logger.info(
                f"所有线程运行完成, 添加: {result.count('0')}  修改: {result.count('2')}  跳过: {result.count('1')}")
    except Exception:
        logger.error(f'错误 {sys.exc_info()}')
        print(f'错误 {sys.exc_info()}')
        tb = sys.exc_info()[2]
        tb_list = traceback.format_tb(tb)
        ex = "".join(tb_list)
        logger.error(ex)
        print(ex)


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
        # logger.debug(f'出现重复tag: {e}', exc_info = True)
        status = ['1']
    except Exception:
        logger.error(f'数据库操作错误，重试: {sys.exc_info()}')
        status = write_tags_to_db_i(tag)
    con.close()
    return status
def write_tags_to_db_m(th_count):
    '''
    提交原始tags
    '''
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
                    SELECT * FROM illusts WHERE is_translated = 0
                    ''')    # 数据结构: [(行1), (行2), ...], 每行: (值1, ...)

            for r in res:
                il_tag = eval(r[1])  # 单双引号问题, 不能用json.loads()
                tags.extend(il_tag)
            # 移除重复元素
            tags = list(set(tags))
            if len(tags) == 0:
                logger.info('没有需要写入的tag')

            while len(tags) > 0:
                tag = tags.pop(0)
                all_th.append(pool.submit(write_tags_to_db_i, tag))
            wait(all_th, return_when=ALL_COMPLETED)
            for th in all_th:
                result.extend(th.result())

                if th.exception():
                    logger.error(f'运行时出现错误: {th.exception()}')
            logger.info(
                f"所有线程运行完成, 添加: {result.count('0')}  跳过: {result.count('1')}")
    except Exception:
        logger.error(f'错误 {sys.exc_info()}')
        print(f'错误 {sys.exc_info()}')
        tb = sys.exc_info()[2]
        tb_list = traceback.format_tb(tb)
        ex = "".join(tb_list)
        logger.error(ex)
        print(ex)


i_count = 0
def notify_formatter(step=0.02):
    nflag = {}
    progress = 0
    while progress <= 1:
        progress += step
        nflag[progress] = False
    return nflag
nflag = notify_formatter()
def fetch_translated_tag_i(j, tot, cookie, priority=None):
    '''
    发送请求获取翻译后的tag \n
    最终将返回值写入.temp/result文件 \n
    返回值为 `dict : {'原tag': '翻译后的tag'}` \n
    - `j`: tag的名称
    - `tot`: tags总数
    - `cookie`: pixiv上的cookie
    - `priority`: 语言优先级
    '''
    global i_count
    priority = ['zh', 'en', 'zh_tw']
    # 转为URL编码, 一定需要加上safe参数, 因为pixiv有些tag有/, 比如: 挟まれたい谷間/魅惑の谷間
    jf = parse.quote(j, safe='')

    options = Options()
    options.add_argument('--log-level=3')
    options.add_argument('--disable-gpu')
    options.add_argument('--headless')
    options.add_argument("--window-position=-2400,-2400")
    service = Service(executable_path = CHROME_DRIVER_PATH)
    driver = webdriver.Chrome(options=options, service=service)
    def get():
        try:
            driver.get(f'https://www.pixiv.net/ajax/search/tags/{jf}?lang=zh')
            for cok in cookie:
                driver.add_cookie(cok)
            driver.refresh()
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located)
        except Exception:
            logger.error(f'请求tag接口时出错,重试 {sys.exc_info()}')
            get()
    get()
    
    resp: dict = json.loads(
        driver.find_element(
            By.CSS_SELECTOR, 'body > pre'
        ).text
    )
    
    driver.quit()
    if type(resp) == type(None):
        logger.warning(f'服务器返回值不正确 此次请求tag: {j}')
        with open(TAG_LOG_PATH, 'a') as f:
            f.write(str(time.strftime("%b %d %Y %H:%M:%S", time.localtime())))
            f.write(f'请求tag {j}')
            f.write('\n')
            f.close()
        logger.info('失败的tag已写入日志')
    else:
        tagTranslation = resp['body']['tagTranslation']
        transtag = ''
        if tagTranslation == []:
            # print(tagTranslation)
            logger.info(f'无tag {j} 的翻译')
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
                        for _ in trans.keys():
                           if trans[_] == available:
                               av.append(_)
                logger.info(f'tag {j} 无目标语言的翻译 & 可用的语言 {av}')
                result = {j: j}
            else:
                result = {j: transtag}

    i_count+=1
    for i in nflag:
        if i_count / tot > i and nflag[i] == False:
            logger.info(f'fetch_translated_tag 当前进度(近似值): {i.__round__(5)}')
            nflag[i] = True
    # 写入文件
    if result != None:
        def writefile():
            # 通过递归防止写入失败
            try:
                with open(CWD + '\\temp\\result', 'a', encoding = 'utf-8') as f:
                    f.write(str(result) + '\n')
                    f.close()
            except Exception:
                logger.error(f'错误 {sys.exc_info()}')
                print(f'错误 {sys.exc_info()}')
                tb = sys.exc_info()[2]
                tb_list = traceback.format_tb(tb)
                ex = "".join(tb_list)
                logger.error(ex)
                print(ex)
                logger.info('重试写入...')
                writefile()
        writefile()
    
    # return result
def fetch_translated_tag_m(th_count, cookie) -> list:
    signature = inspect.signature(fetch_translated_tag_m)
    for param in signature.parameters.values():
        if var_check(eval(param.name)) == 1:
            raise ValCheckError
    try:
        jptags = []
        result = []

        # 只找出未翻译的tag
        res = dbexecute('''
                    SELECT * FROM tags WHERE transtag == ''
                    ''')

        for r in res:
            (jptag, _) = r
            jptags.append(jptag)
        logger.info(f'已从数据库获取 {len(jptags)} 个tag')
        logger.info(f'创建线程池，线程数量: {th_count}')

        with ThreadPoolExecutor(max_workers=th_count) as pool:
            all_th = []
            for j in jptags:
                all_th.append(pool.submit(fetch_translated_tag_i, j, len(jptags), cookie))

            wait(all_th, return_when=ALL_COMPLETED)
            # 读取文件
            logger.debug('tag翻译完成，从文件中读取结果')
            with open(CWD + '\\temp\\result', 'r', encoding = 'utf-8') as f:
                lines = f.readlines()
                for line in lines:
                    dic = eval(line)
                    result.append(dic)
                f.close()

            s = 0
            for r in result:
                if type(r) != type(None):
                    if r.keys == r.values:  # 根据子线程出现无翻译时的操作进行判断
                        s += 1
            
            logger.info(f'tag翻译获取完成, 共 {len(result)} 个, 无翻译 {s} 个')
    except Exception:
        logger.error(f'错误 {sys.exc_info()}')
        print(f'错误 {sys.exc_info()}')
        tb = sys.exc_info()[2]
        tb_list = traceback.format_tb(tb)
        ex = "".join(tb_list)
        logger.error(ex)
        print(ex)
        result = f'ERROR {fetch_translated_tag_m.__name__}'
    return result


def write_transtags_to_db_i(tran: dict):
    '''
    `tran`: 需要提交的tags (jp:tr)
    '''
    if type(tran) == type(None):
        logger.warning('参数为NoneType类型，忽略')
    else:
        transtag = list(tran.values())[0]
        jptag = list(tran.keys())[0]
    # 注意sql语句transtag用双引号！
    # 否则执行sql时会有syntax error
    dbexecute(
        f'''UPDATE tags SET transtag = "{transtag}" WHERE jptag = "{jptag}"''')
def write_transtags_to_db_m(th_count, trans):
    """提交翻译后的tags

    Args:
        th_count (int): 线程数
        trans (list): 包含原tag与翻译后tag字典的列表集合
    """
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
            wait(all_th, return_when=ALL_COMPLETED)
        logger.info('翻译后的tag已提交至表tags')
    except Exception:
        logger.error(f'错误 {sys.exc_info()}')
        print(f'错误 {sys.exc_info()}')
        tb = sys.exc_info()[2]
        tb_list = traceback.format_tb(tb)
        ex = "".join(tb_list)
        logger.error(ex)
        print(ex)


def transtag_return_i(r0):
    if type(r0) != type(None):
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
    else:
        logger.warning('参数为NoneType类型，忽略')
def transtag_return_m(th_count):
    '''
    上传翻译后的tags至表illust
    '''
    signature = inspect.signature(transtag_return_m)
    for param in signature.parameters.values():
        if var_check(eval(param.name)) == 1:
            raise ValCheckError()
    try:
        all_th = []
        logger.info(f'创建线程池，线程数量: {th_count}')
        with ThreadPoolExecutor(max_workers=th_count) as pool:
            resp0 = dbexecute('''
                        SELECT * FROM illusts
                        ''')
            for r0 in resp0:
                all_th.append(pool.submit(transtag_return_i, r0))

            wait(all_th, return_when=ALL_COMPLETED)
        logger.info('翻译后的tag已提交至表illust')
    except Exception:
        logger.error(f'错误 {sys.exc_info()}')
        print(f'错误 {sys.exc_info()}')
        tb = sys.exc_info()[2]
        tb_list = traceback.format_tb(tb)
        ex = "".join(tb_list)
        logger.error(ex)
        print(ex)


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
        with open(CWD + '\\temp\\result', 'r', encoding = 'utf-8') as f:
            lines = f.readlines()
            f.close()
        if lines != []:
            logger.info('备份上次运行时fetch_translated_tag_i函数的返回值')
            timestamp = os.path.getmtime(CWD + '\\temp\\result').__round__(0)
            SrcModifyTime = datetime.datetime.fromtimestamp(timestamp)
            shutil.copy(CWD + '\\temp\\result', CWD + '\\temp\\history\\' + str(SrcModifyTime).replace(':','-'))

            with open(CWD + '\\temp\\result', 'w', encoding = 'utf-8') as f:
                f.write('')
                f.close()

        print('请选择模式: 1-更新tags至本地数据库    2-基于本地数据库进行插画搜索   3-同步fetch_translated_tag_i函数获取的有效数据  4-退出')
        mode = input('模式 = ')
        if mode == '1':
            start = time.time()
            cookie = get_cookies_by_selenium(rtime=COOKIE_EXPIRED_TIME)
            URLs = analyse_bookmarks(cookie=cookie)
            # debug:
            # URLs = ['https://www.pixiv.net/ajax/user/71963925/illusts/bookmarks?tag=&offset=187&limit=1&rest=hide']

            
            illdata = analyse_illusts_m(ANALYSE_ILLUST_THREADS, URLs, cookie)
            # debug:
            #illdata = [{'id': '79862254', 'title': 'タシュケント♡', 'illustType': 0, 'xRestrict': 0, 'restrict': 0, 'sl': 2, 'url': 'https://i.pximg.net/c/250x250_80_a2/img-master/img/2020/03/03/09/31/57/79862254_p0_square1200.jpg', 'description': '', 'tags': ['タシュケント', 'アズールレーン', 'タシュケント(アズールレーン)', 'イラスト', '鯛焼き', 'アズールレーン10000users入り'], 'userId': '9216952', 'userName': 'AppleCaramel', 'width': 1800, 'height': 2546, 'pageCount': 1, 'isBookmarkable': True, 'bookmarkData': {'id': '25192310391', 'private': False}, 'alt': '#タシュケント タシュケント♡ - AppleCaramel的插画', 'titleCaptionTranslation': {'workTitle': None, 'workCaption': None}, 'createDate': '2020-03-03T09:31:57+09:00', 'updateDate': '2020-03-03T09:31:57+09:00', 'isUnlisted': False, 'isMasked': False, 'aiType': 0, 'profileImageUrl': 'https://i.pximg.net/user-profile/img/2022/10/24/02/12/49/23505973_7d9aa88560c5115b85cc29749ed40e28_50.jpg'},
            #{'id': '117717637', 'title': 'おしごと終わりにハグしてくれる天使', 'illustType': 0, 'xRestrict': 0, 'restrict': 0, 'sl': 4, 'url': 'https://i.pximg.net/c/250x250_80_a2/custom-thumb/img/2024/04/10/17/30/02/117717637_p0_custom1200.jpg', 'description': '', 'tags': ['オリジナル', '女の子', '緑髪', '天使', 'ハグ', '巨乳', 'ぱんつ', 'オリジナル1000users入り'], 'userId': '29164302', 'userName': '緑風マルト🌿', 'width': 1296, 'height': 1812, 'pageCount': 1, 'isBookmarkable': True, 'bookmarkData': {'id': '25109862018', 'private': False}, 'alt': '#オリジナル おしごと終わりにハグしてくれる天使 - 緑風マルト🌿的插画', 'titleCaptionTranslation': {'workTitle': None, 'workCaption': None}, 'createDate': '2024-04-10T17:30:02+09:00', 'updateDate': '2024-04-10T17:30:02+09:00', 'isUnlisted': False, 'isMasked': False, 'aiType': 1, 'profileImageUrl': 'https://i.pximg.net/user-profile/img/2024/01/25/15/56/10/25434619_c70d86172914664ea2b15cec94bc0afd_50.png'},
            #{'id': '84450882', 'title': 'ネコ耳墨ちゃん🐈', 'illustType': 0, 'xRestrict': 0, 'restrict': 0, 'sl': 2, 'url': 'https://i.pximg.net/c/250x250_80_a2/img-master/img/2020/09/18/19/44/35/84450882_p0_square1200.jpg', 'description': '', 'tags': ['彼女、お借りします', 'かのかり', '桜沢墨', '猫', '猫耳', '制服', '白ニーソ', '拾ってください', '彼女、お借りします5000users入り'], 'userId': '38436050', 'userName': 'ゆきうなぎ＠土曜東ス88a', 'width': 2894, 'height': 4093, 'pageCount': 1, 'isBookmarkable': True, 'bookmarkData': {'id': '24948220443', 'private': False}, 'alt': '#彼女、お借りします ネコ耳墨ちゃん🐈 - ゆきうなぎ＠土曜東ス88a的插画', 'titleCaptionTranslation': {'workTitle': None, 'workCaption': None}, 'createDate': '2020-09-18T19:44:35+09:00', 'updateDate': '2020-09-18T19:44:35+09:00', 'isUnlisted': False, 'isMasked': False, 'aiType': 0, 'profileImageUrl': 'https://i.pximg.net/user-profile/img/2020/02/22/00/11/25/17966339_a51ca7e8a3aca581fc87021488e21479_50.jpg'},
            #]


            writeraw_to_db_m(WRITERAW_TO_DB_THREADS, illdata)
            write_tags_to_db_m(WRITE_TAGS_TO_DB_THREADS)


            trans = fetch_translated_tag_m(FETCH_TRANSLATED_TAG_THREADS, cookie)
            
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
                        target_key = input('请选择其中一个结果: ')
                        if not target_key in target_keys:
                            print('未匹配, 请重新选择: ')
                            key = ''
                            continue
                        else:
                            print(f'pids: {set(list(df[target_key].dropna().astype(int).sort_values(ascending = False)))}')
                    elif cmd_key.split(' ')[0] == '-f':
                        key = cmd_key.split(' ')[-1]
                        try:
                            print(f'pids: {set(list(df[key].dropna().astype(int).sort_values(ascending = False)))}')
                        except Exception:
                            print('出现错误')
                            print(sys.exc_info())
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
                                target_key = input('请选择其中一个结果: ')
                                if not target_key in target_keys:
                                    print('未匹配, 请重新选择: ')
                                    continue
                                else:
                                    plist.extend(set(list(df[target_key].dropna().astype(int))))
                                    s += 1
                                    break
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
            with open(CWD + '\\temp\\history\\' + str(SrcModifyTime).replace(':','-'), 'r', encoding = 'utf-8') as f:
                lines = f.readlines()
                for line in lines:
                    dic = eval(line)
                    result.append(dic)
                f.close()
            s = 0
            for r in result:
                if type(r) != type(None):
                    if r.keys == r.values:
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
            print('未知的指令')
        print('')
def start_logging():  
    # 清除之前的日志（可选）  
    text_widget.delete(1.0, tk.END)  
    # 开始记录日志  
    def run_main():     #将main函数作为线程运行
        th = threading.Thread(target=main)
        th.start()
    root.after(1000, run_main)  

button = ttk.Button(root, text="运行主程序", command=start_logging)  
button.pack(pady=20)

if __name__ == "__main__":
    root.mainloop()