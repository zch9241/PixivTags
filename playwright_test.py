from playwright.sync_api import sync_playwright
import os
import json

def decrypt():
    with sync_playwright() as p:
        # 使用chrome的用户数据时需要关闭已运行的浏览器实例
        browser = p.chromium.launch_persistent_context(headless=True,
            executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            user_data_dir=os.path.expanduser(
                os.path.join(os.environ['LOCALAPPDATA'], r'Google\Chrome\User Data'))
            )
        with open(r'.\src\cookies.json','w') as f:
            f.write(json.dumps(browser.cookies('https://www.pixiv.net')))
        browser.storage_state(path = 'cookie.json')
        # 关闭浏览器
        browser.close()

def test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe')
        page = browser.new_page()
        page.goto('https://www.baidu.com')
        print(page.title())
        page.goto('https://www.google.com')
        print(page.title())
        browser.close()

if __name__ == "__main__":
    decrypt()
