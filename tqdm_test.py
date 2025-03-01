from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import time

# 示例任务函数
def task(n):
    time.sleep(0.1)  # 模拟耗时操作
    result = n * n
    tqdm.write(f"Task {n} completed with result: {result}")
    return result

# 创建一个任务列表
tasks = list(range(100))

# 使用线程池和 tqdm 显示进度
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(task, n) for n in tasks]
    
    # 使用 tqdm 跟踪进度
    for future in tqdm(as_completed(futures), total=len(futures)):
        result = future.result()
        # 可以在这里处理结果
        # print(result)