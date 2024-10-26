# PixivTags

## 简介

`PixivTags` 是一个获取用户在pixiv上收藏插画tags的爬虫，它旨在解决pixiv网站上用户无法对自己收藏的插画进行搜索的问题

## 安装指南

1. 确保你安装了 `Python 3.10` (程序在其他版本可能出现兼容性问题)
2. 推荐使用 `Visual Code Studio` 运行本程序
3. 克隆仓库

   ```bash
   git clone https://github.com/zch9241/PixivTags.git
4. 进入项目目录并安装依赖项（请自行阅读根目录下`main.py`与`decrypt.py`的源代码）

## 使用说明

1. 编辑项目根目录下的`config.py`

   ```Python
   UID: str = ''    # 修改为你的UID
2. (使用vs code)运行项目根目录下的`main.py`

3. 在 GUI 界面点击“运行主程序”，并在终端输入你想使用的运行模式

## 拓展说明

1. 关于`config.py`

   ```Python
   ANALYSE_ILLUST_THREADS: int = 10         # 函数analyse_illusts_i 的最大线程数量
   WRITERAW_TO_DB_THREADS: int = 10         # 同理
   WRITE_TAGS_TO_DB_THREADS: int = 10
   FETCH_TRANSLATED_TAG_THREADS: int = 8
   WRITE_TRANSTAGS_TO_DB_THREADS: int = 10
   TRANSTAG_RETURN_THREADS: int = 10
   UID: str = '71963925'                    # 你的pixiv UID
   COOKIE_EXPIRED_TIME = 43200              # 重新获取cookie的时间间隔

2. 本项目利用`Google Chrome`保存的cookie实现登录，所以请提前使用上述浏览器登录pixiv

3. 本项目使用`selenium`实现浏览器自动化，请[下载](https://developer.chrome.com/docs/chromedriver/downloads/version-selection)与Chrome版本相同的`chromedriver`(需要魔法)

4. 本项目不提供访问pixiv的方法，请自行解决网络问题

## 版权  
  
© 2024 zch9241. All rights reserved.  
  
本项目版权归 [zch9241] 所有，未经授权不得复制、分发或用于商业目的。
