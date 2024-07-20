import tkinter as tk  
from tkinter import scrolledtext  
from tkinter import ttk  
import logging  
import threading
import time  



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
  
# 创建日志器和日志处理器  
logger = logging.getLogger('my_logger')  
logger.setLevel(logging.DEBUG)
  
# 创建一个Tkinter窗口和文本框
root = tk.Tk()
text_widget = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=80, height=20)
text_widget.pack(fill=tk.BOTH, expand=True)
text_widget.config(state='disabled')  # 禁止直接编辑
  
# 将TkinterLogHandler添加到日志器  
handler = TkinterLogHandler(text_widget)  
logger.addHandler(handler) 



def _main():
    while True:
        for i in range(5):
            logger.info(i)
            time.sleep(1)

thread = threading.Thread(target=_main)  
thread.start()

if __name__ == "__main__":  
    root.mainloop()