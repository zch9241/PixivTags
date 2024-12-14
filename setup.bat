chcp 65001
REM 创建src文件夹和其下的文件
mkdir src
cd src
(
    echo ANALYSE_ILLUST_THREADS: int = 10
    echo WRITERAW_TO_DB_THREADS: int = 10
    echo WRITE_TAGS_TO_DB_THREADS: int = 10
    echo FETCH_TRANSLATED_TAG_THREADS: int = 8
    echo WRITE_TRANSTAGS_TO_DB_THREADS: int = 10
    echo TRANSTAG_RETURN_THREADS: int = 10
    echo UID: str = ''                            # 你的pixiv UID
    echo CHROME_PATH: str = r''                   # Google Chrome主程序位置
    echo COOKIE_EXPIRED_TIME = 43200              # 重新获取cookie的时间间隔
) > config.py
type nul > cookies_modify_time
type nul > cookies.json
cd ..
REM 创建temp/history文件夹
cd temp
mkdir history
echo 初始化完成
pause