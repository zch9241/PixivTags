import sqlite3
import readline
# 这个稍微有点问题

class TagCompleter:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        readline.set_completer(self.complete)
        readline.parse_and_bind("tab: complete")
    
    def complete(self, text: str, state: int) -> str:
        """自动补全函数"""
        if state == 0:
            self.matches = self._get_suggestions(text)
        return self.matches[state] if state < len(self.matches) else None

    def _get_suggestions(self, partial: str) -> list[str]:
        """获取标签建议（包含使用次数）"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT t.jptag, t.transtag, COUNT(it.pid) as cnt 
            FROM tags t
            LEFT JOIN illust_tags it ON t.tag_id = it.tag_id
            WHERE LOWER(t.jptag) LIKE LOWER(?) OR LOWER(t.transtag) LIKE LOWER(?)
            GROUP BY t.tag_id
            ORDER BY cnt DESC
            LIMIT 5
        ''', (f'%{partial}%', f'%{partial}%'))
        
        suggestions = []
        for jp, trans, cnt in cursor.fetchall():
            display = []
            if jp: display.append(jp)
            if trans: display.append(trans)
            suggestions.append(f'{" / ".join(display)} ({cnt} uses)')
        return suggestions

if __name__ == '__main__':
    # 使用示例
    completer = TagCompleter('src/illdata.db')
    
    try:
        while True:
            query = input("请输入搜索条件（TAB补全）: ")
            print(f"执行搜索: {query}")
    except KeyboardInterrupt:
        pass