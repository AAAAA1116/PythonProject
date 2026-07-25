# 报告：架构可行性验证（通不通）

## 1. 这一步干嘛
搭建最小「生产者-消费者模型」，验证「Web 接口 → Redis → 后台 Worker」这条链路到底通不通。
- 生产者：一个 Web 接口，访问它就往 Redis 里塞一个字符串 `"Hello Task"`。
- 消费者：一个后台脚本，一直盯着 Redis，发现有新字符串就取出来打印在屏幕上。
- 验收标准：浏览器访问接口后，后台脚本屏幕瞬间弹出刚发送的那句话。

## 2. 做了什么改动

### Redis 服务
装成 Windows 服务并运行（Redis 3.2.100，端口 6379，开机自启），作为消息中转的「管道」。

### 生产者 producer.py（早期纯文本版）
- 接口：`GET /`
- 关键逻辑：访问即 `LPUSH` 一个固定字符串进 Redis 列表 `tasks`：
```python
r.lpush("tasks", "Hello Task")
```

### 消费者 consumer.py（早期纯文本版）
- 关键逻辑：用 `BRPOP` 阻塞监听 Redis，取出字符串直接打印：
```python
_, item = r.brpop("tasks", timeout=0)
print(item.decode("utf-8"))
```
> 注：此为早期「传话」版本，仅 print 原文；后续已被任务引擎版（见 report_02）替代。

## 3. 验证结果
- 浏览器/终端访问 `http://localhost:8000/` → 返回 `Pushed to Redis: Hello Task`。
- 消费者屏幕输出：
```
[19:44:13] Got task: Hello Task
```
访问接口后后台立刻弹出这句话 → **验收通过 ✅**

## 4. 关键决策 / 踩的坑
- **GitHub 大文件下载超时**：winget/urllib 拉 Redis 二进制失败（WinINet `0x80072ee2`），改用 conda 清华镜像装 `redis=3.2.100`。
- **redis-py 8.0.1 不兼容**：它对老 Redis 3.2 一握手就发 `HELLO` 命令报错。
- **redis==3.5.3 也不可用**：依赖 Python 3.13 已移除的 `distutils`，导入即失败。
- **最终锁定 `redis==4.6.0`**：既不用 distutils，又默认 RESP2 不会发 `HELLO`，兼容老 Redis 3.2 + Python 3.13，链路才打通。
