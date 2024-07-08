import logging  
import multiprocessing as mp  
import os  

def log_receiver_proc(conn):  
    while True:  
        try:  
            log_entry = conn.recv()  
            if log_entry is None:  # 停止日志接收进程的哨兵值
                break  
            # 在这里处理接收到的日志条目，例如打印、存储或传递给其他程序  
            print(log_entry)  
        except EOFError:  
            break  
  
def setup_logging_to_pipe(conn):  
    class LoggingPipeHandler(logging.Handler):  
        def emit(self, record):  
            log_entry = self.format(record)  
            conn.send(log_entry)  
  
    pipe_handler = LoggingPipeHandler()  
    pipe_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))  
  
    logger = logging.getLogger()  
    logger.addHandler(pipe_handler)  
    logger.setLevel(logging.INFO)  
  
if __name__ == '__main__':  
    # 创建管道  
    parent_conn, child_conn = mp.Pipe()  
  
    # 启动日志接收进程  
    log_receiver = mp.Process(target=log_receiver_proc, args=(child_conn,))  
    log_receiver.start()  
  
    # 设置日志记录到管道  
    setup_logging_to_pipe(parent_conn)  
  
    # 记录一些日志  
    logging.info('This is an info message.')  
    logging.warning('This is a warning message.')  
  
    # 发送一个哨兵值来停止日志接收进程  
    parent_conn.send(None)  
  
    # 等待日志接收进程结束  
    log_receiver.join()