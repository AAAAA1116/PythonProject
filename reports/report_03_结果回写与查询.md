# 报告：结果回写与查询验证

## 1. 这一步干嘛
之前 Worker 算完结果只是 `print` 在它自己的屏幕上，发任务的 API 端（和调用 API 的用户）根本拿不到结果——任务变成「发了就不管」的盲盒。

这一步让系统变成**可查询的异步任务**：Worker 算完把结果存回 Redis，API 端凭 `task_id` 随时来取。

- 验收标准：访问 `/?a=1&b=2&func=add` 拿到 `task_id` → 等几秒 → 访问 `/result?task_id=刚才的ID`，浏览器显示 `{"status": "success", "data": 3}`。

## 2. 做了什么改动

### 消费者 consumer.py（结果回写）
算出 `result` 后，不再只打印，而是按 `task_id` 把结果写回 Redis（Key-Value）：
```python
# Key = result:{task_id}，Value = JSON
r.set(f"result:{task_id}", json.dumps(
    {"status": status, "data": result}, ensure_ascii=False))
```
- `status` 区分成功/失败：`"success"` 或 `"error"`。
- 即使执行抛异常，也会回写 `{"status": "error", "data": str(e)}`，让 API 端能查到失败原因，而不是查不到。
- 屏幕打印保留（`-> stored`），方便肉眼看 Worker 仍在干活。

### 生产者 producer.py（结果查询接口）
`do_GET` 增加路径判断：
- **`/result?task_id=xxx`**：去 Redis 查 `result:{task_id}`。
  - 查到 → 返回 JSON `{"status": "success", "data": 3}`，HTTP 200。
  - 查不到 → 返回 `{"status": "pending", "data": null}`，HTTP 404（区分「还没跑完」和「跑失败」）。
- **`/`**（提交接口）：行为不变，但返回改成 JSON，浏览器里直接能看到 `task_id`。

## 3. 验证结果
```text
SUBMIT task_id = 31d3a5a88418443b91ade7eddc3ec48a
RESULT = {'status': 'success', 'data': 3}
```
提交 `1+2` → 拿到 `task_id` → 查询接口返回 `{"status": "success", "data": 3}` → **验收通过 ✅**

## 4. 关键决策 / 踩的坑
- **为什么 Key 用 `result:{task_id}`**：`task_id` 是之前设计的「快递单号」，结果按单号存，查询是 O(1)，且一个任务对应一份结果，互不覆盖。
- **`pending` vs `error`**：查不到时不直接报错，而是返回 `pending`，让调用方能区分「任务还在队列里没跑」和「跑挂了」，这是真实异步系统的标配语义。
- **这一步的意义**：系统时序从「提交即忘」升级为「提交→异步执行→凭 ID 取结果」，是构建完整任务系统（以后可加状态追踪、结果留存、重试）的基础骨架。
- （环境沿用：`redis==4.6.0` 客户端 + Redis 3.2 服务，本次无新增环境问题。）
