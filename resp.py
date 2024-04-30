urls = []
r = 'show'
total_show = 97
limit =100
UID = '0000000'
if r == 'show':
    total = total_show
    k = total//limit            # 整步步数
    l = total - k*limit + 1     # 剩余部分对应的limit
    s = 0                       # 计数器
    while k > s:
        urls.append(f'https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset={s*limit}&limit={limit}&rest=show&lang=zh')
        s+=1
    urls.append(f'https://www.pixiv.net/ajax/user/{UID}/illusts/bookmarks?tag=&offset={s*limit}&limit={l}&rest=show&lang=zh')
print(urls)    