import datetime
import json

import redis

# 函数注册表：func_name -> 真正的 Python 函数
def add(a, b):
    return a + b


def sub(a, b):
    return a - b


def mul(a, b):
    return a * b


FUNCS = {
    "add": add,
    "sub": sub,
    "mul": mul,
}

r = redis.Redis(host="localhost", port=6379, db=0)
QUEUE = "tasks"

print(f'Worker started, watching Redis list "{QUEUE}" ...', flush=True)
while True:
    # 阻塞取出任务指令包（JSON 字符串）
    _, item = r.brpop(QUEUE, timeout=0)
    try:
        packet = json.loads(item.decode("utf-8"))
        task_id = packet["task_id"]
        func_name = packet["func_name"]
        args = packet["args"]

        func = FUNCS.get(func_name)
        if func is None:
            result = f"ERROR: unknown func_name '{func_name}'"
        else:
            result = func(*args)  # 按 func_name 找到函数，传入 args 执行

        ts = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] task_id={task_id} | {func_name}{tuple(args)} = {result}", flush=True)
    except Exception as e:
        print(f"[ERROR] failed to process packet: {e} | raw={item}", flush=True)
