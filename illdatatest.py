import json
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import logging
from concurrent.futures import ThreadPoolExecutor,wait,ALL_COMPLETED


from decrypt import *


UID :str = '71963925'
ANALYSE_ILLUST_THREADS: int = 10

logger = logging.getLogger('logger')

handler = logging.StreamHandler()

logger.setLevel(logging.DEBUG)
handler.setLevel(logging.DEBUG)

formatter = logging.Formatter("[%(asctime)s %(name)s %(thread)d %(funcName)s] %(levelname)s %(message)s")
handler.setFormatter(formatter)

logger.addHandler(handler)


CWD = os.getcwd()
SQLPATH = CWD + '\src\illdata.db'

illdata = [{'id': '79862254', 'title': 'タシュケント♡', 'illustType': 0, 'xRestrict': 0, 'restrict': 0, 'sl': 2, 'url': 'https://i.pximg.net/c/250x250_80_a2/img-master/img/2020/03/03/09/31/57/79862254_p0_square1200.jpg', 'description': '', 'tags': ['タシュケント', 'アズールレーン', 'タシュケント(アズールレーン)', 'イラスト', '鯛焼き', 'アズールレーン10000users入り'], 'userId': '9216952', 'userName': 'AppleCaramel', 'width': 1800, 'height': 2546, 'pageCount': 1, 'isBookmarkable': True, 'bookmarkData': {'id': '25192310391', 'private': False}, 'alt': '#タシュケント タシュケント♡ - AppleCaramel的插画', 'titleCaptionTranslation': {'workTitle': None, 'workCaption': None}, 'createDate': '2020-03-03T09:31:57+09:00', 'updateDate': '2020-03-03T09:31:57+09:00', 'isUnlisted': False, 'isMasked': False, 'aiType': 0, 'profileImageUrl': 'https://i.pximg.net/user-profile/img/2022/10/24/02/12/49/23505973_7d9aa88560c5115b85cc29749ed40e28_50.jpg'},
{'id': '117717637', 'title': 'おしごと終わりにハグしてくれる天使', 'illustType': 0, 'xRestrict': 0, 'restrict': 0, 'sl': 4, 'url': 'https://i.pximg.net/c/250x250_80_a2/custom-thumb/img/2024/04/10/17/30/02/117717637_p0_custom1200.jpg', 'description': '', 'tags': ['オリジナル', '女の子', '緑髪', '天使', 'ハグ', '巨乳', 'ぱんつ', 'オリジナル1000users入り'], 'userId': '29164302', 'userName': '緑風マルト🌿', 'width': 1296, 'height': 1812, 'pageCount': 1, 'isBookmarkable': True, 'bookmarkData': {'id': '25109862018', 'private': False}, 'alt': '#オリジナル おしごと終わりにハグしてくれる天使 - 緑風マルト🌿的插画', 'titleCaptionTranslation': {'workTitle': None, 'workCaption': None}, 'createDate': '2024-04-10T17:30:02+09:00', 'updateDate': '2024-04-10T17:30:02+09:00', 'isUnlisted': False, 'isMasked': False, 'aiType': 1, 'profileImageUrl': 'https://i.pximg.net/user-profile/img/2024/01/25/15/56/10/25434619_c70d86172914664ea2b15cec94bc0afd_50.png'},
{'id': '84450882', 'title': 'ネコ耳墨ちゃん🐈', 'illustType': 0, 'xRestrict': 0, 'restrict': 0, 'sl': 2, 'url': 'https://i.pximg.net/c/250x250_80_a2/img-master/img/2020/09/18/19/44/35/84450882_p0_square1200.jpg', 'description': '', 'tags': ['彼女、お借りします', 'かのかり', '桜沢墨', '猫', '猫耳', '制服', '白ニーソ', '拾ってください', '彼女、お借りします5000users入り'], 'userId': '38436050', 'userName': 'ゆきうなぎ＠土曜東ス88a', 'width': 2894, 'height': 4093, 'pageCount': 1, 'isBookmarkable': True, 'bookmarkData': {'id': '24948220443', 'private': False}, 'alt': '#彼女、お借りします ネコ耳墨ちゃん🐈 - ゆきうなぎ＠土曜東ス88a的插画', 'titleCaptionTranslation': {'workTitle': None, 'workCaption': None}, 'createDate': '2020-09-18T19:44:35+09:00', 'updateDate': '2020-09-18T19:44:35+09:00', 'isUnlisted': False, 'isMasked': False, 'aiType': 0, 'profileImageUrl': 'https://i.pximg.net/user-profile/img/2020/02/22/00/11/25/17966339_a51ca7e8a3aca581fc87021488e21479_50.jpg'},
]


def writeraw_to_db_i(illdata):
    # 一个线程对应一个connection
    con = sqlite3.connect(SQLPATH)
    cursor = con.cursor()
    # 新数据
    pid = int(illdata['id'])
    jptag = str(illdata['tags'])
    transtag = '0'
    is_translated = 0
    is_private_b = illdata['bookmarkData']['private']
    if is_private_b == False:
        is_private = 0
    elif is_private_b == True:
        is_private = 1
    
    newdata = (pid, jptag, transtag, is_translated, is_private)
    data_to_modify = [0,0,0,0,0]
    var = {0:['pid',pid], 1:['jptag',jptag], 2:['transtag',transtag], 
           3:['is_translated',is_translated], 4:['is_private',is_private]}
    
    # 先查询已有信息，再判断是否需要修改
    cursor.execute(f'''
                   SELECT * FROM illusts WHERE pid = {pid}
                   ''')
    olddata: list = cursor.fetchall()
    # 比较信息, 将不同之处添加至修改位置列表
    if olddata == []:     # 无信息
        logger.debug('添加新信息')
        cursor.execute(f'''
                       INSERT INTO illusts VALUES ({pid},"{jptag}",{transtag},{is_translated},{is_private})
                       ''')
        con.commit()
    elif olddata[0] == newdata:
        logger.debug('数据重复，无需添加')
        pass
    else:
        for i in range(len(olddata[0])):
            if olddata[0][i] != newdata[i]:
                data_to_modify[i] = 1
        for i in range(len(data_to_modify)):
            if data_to_modify[i] == 1 and i == 1:    #只修改jptag和is_private值
                # logger.debug('更新jptag数据, 修改is_translated值')
                # 下面这里要加个""才行
                cursor.execute(f'''
                                UPDATE illusts SET {var[1][0]} = "{var[1][1]}" where pid = {pid}
                                ''')
                con.commit()
                cursor.execute(f'''
                                UPDATE illusts SET {var[3][0]} = {var[3][1]} where pid = {pid}
                                ''')
                con.commit()
                
            elif data_to_modify[i] == 1 and i == 4:
                #logger.debug('更新is_privated数据')
                cursor.execute(f'''
                                UPDATE illusts SET {var[4][0]} = {var[4][1]} where pid = {pid}
                                ''')
                con.commit()

    con.close()


def writeraw_to_db_m(th_count):
    '''
    将所有tag提交至数据库
    '''
    all_th = []
    logger.info(f'创建线程池，线程数量: {th_count}')
    with ThreadPoolExecutor(max_workers = th_count) as pool:
        while len(illdata) > 0:
            i = illdata.pop(0)
            all_th.append(pool.submit(writeraw_to_db_i, i))
        wait(all_th, return_when=ALL_COMPLETED)
        for th in all_th:
            if th.exception():
                logger.warning(f'运行时出现错误: {th.exception()}')
        logger.info('所有线程运行完成')

writeraw_to_db_m(10)