from playwright.sync_api import sync_playwright
import os
import json

def load_cookies():
    with open(r"C:\Users\chaos_z\Downloads\www.pixiv.net_json_1762072076938.json", "r", encoding="utf-8") as f:
        cookies = json.load(f)
    
    for cookie in cookies:
        if "sameSite" in cookie:
            if cookie["sameSite"].lower() == "unspecified":
                cookie["sameSite"] = 'Lax'
            elif cookie["sameSite"].lower() == "no_restriction":
                cookie["sameSite"] = 'None'
    return cookies

def auth_test(cookies):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel='chrome')
        context = browser.new_context()
        context.add_cookies(cookies)
        
        page = context.new_page()
        page.goto("https://www.pixiv.net")
        
        os.system("pause")

auth_test(load_cookies())
