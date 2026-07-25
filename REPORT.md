# 生产者-消费者（任务引擎）验证报告

> 环境：Windows / Python 3.13.5（`.venv`）/ Redis 3.2.100（conda 镜像，Windows 服务，端口 6379，已运行、开机自启）/ redis-py 4.6.0
> 结论：**两阶段均通过 ✅**

---

## 阶段一：架构可行性验证（验证“通不通”）
链路：`浏览器 → producer(LPUSH) → Redis(tasks) → consumer(BRPOP) → 屏幕`
- 生产者发 `Hello Task`，消费者打印 `Got task: Hello Task` → 全链路打通。
- 关键坑：① GitHub 大文件下载超时 → 改用 conda 清华镜像装 Redis；② 老 Redis 3.2 不支持 `HELLO`、Python 3.13 无 `distutils` → 客户端固定 `redis==4.6.0`。

## 阶段二：任务引擎验证（验证“听不听指令”）
把“传话”升级为“下指令”：不再发纯文本，而是发**任务指令包**，Worker 按指令执行真正的 Python 函数。

### 1. 任务指令包格式（JSON）
```json
{ "task_id": "abc-123", "func_name": "add", "args": [10, 20] }
```
- `task_id`：任务身份（快递单号），后续查状态/取结果都靠它。
- `func_name`：要执行的函数名。
- `args`：函数参数列表。

### 2. 生产者改造
`GET /?a=5&b=8`（默认 `func=add`，支持 `?func=sub&...`）→ 打包成上面 JSON → `LPUSH` 进 Redis。

### 3. 消费者（Worker）改造
`BRPOP` 取出 → `json.loads` 解析 → 用 `func_name` 在**函数注册表**里查找：
```python
FUNCS = {"add": add, "sub": sub, "mul": mul}
```
→ `func(*args)` 执行 → 打印 `add(5, 8) = 13`。

### 4. 验证结果（实测）
```text
# 浏览器访问 http://localhost:8000/?a=5&b=8
Pushed task: {"task_id":"e403ad39...","func_name":"add","args":[5,8]}

# Worker 屏幕
Worker started, watching Redis list "tasks" ...
[14:17:47] task_id=e403ad39... | add(5, 8) = 13
```
发 5 和 8 → Worker 真的算出并打印 **13**，**满足验收标准**。

### 5. 这一步解决了什么
- **函数怎么存**：Redis 只能存字符串，用「函数名 + 参数」代表任务（分布式任务系统核心设计）。
- **任务身份**：`task_id` 入包，系统不再是盲盒。
- **调度能力**：Worker 从复读机变成执行器，系统从“消息队列”进化为“任务引擎”。

---

## 怎么跑（交付）
```cmd
# 终端1 生产者
.venv\Scripts\python.exe producer.py
# 终端2 消费者（看这个屏幕）
.venv\Scripts\python.exe consumer.py
# 浏览器
http://localhost:8000/?a=5&b=8            → 打印 add(5, 8) = 13
http://localhost:8000/?a=10&b=3&func=sub  → 打印 sub(10, 3) = 7
```
Redis 已作为服务运行，无需手动启动。
