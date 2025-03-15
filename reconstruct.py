import sqlite3
import ast
import binascii
import base64

def init_new_database():
    conn = sqlite3.connect('src/test.db')
    cursor = conn.cursor()
    
    # 作品主表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS illusts (
        pid INTEGER PRIMARY KEY,
        title TEXT,
        created_at TEXT DEFAULT (datetime('now', 'localtime')),
        is_private INTEGER DEFAULT 0
    )''')
    
    # 标签字典表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tags (
        tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
        jptag TEXT UNIQUE,
        transtag TEXT
    )''')
    
    # 作品-标签关联表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS illust_tags (
        pid INTEGER,
        tag_id INTEGER,
        FOREIGN KEY(pid) REFERENCES illusts(pid),
        FOREIGN KEY(tag_id) REFERENCES tags(tag_id),
        UNIQUE(pid, tag_id)
    )''')
    
    # 创建索引
    cursor.execute('CREATE INDEX idx_jptag ON tags(jptag)')
    cursor.execute('CREATE INDEX idx_transtag ON tags(transtag)')
    conn.commit()
    conn.close()



def migrate_data(old_db_path='src/illdata.db', new_db_path='src/test.db'):
    # 连接旧数据库
    old_conn = sqlite3.connect(old_db_path)
    old_cursor = old_conn.cursor()
    
    # 连接新数据库
    new_conn = sqlite3.connect(new_db_path)
    new_cursor = new_conn.cursor()
    
    # 迁移作品数据
    old_cursor.execute('SELECT pid, jptag, transtag FROM illusts')
    for row in old_cursor.fetchall():
        pid, jptags_str, transtags_str = row
        
        # 插入作品主表
        new_cursor.execute('''
            INSERT OR IGNORE INTO illusts (pid) VALUES (?)
        ''', (pid,))
        
        # 解析旧标签数据
        jptags = ast.literal_eval(jptags_str) if jptags_str else []
        transtags = ast.literal_eval(transtags_str) if transtags_str else []
        
        # 插入标签数据
        for jp, tr in zip(jptags, transtags):
            # 插入标签字典
            new_cursor.execute('''
                INSERT OR IGNORE INTO tags (jptag, transtag)
                VALUES (?, ?)
            ''', (jp.strip(), tr.strip()))
            
            # 获取tag_id
            new_cursor.execute('''
                SELECT tag_id FROM tags WHERE jptag = ?
            ''', (jp.strip(),))
            tag_id = new_cursor.fetchone()[0]
            
            # 插入关联关系
            new_cursor.execute('''
                INSERT OR IGNORE INTO illust_tags (pid, tag_id)
                VALUES (?, ?)
            ''', (pid, tag_id))
    
    new_conn.commit()
    new_conn.close()
    old_conn.close()


def decode_translations(db_path='src/test.db'):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # 获取所有需要解码的记录
        cursor.execute('SELECT tag_id, transtag FROM tags')
        records = cursor.fetchall()
        
        # 逐条解码更新
        for tag_id, encoded_tag in records:
            if not encoded_tag:
                continue
            
            try:
                # Base64解码
                decoded = base64.b64decode(encoded_tag).decode('utf-8')
                
                # 更新数据库
                cursor.execute('''
                    UPDATE tags 
                    SET transtag = ?
                    WHERE tag_id = ?
                ''', (decoded, tag_id))
                
            except (UnicodeDecodeError, binascii.Error) as e:
                print(f"解码失败 tag_id:{tag_id} error:{str(e)}")
                # 保留原始值或置空
                # cursor.execute('UPDATE tags SET transtag = ? WHERE tag_id = ?', ("", tag_id))
        
        conn.commit()
