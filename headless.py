
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument("--window-position=-2400,-2400")
options.add_argument("--headless")

driver = webdriver.Chrome(options=options)
driver.get('https://www.baidu.com')
print(driver.title)