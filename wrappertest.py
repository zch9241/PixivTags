import sys
import traceback
def connection_handler(vars: list):
    """对远程服务器返回非预期值的处理

    Args:
        vars (list): 可能出现解析错误的变量列表
    """
    def wrapper(func):
        def inner_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if e.__class__ == KeyError:
                    # 获取当前的traceback对象
                    tb = sys.exc_info()[2]
                    # 获取堆栈跟踪条目
                    tblist = traceback.extract_tb(tb)
                    # 获取引发错误的起始原因
                    initial_reason = tblist[-1].line
                    print(f'解析出现错误，服务器可能未返回正确信息 {initial_reason}')
                    
                    # debug使用，以获取出现错误的具体原因
                    # tb_list = traceback.format_tb(tb)
                    # print("".join(tb_list))
                    
                    for var in vars:
                        if str(var) in initial_reason:
                            print(f'相关变量: {var}')

                else:
                    print(f'未知错误 {sys.exc_info}')
                    tb = sys.exc_info()[2]
                    tb_list = traceback.format_tb(tb)
                    print("".join(tb_list))
        return inner_wrapper
    return wrapper



@connection_handler(['b'])
def foo():
    a = {'1':0}
    s = '2'
    b = a[s]
foo()
print(1 is 1)