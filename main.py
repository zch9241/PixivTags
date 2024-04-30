from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import logging

from decrypt import *


# 解密cookies
cookie = {}
cookies = query_cookie("www.pixiv.net")
for data in cookies:
    cookie[data[1]] = chrome_decrypt(data[2])

cookies = query_cookie(".pixiv.net")
for data in cookies:
    cookie[data[1]] = chrome_decrypt(data[2])





driver = webdriver.Chrome()
driver.get_network_conditions


logger = logging.getLogger('logger')

handler = logging.StreamHandler()

logger.setLevel(logging.DEBUG)
handler.setLevel(logging.DEBUG)

formatter = logging.Formatter("[%(asctime)s %(name)s %(thread)d %(funcName)s] %(levelname)s %(message)s")
handler.setFormatter(formatter)

logger.addHandler(handler)





