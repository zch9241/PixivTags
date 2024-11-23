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
import yaml


import decrypt
import decrypt_by_selenium
from src import config


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
COOKIE_PATH = CWD + r'\src\cookies.yaml'
TAG_LOG_PATH = CWD + r'\logs\tag\content.log'
CHROME_DRIVER_PATH = CWD + r'\bin\chromedriver.exe' 

with open(COOKIE_PATH, 'r') as f:
    configs = f.read()
    config_dict = yaml.load(configs, yaml.Loader)
    cookies = config_dict['Cookies'][0]
    f.close()


options = Options()
options.add_argument('--log-level=3')
options.add_argument('--disable-gpu')
options.add_argument('--headless')
# 对chrome 129版本无头模式白屏的临时解决办法 (https://stackoverflow.com/questions/78996364/chrome-129-headless-shows-blank-window)
options.add_argument("--window-position=-2400,-2400")
service = Service(executable_path = CHROME_DRIVER_PATH)
driver = webdriver.Chrome(options=options, service=service)


pid = '119639140'

def get_bookmark(pid):
    api = 'https://www.pixiv.net/touch/ajax/illust/details?illust_id='
    driver.get(api + pid)
    for cok in cookies:
        driver.add_cookie(cok)
    driver.refresh()
    resp: dict = json.loads(
        driver.find_element(
            By.CSS_SELECTOR, 'body > pre'
        ).text
    )
    driver.quit()
    bookmark_user_total = str(resp['body']['illust_details']['bookmark_user_total'])
    rating_count = resp['body']['illust_details']['rating_count']
    rating_view = resp['body']['illust_details']['rating_view']
    
    return (rating_count, bookmark_user_total, rating_view) # 三者均为str类型，根据pixiv上页面重新排序
start = time.time()
s = get_bookmark(pid)
end = time.time()
print(s)
print(end - start)