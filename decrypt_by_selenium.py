from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import os


def decrypt():
    """
    通过指定本地user data文件夹以获取对应网站的cookie \n
    这种方式应该是最稳妥的 \n
    - returns (list): 包含cookie的列表
    """
    user_data_path = os.path.expanduser(os.path.join(
        os.environ['LOCALAPPDATA'], r'Google\Chrome\User Data'))

    options = Options()
    options.add_argument('--log-level=3')
    options.add_argument('--disable-gpu')
    options.add_argument(f'user-data-dir={user_data_path}')

    driver_path = os.getcwd() + '.\\bin\\chromedriver.exe'
    service = Service(executable_path = driver_path)

    driver = webdriver.Chrome(options = options, service = service)

    driver.get('https://www.pixiv.net')
    cookies = driver.get_cookies()
    driver.quit()
    return cookies
