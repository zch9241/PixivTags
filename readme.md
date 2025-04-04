# PixivTags

## 简介

`PixivTags` 是一个获取用户在pixiv上收藏插画tags的爬虫，它旨在解决pixiv网站上用户无法对自己收藏的插画进行搜索的问题

## 重要说明

1. 确保你安装了 `Python >=3.12` (程序在其他版本可能出现兼容性问题)
2. 推荐使用 `Visual Studio Code` 运行本程序
3. 本项目利用`Google Chrome`保存的cookie实现登录，所以请**提前使用该浏览器登录pixiv**以保留登录凭据，并在程序获取cookie时**关闭浏览器**，否则会报错

## 运行说明

1. 安装依赖

   ```cmd
   pip install -r requirements.txt
   playwright install
   ```

2. 运行项目根目录下的`setup.bat`

   **注意**：运行此批处理文件可能会被Windows拦截，请点击`更多信息`，然后点击`仍要运行`

   若不放心，可以自行阅读 [源代码](setup.bat)

   (只是创建一些文件而已...)

3. 编辑src文件夹下的`config.py`

   **注意**：修改时请保留单引号！

   ```Python
   UID: str = ''    # 修改为你的UID
   CHROME_PATH: str = r''     # 修改为Google Chrome主程序位置
4. 运行项目根目录下的`main.py`

## 拓展说明

1. 关于`config.py`的说明

   ```Python
   UID: str = ''                            # 你的pixiv UID
   CHROME_PATH: str = r''                   # Google Chrome主程序位置
   COOKIE_EXPIRED_TIME = 43200              # 重新获取cookie的时间间隔，单位为秒

2. 其他可调参数（**若不清楚作用请不要随意改动**）

   **main.py**

   - 函数 `get_cookies`:
      - 参数 `forced`: 强制更新cookie
   - 函数 `analyse_bookmarks`:
      - 参数 `rest_flag`：获取的收藏插画的可见性 (0=公开, 1=不公开, 2=全部)
   - 函数 `analyse_illusts_main`:
      - 参数 `max_concurrency`，最大协程数量（如果频繁出现429错误请减小此数值）
   - 函数 `fetch_translated_tag_main`:
      - 参数 `priority`，翻译语言优先级
      - 参数 `max_concurrency`，最大协程数量如果频繁出现429错误请减小此数值）

   **search.py**

   - 类 `PixivSearchCLI`:

      - 参数 `page_size`: 分页模式的默认分页数量

## 版权声明

本项目受严格的使用条款约束，包含但不限于：

- 禁止商业使用条款
- 再分发限制条款
- 免责声明

**完整法律文本请参见 [LICENSE](LICENSE) 文件**
