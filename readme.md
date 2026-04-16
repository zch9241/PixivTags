# PixivTags

## 简介

**DEPRECATED**

**pixiv官方已上线本项目功能，本项目弃用**

`PixivTags` 是一个获取用户在pixiv上收藏插画tags的爬虫，它旨在解决pixiv网站上用户无法对自己收藏的插画进行搜索的问题

## 重要说明

1. 确保你安装了 `Python >=3.12` (程序在其他版本可能出现兼容性问题)
2. 推荐使用 `Visual Studio Code` 运行本程序
3. 由于 chrome 增强了安全性，本程序弃用了获取cookie的功能，请使用 [Cookie-Editor](https://chromewebstore.google.com/detail/cookie-editor/ookdjilphngeeeghgngjabigmpepanpl) 这个 chrome 扩展导出 cookie

## 运行方法

1. 安装依赖

   ```cmd
   pip install -r requirements.txt
   python -m playwright install
   ```

2. 运行项目根目录下的`setup.bat`

   运行此批处理文件可能会被Windows拦截，请点击`更多信息`，然后点击`仍要运行`

   (只是创建一些文件而已...)

3. 编辑src文件夹下的`config.py`

   ```Python
   UID: str = ''    # 修改为你的UID，修改时请保留单引号！
   ```

   **示例**：

   ```Python
   UID: str = '12345678'
   ```

4. 将 `Cookie-Editor` 导出的 **json 格式** cookie 文件内容复制到 .\src\cookies.json 中

5. 运行项目根目录下的`main.py`

## 拓展说明

1. 其他可调参数（**若不清楚作用请不要随意改动**）

   **main.py**

   - 函数 `get_cookies`:
      - 参数 `forced`: 强制更新cookie
   - 函数 `analyse_bookmarks`:
      - 参数 `rest_flag`：获取的收藏插画的可见性 (0=公开, 1=不公开, 2=全部)
   - 函数 `analyse_illusts_main`:
      - 参数 `max_concurrency`，最大协程数量（如果频繁出现429错误请减小此数值）
   - 函数 `fetch_translated_tag_main`:
      - 参数 `priority`，翻译语言优先级
      - 参数 `max_concurrency`，最大协程数量（如果频繁出现429错误请减小此数值）

   **search.py**

   - 类 `PixivSearchCLI`:

      - 参数 `page_size`: 分页模式的默认分页数量

2. 当程序提示触发限流时，可以尝试切换IP

## 版权声明

本项目受严格的使用条款约束，包含但不限于：

- 禁止商业使用条款
- 再分发限制条款
- 免责声明

**完整法律文本请参见 [LICENSE](LICENSE) 文件**
