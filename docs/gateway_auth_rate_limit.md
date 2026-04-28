# Drogon Gateway 鉴权与限流

本文档说明 C++ Drogon Gateway 的 API Key 鉴权和 Redis 限流实现。

## 保护范围

- `/health` 不做鉴权和限流，保留给负载均衡、运维探活使用。
- `/v1/*` 业务接口会先执行 API Key 鉴权，再执行限流。
- `OPTIONS` 预检请求不拦截，CORS 允许 `Authorization`、`X-API-Key` 和 `X-User-Id`。

## API Key 鉴权

客户端可以使用以下任一方式传递 API Key：

```bash
X-API-Key: your-secret-key
Authorization: Bearer your-secret-key
```

网关从环境变量读取配置，`cpp_gateway/scripts/start_gateway.sh` 已经会加载根目录 `.env`。

```bash
GATEWAY_AUTH_ENABLED=true
GATEWAY_API_KEYS=admin=dev-secret,worker=worker-secret
GATEWAY_API_KEY_HEADER=X-API-Key
```

说明：

- `GATEWAY_API_KEYS` 支持逗号分隔的 `name=secret`、`name:secret` 或纯 secret。
- `name` 会作为限流 principal；纯 secret 会生成本地指纹，避免把原始 key 写进 Redis key。
- `GATEWAY_AUTH_ENABLED` 默认在存在 `GATEWAY_API_KEYS` 时启用；生产环境建议显式设置为 `true`。
- 鉴权失败返回 `401`，响应体形如：`{"ok":false,"code":"UNAUTHORIZED","message":"missing API key"}`。

## Redis 限流

实现位于 `cpp_gateway/src/common/GatewaySecurity.*`，使用 Drogon 默认 Redis client：

1. IP 维度：按客户端 IP 计数。
2. User 维度：优先使用 `X-User-Id`，没有时使用 API Key principal；如果二者都没有，则只做 IP 限流。
3. Redis key 使用固定窗口，执行 `INCR`；首次命中时设置 `EXPIRE`。

可配置项：

```bash
GATEWAY_RATE_LIMIT_ENABLED=true
GATEWAY_RATE_LIMIT_WINDOW_SECONDS=60
GATEWAY_RATE_LIMIT_IP_LIMIT=120
GATEWAY_RATE_LIMIT_USER_LIMIT=60
GATEWAY_RATE_LIMIT_FAIL_OPEN=false
GATEWAY_RATE_LIMIT_REDIS_PREFIX=rag_gateway:rate_limit
GATEWAY_TRUST_X_FORWARDED_FOR=false
```

说明：

- 默认窗口为 60 秒。
- IP 默认每窗口 120 次；User 默认每窗口 60 次。
- `GATEWAY_RATE_LIMIT_FAIL_OPEN=false` 时 Redis 异常返回 `503 RATE_LIMIT_UNAVAILABLE`；设置为 `true` 时 Redis 异常会放行并写 warning 日志。
- `GATEWAY_TRUST_X_FORWARDED_FOR=true` 时才信任 `X-Forwarded-For` / `X-Real-IP`，否则使用连接 peer IP。
- 限流命中返回 `429`，并带 `Retry-After` 以及 `X-RateLimit-IP-*` / `X-RateLimit-User-*` 响应头。

## 验证示例

启动前在 `.env` 中写入：

```bash
GATEWAY_AUTH_ENABLED=true
GATEWAY_API_KEYS=admin=dev-secret
GATEWAY_RATE_LIMIT_WINDOW_SECONDS=60
GATEWAY_RATE_LIMIT_IP_LIMIT=3
GATEWAY_RATE_LIMIT_USER_LIMIT=2
```

重新启动 Gateway：

```bash
bash cpp_gateway/scripts/start_gateway.sh
```

缺少 API Key：

```bash
curl -i http://127.0.0.1:8080/v1/monitor/overview
```

携带 API Key：

```bash
curl -i http://127.0.0.1:8080/v1/monitor/overview \
  -H "X-API-Key: dev-secret" \
  -H "X-User-Id: demo-user"
```

重复请求超过窗口阈值后会返回 `429 RATE_LIMITED`。
