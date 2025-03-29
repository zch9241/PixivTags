chcp 65001
REM 创建src文件夹和其下的文件
mkdir src
cd src
echo UID: str = ''                            # 你的pixiv UID>> config.py
echo CHROME_PATH: str = r''                   # Google Chrome主程序位置>> config.py
echo COOKIE_EXPIRED_TIME = 43200              # 重新获取cookie的时间间隔(s)>> config.py
type nul > cookies_modify_time
type nul > cookies.json
echo 初始化完成
pause
