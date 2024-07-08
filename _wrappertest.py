import sys
from pathlib import Path
# 获取当前脚本的目录
current_dir = Path(__file__).resolve().parent
# 获取上级目录
parent_dir = current_dir.parent
# 将上级目录添加到sys.path
sys.path.append(str(parent_dir))

import json
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import logging
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED
from time import sleep
from urllib import parse
import traceback
import re
from difflib import get_close_matches
import time
import psutil
import shutil
import os
import sqlite3
from win10toast import ToastNotifier

import decrypt
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
SQLPATH = CWD + '\src\illdata.db'
COOKIE_PATH = CWD + '\src\Cookies'

# 日志初始化
logger = logging.getLogger('logger')
handler = logging.StreamHandler()
logger.setLevel(logging.DEBUG)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "[%(asctime)s %(name)s %(thread)d %(funcName)s] %(levelname)s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

def get_cookies(rtime: int, ignore = False):
    """获取Google Chrome的cookies

    Args:
        rtime (int): cookie更新间隔
        ignore (Bool): 是否忽略更新

    Returns:
        (list): 包含所有pixiv的cookie列表
    """
    global update_cookies
    cookie = []

    # 判断是否需要更新cookies
    mod_time = os.path.getmtime(COOKIE_PATH)
    relative_time = time.time() - mod_time
    if ignore == True:
        update_cookies = False
    elif relative_time < rtime:
        update_cookies = False
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

    logger.info(f'解密完成，数量 {len(cookie)}')
    return cookie

cookie = get_cookies(0, True)

