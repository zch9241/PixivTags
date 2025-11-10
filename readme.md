# PixivTags

## 简介

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

2. 可以选择动态切换IP来规避限流（本程序仅实现了基于clash verge API切换IP的功能）

```Python
# src/config.py
ENABLE_CLASH_PROXY = False                            # 修改为True
CLASH_HTTP_PROXY: str = ''                            # 修改为clash verge的http代理
CLASH_API_HOST: str = ''                              # 修改为clash verge的外部控制器监听地址
CLASH_API_SECRET: str = ''                            # 修改为clash verge的外部控制器API访问密钥（若有）
CLASH_SELECTOR_NAME: str = ''                         # 修改为clash verge代理组选择器名称
CLASH_NODES_FILTER: list = []                         # 修改为想要使用的节点部分名称（可选）（根据节点名称选择对应地区的节点）
```

示例：

```Python
ENABLE_CLASH_PROXY = True
CLASH_HTTP_PROXY: str = 'http://127.0.0.1:7897'
CLASH_API_HOST: str = 'http://127.0.0.1:9097'
CLASH_API_SECRET: str = '123456'
CLASH_SELECTOR_NAME: str = 'xyz Cloud'
CLASH_NODES_FILTER: list = ['香港', '日本', '美国']
```

## 版权声明

本项目受严格的使用条款约束，包含但不限于：

- 禁止商业使用条款
- 再分发限制条款
- 免责声明

**完整法律文本请参见 [LICENSE](LICENSE) 文件**
