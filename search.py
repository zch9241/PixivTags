# PixivTags
# 
# Copyright (c) 2024-2025 zch9241. All rights reserved.
# 
# 本软件受以下使用条款约束：
# 1. 仅限个人及教育用途，禁止商业使用
# 2. 禁止未经授权的营利性传播
# 3. 完整条款详见项目根目录LICENSE文件
# 
# 如有疑问请联系：[zch2426936965@gmail.com]
# 

# standard-libs
import re
import sqlite3

# site-packages
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML

class QueryParser:
    """查询解析器，将自然语言查询转换为抽象语法树（AST）"""
    def __init__(self):
        self.tokens = []
        self.pos = 0
    
    def tokenize(self, query):
        # 匹配标签、引号包围的词、逻辑运算符和括号
        pattern = r'"[^"]*"|\bAND\b|\bOR\b|\bNOT\b|\(|\)|[\w\-/]+'
        self.tokens = re.findall(pattern, query, re.IGNORECASE)
        self.pos = 0
        return self.tokens
    
    def parse(self, query):
        """解析入口

        Args:
            query (str): 要解析的字符串
        """
        self.tokenize(query)
        return self.parse_expression()
    
    def parse_expression(self):
        term = self.parse_term()
        
        while self.pos < len(self.tokens) and self.tokens[self.pos].upper() == "OR":
            self.pos += 1
            right = self.parse_term()
            term = {"operator": "OR", "left": term, "right": right}
        
        return term
    
    def parse_term(self):
        factor = self.parse_factor()
        
        while self.pos < len(self.tokens) and self.tokens[self.pos].upper() == "AND":
            self.pos += 1
            right = self.parse_factor()
            factor = {"operator": "AND", "left": factor, "right": right}
        
        return factor
    
    def parse_factor(self):
        if self.pos >= len(self.tokens):
            raise ValueError("Unexpected end of expression")
            
        token = self.tokens[self.pos]
        
        if token.upper() == "NOT":
            self.pos += 1
            operand = self.parse_factor()
            return {"operator": "NOT", "operand": operand}
        
        elif token == "(":  # 处理括号内的内容
            self.pos += 1
            expr = self.parse_expression()
            
            if self.pos < len(self.tokens) and self.tokens[self.pos] == ")":
                self.pos += 1
                return expr
            else:
                raise ValueError("Missing closing parenthesis")
        
        else:   # token为tag
            self.pos += 1
            # 处理带引号的tag
            if token.startswith('"') and token.endswith('"'):
                token = token[1:-1]
            return {"tag": token}

class TagCompleter(Completer):
    """tag补全"""
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
    
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor  # 获取光标前的输入文本
        
        # 寻找最后一个标签词
        tokens = []
        in_quotes = False   # 跟踪 in_quotes 状态，确保带空格的标签（如 "white hair"）被视为单个 token。
        current = ""
        for char in text:
            if char == '"':
                in_quotes = not in_quotes
                current += char
                if not in_quotes:  # 引号结束
                    tokens.append(current)
                    current = ""
            elif char.isspace() and not in_quotes:
                if current:
                    tokens.append(current)
                    current = ""
                tokens.append(char) # 保留空格作为分隔符
            else:
                current += char
        
        if current:
            tokens.append(current)
        
        # 查找最后一个标签(忽略逻辑运算符和括号)
        last_token = ""
        for i in range(len(tokens)-1, -1, -1):
            if tokens[i].strip() and not tokens[i].upper() in ["AND", "OR", "NOT", "(", ")"]:
                last_token = tokens[i]
                break
        
        if not last_token:
            return
        
        # 处理引号
        search_term = last_token
        quoted = False
        if search_term.startswith('"') and not search_term.endswith('"'):
            search_term = search_term[1:]
            quoted = True
        
        # 查询匹配标签
        self.cursor.execute('''
            SELECT t.jptag, t.transtag, COUNT(it.pid) as count 
            FROM tags t
            LEFT JOIN illust_tags it ON t.tag_id = it.tag_id
            WHERE t.jptag LIKE ? OR t.transtag LIKE ?
            GROUP BY t.tag_id
            ORDER BY count DESC
            LIMIT 15
        ''', (f'{search_term}%', f'{search_term}%'))
        
        # 生成补全建议
        for row in self.cursor.fetchall():
            jptag = row['jptag']
            transtag = row['transtag']
            count = row['count']
            
            # 决定是否需要引号
            completion = jptag
            if ' ' in jptag or quoted:
                completion = f'"{jptag}"'
            
            # display_text = f"{jptag} ({transtag}) - {count}项"
            yield Completion(
                completion, 
                start_position=-len(search_term) - (1 if quoted else 0),
                display=HTML(f'<b>{jptag}</b> <i>({transtag})</i> - <ansired>{count}项</ansired>')
            )

class PixivSearchEngine:
    """搜索核心"""
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.parser = QueryParser()
    
    def build_sql_from_ast(self, ast):
        """将抽象语法树转换为SQL查询"""
        if "operator" in ast:
            if ast["operator"] == "AND":
                left_sql, left_params = self.build_sql_from_ast(ast["left"])
                right_sql, right_params = self.build_sql_from_ast(ast["right"])
                # 使用子查询替代INTERSECT
                return f"""
                    SELECT DISTINCT pid FROM ({left_sql}) 
                    WHERE pid IN (SELECT pid FROM ({right_sql}))
                """, left_params + right_params
            
            elif ast["operator"] == "OR":
                left_sql, left_params = self.build_sql_from_ast(ast["left"])
                right_sql, right_params = self.build_sql_from_ast(ast["right"])
                # 使用UNION更安全
                return f"""
                    SELECT DISTINCT pid FROM ({left_sql})
                    UNION 
                    SELECT DISTINCT pid FROM ({right_sql})
                """, left_params + right_params
            
            elif ast["operator"] == "NOT":
                operand_sql, operand_params = self.build_sql_from_ast(ast["operand"])
                return f"""
                    SELECT DISTINCT pid FROM illusts
                    WHERE pid NOT IN (SELECT pid FROM ({operand_sql}))
                """, operand_params
        
        elif "tag" in ast:
            tag = ast["tag"]
            # 对于精确匹配
            if tag.startswith("="):
                tag = tag[1:]  # 移除等号
                return """
                    SELECT DISTINCT it.pid
                    FROM illust_tags it
                    JOIN tags t ON it.tag_id = t.tag_id
                    WHERE t.jptag = ? OR t.transtag = ?
                """, [tag, tag]
            # 对于默认的部分匹配
            else:
                return """
                    SELECT DISTINCT it.pid
                    FROM illust_tags it
                    JOIN tags t ON it.tag_id = t.tag_id
                    WHERE t.jptag LIKE ? OR t.transtag LIKE ?
                """, [f"%{tag}%", f"%{tag}%"]

        raise ValueError(f"无效的语法树节点: {ast}")
    
    def search(self, query):
        """执行搜索查询并返回结果"""
        try:
            ast = self.parser.parse(query)
            sql, params = self.build_sql_from_ast(ast)
            
            full_sql = f"""
                SELECT i.pid, i.title, i.author_id
                FROM ({sql}) as result
                JOIN illusts i ON result.pid = i.pid
                ORDER BY i.created_at DESC
            """
            
            self.cursor.execute(full_sql, params)
            return self.cursor.fetchall()
        except Exception as e:
            return f"搜索错误: {str(e)}"

class PixivSearchCLI:
    """交互界面"""
    def __init__(self, db_path):
        self.engine = PixivSearchEngine(db_path)
        self.completer = TagCompleter(db_path)
        self.session = PromptSession(completer=self.completer)
    
    def display_result(self, results):
        """格式化并显示搜索结果"""
        if isinstance(results, str):  # 错误消息
            print(results)
            return
            
        print(f"\n共找到 {len(results)} 个结果:")
        for i, row in enumerate(results[:30], 1):
            print(f"{i}. [PID: {row['pid']}] {row['title']} (作者ID: {row['author_id']})")
        
        if len(results) > 30:
            print(f"... 还有 {len(results) - 30} 个结果未显示")
    
    def show_help(self):
        """显示帮助信息"""
        print("\n===== Pixiv 标签搜索工具 =====")
        print("支持的搜索语法:")
        print("  - 普通标签: 女の子")
        print("  - 带空格的标签使用引号: \"white hair\"")
        print("  - 逻辑运算: AND OR NOT")
        print("  - 使用括号分组: (tag1 OR tag2) AND tag3")
        print("  - 输入时按Tab键自动完成标签")
        print("\n命令:")
        print("  :help  显示帮助")
        print("  :exit  退出程序")
        print("==============================\n")
    
    def run(self):
        self.show_help()
        
        while True:
            try:
                query = self.session.prompt("\nPixiv Search> ")
                
                if not query.strip():
                    continue
                    
                if query.strip() == ":exit":
                    print("退出搜索")
                    break
                    
                if query.strip() == ":help":
                    self.show_help()
                    continue
                
                results = self.engine.search(query)
                self.display_result(results)
                
            except KeyboardInterrupt:
                continue
            except EOFError:
                break
            except Exception as e:
                print(f"错误: {str(e)}")

def main(db_path: str):
    """搜索入口函数

    Args:
        db_path (str): 数据库位置
    """
    import os

    if not os.path.exists(db_path):
        print(f"错误: 找不到数据库文件 '{db_path}'")
        return
    
    print("正在初始化搜索引擎...")
    cli = PixivSearchCLI(db_path)
    cli.run()

if __name__ == "__main__":
    # main("src/illdata.db")
    
    # QueryParser测试
    print('-' * 50)
    parser = QueryParser()
    print('QueryParser测试')
    query = '"a b" AND (NOT c OR d) '
    print(f'query: {query}')
    ret = parser.parse(query)
    print(ret)
    print('-' * 50)
