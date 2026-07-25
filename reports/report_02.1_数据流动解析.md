# 报告：数据流动解析（consumer.py 代码级长镜头）

> 配套文档：`report_02_任务引擎验证.md`
> 本文把 Worker 从 Redis 取任务 → 拆包 → 找函数 → 算出结果的全过程，按 `consumer.py` 源码逐行拉成一条「长镜头」，让你看清数据每一步的形态变化。

---

## 一、起点：Redis 里躺着一条任务

生产者往 Redis 塞任务（对应 `producer.py` 第 34 行 `r.lpush(QUEUE, json.dumps(packet))`，队列名 `tasks`）：

```text
LPUSH tasks '{"task_id":"9","func_name":"add","args":[3,5]}'
```

此时 Redis 的 `tasks` 里存的是**字节串**：

```text
b'{"task_id":"9","func_name":"add","args":[3,5]}'
```

---

## 二、Worker 阻塞在门口等活

```31:31:c:\Users\Administrator\Desktop\PythonProject\consumer.py
        _, item = r.brpop(QUEUE, timeout=0)
```

- Worker 卡在这一行。
- Redis 队列空 → 不动（阻塞）。
- 一旦上面那条任务进来：`brpop` 立刻返回，把字节串交给 `item`。
- 此时数据：`item == b'{"task_id":"9","func_name":"add","args":[3,5]}'`

---

## 三、字节串 → 字符串 → Python 对象

```33:33:c:\Users\Administrator\Desktop\PythonProject\consumer.py
        packet = json.loads(item.decode("utf-8"))
```

流动路径：

```text
bytes  (b'{...}')
  ↓  .decode("utf-8")
str    ('{...}')
  ↓  json.loads
dict   ({...})
```

变成：

```python
packet = {
    "task_id": "9",
    "func_name": "add",
    "args": [3, 5]
}
```

---

## 四、从 dict 里拆出「指令」

```34:36:c:\Users\Administrator\Desktop\PythonProject\consumer.py
        task_id = packet["task_id"]
        func_name = packet["func_name"]   # "add"
        args = packet["args"]             # [3, 5]
```

此时数据形态：

```text
task_id   → str
func_name → str
args      → list
```

---

## 五、函数表里「按名找人」

```38:38:c:\Users\Administrator\Desktop\PythonProject\consumer.py
        func = FUNCS.get(func_name)
```

`FUNCS` 是函数注册表（`consumer.py` 第 19–23 行）：

```python
FUNCS = {
    "add": add,   # add(a, b) = a + b
    "sub": sub,
    "mul": mul,
}
```

流动：

```text
"add"
  ↓  字典查找 FUNCS.get("add")
<function add>   ← 函数对象本身，还没调用
```

> 关键：Redis 只能存字符串 `"add"`，存不了函数。`FUNCS.get` 就是把它**还原成可调用的函数对象**。

---

## 六、最关键的一步：解包 + 调用

```42:42:c:\Users\Administrator\Desktop\PythonProject\consumer.py
            result = func(*args)   # 即 add(3, 5)
```

### 解包阶段（参数准备）
```python
args == [3, 5]
*args  →  3, 5        # * 把列表拆成位置参数
```

### 调用阶段（函数执行）
```python
add(3, 5)
#   3 → 参数 a
#   5 → 参数 b
#   ↓ 执行 a + b
#   返回 8
```

于是：
```python
result == 8
```

（随后第 45 行带时间戳打印：`[..] task_id=9 | add(3, 5) = 8`）

---

## 七、整条「数据流动链」（一口气看完）

```text
Redis bytes          b'{"task_id":"9",...}'
  ↓  UTF-8 解码 (.decode)
str                  '{"task_id":"9",...}'
  ↓  JSON 解析 (json.loads)
dict                 {task_id, func_name, args}
  ↓  取出字段
func_name(str) + args(list)
  ↓  FUNCS.get(func_name)
函数对象 <function add>
  ↓  * 解包 + 调用  func(*args)
函数执行栈            add(3, 5) → 3+5
  ↓  返回
result = 8
```

---

## 八、人话版「长镜头」

> Redis 里躺着一封任务信，Worker 一直守在门口。
> 信一到，Worker 拆信封，把 JSON 转成 Python 看得懂的 dict。
> 从 dict 里读出「叫什么函数」「参数是什么」。
> 再去自己的函数表里按名字翻到人，把参数一个个拆开塞进函数。
> 函数开始算，算完吐出一个结果。
> 这一整趟，就是一次任务的完整流动。

---

## 小结
这条链路的本质，就是**把「字符串指令」逐步翻译成「可执行的 Python 调用」**：

`字节串 → 字符串 → dict → 函数对象 → 参数解包 → 返回值`

每一步都是一次「形态升级」，最终让 Redis 里冰冷的字符串，变成了 Worker 真正跑起来的计算。
