chcp 65001
REM 创建src文件夹和其下的文件
mkdir src
cd src
echo UID: str = ''                            # 你的pixiv UID>> config.py
echo ENABLE_CLASH_PROXY = False>> config.py
echo CLASH_HTTP_PROXY: str = ''>> config.py
echo CLASH_API_HOST: str = ''>> config.py
echo CLASH_API_SECRET: str = ''>> config.py
echo CLASH_SELECTOR_NAME: str = ''>> config.py
echo CLASH_NODES_FILTER: list = []>> config.py
type nul > cookies.json
echo 初始化完成
pause
