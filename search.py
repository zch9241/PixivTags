import sqlite3
import re
from functools import lru_cache
import logging


class PixivSearcher:
    def __init__(self, logger: logging.Logger, db_path: str):
        """初始化

        Args:
            logger (logging.Logger): logger
            db_path (str): 数据库位置
        """
        self.conn = sqlite3.connect(db_path)
        self.logger = logger
        # 预编译正则表达式
        self.token_pattern = re.compile(
            r'''(
                (\(|\)) |                  # 匹配括号
                \b(?:OR|AND|NOT)\b |       # 匹配逻辑运算符（不捕获）
                -\S+ |                     # 匹配否定操作符
                "[^"]+" |                  # 匹配带空格的标签
                [^\s()]+                   # 匹配普通标签（含连字符）
            )''', 
            flags=re.IGNORECASE | re.VERBOSE
        )
        
    def _parse_query(self, query: str):
        """
        ## 将自然语言查询转换为SQL WHERE条件
        
        ### 语法：
        - NOT: -前缀
        - AND: 空格分隔 或 直接输入AND
        - OR: 直接输入OR
        ### 特性：
        - 支持括号
        - 支持带连字符的标签（如 R-18）
        - 支持引号包裹的标签
        - 精准的否定操作符识别
        """
        tokens = self.token_pattern.findall(query)
        tokens = [t[0].strip('"') for t in tokens]  # 去除引号并展平结果
        
        sql_where = []
        params = []
        stack = []          # 保存外层条件
        current_clause = [] # 当前层条件
        
        # 使用栈结构处理括号嵌套
        for token in tokens:
            token: str
            token_lower = token.lower()
            
            # 处理逻辑运算符和括号
            if token == '(':
                stack.append(current_clause)
                current_clause = []
            elif token == ')':
                if not stack:
                    raise ValueError("括号未闭合: Unbalanced parentheses")
                closed_clause = current_clause
                current_clause = stack.pop()
                current_clause.append(f"({' '.join(closed_clause)})")
            elif token_lower in ('and', 'or', 'not'):
                current_clause.append(token.upper())
            
            # 处理否定标签（以 - 开头）
            elif token.startswith('-'):
                raw_tag = token[1:].lower()
                self._handle_tag_condition(raw_tag, current_clause, params, negated=True)
            
            # 处理普通标签
            else:
                self._handle_tag_condition(token_lower, current_clause, params)
        
        # 处理未闭合的括号
        if stack:
            raise ValueError("括号未闭合: Unbalanced parentheses")
        
        return ' '.join(current_clause), params if current_clause else (None, [])

    def _handle_tag_condition(self, tag: str, clause: list, params: list, negated: bool = False):
        """统一处理标签条件（正向/反向）"""
        tag_ids = self._get_tag_ids(tag)
        if not tag_ids:
            return
        
        placeholders = ','.join(['?'] * len(tag_ids))
        operator = "NOT EXISTS" if negated else "EXISTS"
        clause.append(
            f"{operator} (SELECT 1 FROM illust_tags " 
            f"WHERE pid = i.pid AND tag_id IN ({placeholders}))"
        )
        params.extend(tag_ids)

    @lru_cache(maxsize=100)
    def _get_tag_ids(self, tag: str) -> tuple[int]:
        """获取标签对应的所有tag_id（包含日语和翻译标签）"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT tag_id FROM tags 
            WHERE LOWER(jptag) = LOWER(?) OR LOWER(transtag) = LOWER(?)
        ''', (tag, tag))
        return tuple(row[0] for row in cursor.fetchall())

    def search(self, query: str) -> list[int]:
        """执行搜索的主入口"""
        try:
            where_clause, params = self._parse_query(query)
            if not where_clause:
                return []
            
            sql = f'''
                SELECT i.pid 
                FROM illusts i
                WHERE {where_clause}
                GROUP BY i.pid
                ORDER BY i.created_at DESC
            '''
            
            cursor = self.conn.cursor()
            cursor.execute(sql, params)
            return [row[0] for row in cursor.fetchall()]
        
        except ValueError as e:
            self.logger.error(f"查询语法错误: {str(e)}")
            return []
        
        except sqlite3.Error as e:
            self.logger.error(f"数据库错误: {str(e)}")
            return []

    def close(self):
        """关闭数据库连接"""
        self.conn.close()





# 测试用例
if __name__ == '__main__':
    # 日志初始化
    logger = logging.getLogger('logger')
    handler = logging.StreamHandler()
    logger.setLevel(logging.DEBUG)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "[%(asctime)s %(name)s %(thread)d %(funcName)s] %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    def run_test_case(searcher: PixivSearcher, query: str, expected: str):
        try:
            print(f"测试查询: {query}")
            where, _ = searcher._parse_query(query)
            print(f"生成条件: {where}")
            print("结果:", searcher.search(query))
            print("-" * 50)
        except Exception as e:
            print(f"测试失败: {str(e)}")

    searcher = PixivSearcher(logger, 'src/illdata.db')
    
    # 有效测试用例
    run_test_case(searcher, "R-18", "EXISTS (...R-18...)")
    run_test_case(searcher, "-A-1", "NOT EXISTS (...A-1...)")
    run_test_case(searcher, '"science-fiction"', "EXISTS (...science-fiction...)")
    run_test_case(searcher, "(A-1 OR B-2) AND C-3", "组合逻辑")
    
    # 错误用例测试
    run_test_case(searcher, "A- AND B", "不完整标签")
    run_test_case(searcher, "(A OR B", "未闭合括号")
    
    searcher.close()