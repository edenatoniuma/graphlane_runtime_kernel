# Pure Python Example

这个例子展示 Graphlane 当前最小可运行闭环：

1. 用 `KernelBuilder().build()` 构建默认 kernel
2. 发布一个 revision
3. 走一次同步 `invoke`
4. 走一次异步 `submit_async + subscribe_async`

运行方式：

```bash
python open_source_todo/examples/pure_python/run.py
```

