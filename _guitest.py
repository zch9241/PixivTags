from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED
import datetime
from difflib import get_close_matches
import json
import logging
import os
import pandas as pd
import psutil
import re
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
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
from win10toast import ToastNotifier
  
def update_progress(progress_var, total):  
    for i in range(total):  
        # 模拟长时间运行的任务  
        time.sleep(0.1)  
        progress_var.set(i + 1)  
        root.update_idletasks()  # 更新GUI以显示新的进度  


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


# 创建一个Tkinter窗口和文本框
root = tk.Tk()
font_ = Font(family="Consolas", size=8, weight="bold")

text_widget = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=120, height=30, font=font_)
text_widget.pack(fill=tk.BOTH, expand=True)
text_widget.config(state='disabled')  # 禁止直接编辑

progress_var = tk.IntVar()  
progress_var.set(0)

progress_bar = ttk.Progressbar(root, orient="horizontal", length=600, mode="determinate", variable=progress_var)  
progress_bar.pack(pady=20)  
  
button = tk.Button(root, text="Start", command=lambda: update_progress(progress_var, 100))  
button.pack(pady=20)  

# 将TkinterLogHandler添加到日志器  
handler = TkinterLogHandler(text_widget)  
formatter = logging.Formatter(
    "[%(asctime)s %(name)s %(thread)d %(funcName)s] %(levelname)s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler) 
root.mainloop()