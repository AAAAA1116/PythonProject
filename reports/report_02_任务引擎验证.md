# 报告：任务引擎验证（下指令，而非传话）

## 1. 这一步干嘛
把系统从「消息队列」升级为「任务引擎」：
- 之前：Web 发字符串 `"Hello"`，Worker 只是 `print(data)`（复读机）。
- 现在：Web 发「执行加法，参数是 5 和 8」，Worker 真的算出 `13` 并打印。

为什么要做：验证「业务逻辑抽象」——Redis 只能存字符串，无法存函数对象，所以要学会用「函数名 + 参数 + 任务ID」来表示一个任务，这是分布式任务系统的核心设计思想。

## 2. 做了什么改动

### 任务指令包（标准 JSON 格式）
不再发普通文本，而是发结构化指令：
```json
{
  "task_id": "e403ad39...",
  "func_name": "add",
  "args": [5, 8]
}
```
`task_id` 像快递单号，以后查状态、取结果全靠它。

### 生产者 producer.py（接收参数 → 打包 → 入队）
- 接口：`GET /?a=5&b=8&func=add`（默认 `func=add`）。
- 关键逻辑：把请求参数打包成上面的 JSON，`LPUSH` 进 Redis 列表 `tasks`。
```python
packet = {"task_id": uuid.uuid4().hex, "func_name": func_name, "args": args}
r.lpush(QUEUE, json.dumps(packet, ensure_ascii=False))
```

### 消费者 consumer.py（取指令 → 找函数 → 执行 → 打印）
- 用**函数注册表** `FUNCS` 把「函数名」映射到「真正的 Python 函数」：
```python
def add(a, b): return a + b
def sub(a, b): return a - b
def mul(a, b): return a * b
FUNCS = {"add": add, "sub": sub, "mul": mul}
```
- 关键逻辑：`BRPOP` 阻塞取出 → `json.loads` 解析 → `FUNCS.get(func_name)` 找到函数 → `func(*args)` 执行 → 带时间戳和 `task_id` 打印结果。
```python
func = FUNCS.get(func_name)
result = func(*args) if func else f"ERROR: unknown func_name '{func_name}'"
print(f"[{ts}] task_id={task_id} | {func_name}{tuple(args)} = {result}")
```

## 3. 验证结果
浏览器/终端访问 `http://localhost:8000/?a=5&b=8`，Worker 屏幕输出：
```
[14:17:47] task_id=e403ad39... | add(5, 8) = 13
```
输入 5 和 8，Worker 不仅收到请求，还真正执行了加法并打印出 `13` → **验收通过 ✅**

（同样可测 `?a=10&b=3&func=sub` → 打印 `sub(10, 3) = 7`。）

## 4. 关键决策 / 踩的坑
- **函数怎么存**：Redis 只认字符串，所以存「函数名 + 参数」而不是函数对象，由 Worker 端用注册表把它还原成真正可调用的函数。
- **任务身份**：指令包里带 `task_id`，使系统从「盲盒」变成可追溯——后续可凭 ID 查状态、取结果。
- **调度能力**：Worker 从复读机变成执行器，能理解指令并干活，系统完成「消息队列 → 任务引擎」的进化。
- （环境约束沿用上一阶段：Redis 3.2 服务 + `redis==4.6.0` 客户端，已就绪，本次无新增环境问题。）
