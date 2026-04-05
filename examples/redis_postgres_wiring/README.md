# Redis + Postgres Wiring Example

这个例子展示 Graphlane 当前如何把真实 adapter 装到 `KernelBuilder`：

- `PostgresRevisionStore`
- `RedisEventBus`
- `RedisLockManager`
- `RedisLimiter`

当前说明：

- `PostgresOutboxStore` 已经有 adapter 骨架
- 但还没有正式接回 `KernelBuilder` 的 publish side effect 主链
- 所以这个例子重点是 wiring，不是完整生产配置

运行前需要准备：

- `GRAPHLANE_DATABASE_URL`
- `GRAPHLANE_REDIS_URL`

运行方式：

```bash
python open_source_todo/examples/redis_postgres_wiring/run.py
```

