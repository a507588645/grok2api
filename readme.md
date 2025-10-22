# grok2api

基于 FastAPI 重构的 grok2api，全面适配最新 Web 调用格式，支持流式对话、图像生成、图像编辑、联网搜索、深度思考，号池并发与自动负载均衡一体化。


<br>

## 使用说明

### 调用次数与配额

- **普通账号（Basic）**：免费使用 **80 次 / 20 小时**
- **Super 账号**：配额待定（作者未测）
- 系统自动负载均衡各账号调用次数，可在**管理页面**实时查看用量与状态

### 图像生成功能

- 在对话内容中输入如“给我画一个月亮”自动触发图片生成
- 每次以 **Markdown 格式返回两张图片**，共消耗 4 次额度
- **注意：Grok 的图片直链受 403 限制，系统自动缓存图片到本地。必须正确设置 `Base Url` 以确保图片能正常显示！**

### 视频生成功能
- 选择 `grok-imagine-0.9` 模型，传入图片和提示词即可（方式和 OpenAI 的图片分析调用格式一致）
- 返回格式为 `<video src="{full_video_url}" controls="controls"></video>`
- **注意：Grok 的视频直链受 403 限制，系统自动缓存图片到本地。必须正确设置 `Base Url` 以确保视频能正常显示！**

```
curl https://你的服务器地址/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GROK2API_API_KEY" \
  -d '{
    "model": "grok-imagine-0.9",
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "让太阳升起来"
          },
          {
            "type": "image_url",
            "image_url": {
              "url": "https://your-image.jpg"
            }
          }
        ]
      }
    ]
  }'
```

### 关于 `x_statsig_id`

- `x_statsig_id` 是 Grok 用于反机器人的 Token，有逆向资料可参考
- **建议新手勿修改配置，保留默认值即可**
- 尝试用 Camoufox 绕过 403 自动获 id，但 grok 现已限制非登陆的`x_statsig_id`，故弃用，采用固定值以兼容所有请求

<br>

## 如何部署

### 快速开始（推荐）

使用 Docker Compose 一键部署：

```bash
# 1. 创建 docker-compose.yml 文件
# 2. 启动服务
docker-compose up -d

# 3. 查看日志
docker-compose logs -f

# 4. 访问管理后台
# 浏览器访问: http://your-server-ip:8000/login
# 默认用户名: admin
# 默认密码: admin
```

**⚠️ 重要提示：**
- 首次部署后，请立即登录管理后台修改默认密码
- 必须在管理后台添加 Grok Token 才能使用服务
- 建议正确配置 `base_url` 参数以确保图片和视频功能正常

### docker-compose 配置

```yaml
services:
  grok2api:
    image: ghcr.io/a507588645/grok2api:latest
    ports:
      - "8000:8000"
    volumes:
      - grok_data:/app/data
      - ./logs:/app/logs
    environment:
      # =====存储模式: file, mysql 或 redis=====
      - STORAGE_MODE=file
      # =====数据库连接 URL (仅在STORAGE_MODE=mysql或redis时需要)=====
      # - DATABASE_URL=mysql://user:password@host:3306/grok2api

      ## MySQL格式: mysql://user:password@host:port/database
      ## Redis格式: redis://host:port/db 或 redis://user:password@host:port/db
    restart: unless-stopped

volumes:
  grok_data:
```

### Docker 命令行部署

```bash
# 拉取最新镜像
docker pull ghcr.io/a507588645/grok2api:latest

# 启动容器
docker run -d -p 8000:8000 --name grok2api \
  -v grok_data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e STORAGE_MODE=file \
  --restart unless-stopped \
  ghcr.io/a507588645/grok2api:latest

# 查看日志
docker logs -f grok2api
```

### 本地开发部署

```bash
# 1. 克隆仓库
git clone https://github.com/a507588645/grok2api.git
cd grok2api

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务
python main.py

# 服务将在 http://localhost:8000 启动
```

### 环境变量说明

| 环境变量      | 必填 | 默认值 | 说明                                    | 示例 |
|---------------|------|--------|----------------------------------------|------|
| STORAGE_MODE  | 否   | file   | 存储模式：file/mysql/redis              | file |
| DATABASE_URL  | 条件 | -      | 数据库连接URL（MySQL/Redis模式时必需）  | mysql://user:pass@host:3306/db |

**存储模式详解：**
- `file`: 本地文件存储（默认），适合单机部署，无需额外配置
- `mysql`: MySQL数据库存储，适合分布式部署，需设置 DATABASE_URL
- `redis`: Redis缓存存储，适合高并发场景，需设置 DATABASE_URL

**数据库 URL 格式：**
- MySQL: `mysql://username:password@hostname:3306/database_name`
- Redis: `redis://hostname:6379/0` 或 `redis://username:password@hostname:6379/0`

### 构建自定义镜像

#### 自动构建（GitHub Actions）

默认仓库已内置 GitHub Actions 工作流（`.github/workflows/docker.yml`），当代码推送到 `main` 分支或打上 `v*` 标签时，会自动构建多架构 Docker 镜像并推送到 GitHub Container Registry。

**配置步骤：**
1. 在 GitHub 仓库的 **Settings → Actions → General** 中，确保允许 GitHub Actions 访问 `GITHUB_TOKEN` 的写入权限
2. 推送到 `ghcr.io` 无需额外配置，使用仓库内置的 `GITHUB_TOKEN`
3. 推送到 Docker Hub 需在 **Settings → Secrets and variables → Actions** 中添加凭证

#### 手动构建

```bash
# 登录容器注册表（以 ghcr.io 为例）
echo "<个人访问令牌>" | docker login ghcr.io -u <GitHub用户名> --password-stdin

# 构建多架构镜像并推送
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag ghcr.io/a507588645/grok2api:latest \
  --push .

# 仅本地构建测试
docker build -t grok2api:local .
```

### 部署故障排查

#### 容器无法启动
```bash
# 查看容器日志
docker logs grok2api

# 检查容器状态
docker ps -a | grep grok2api

# 常见原因：
# 1. 端口被占用：修改 docker-compose.yml 中的端口映射
# 2. 数据目录权限：确保 Docker 有权限访问挂载的目录
```

#### 数据库连接失败
```bash
# 检查 DATABASE_URL 格式是否正确
# MySQL: mysql://user:pass@host:3306/dbname
# Redis: redis://host:6379/0

# 测试数据库连接
docker exec -it grok2api python -c "from app.core.storage import storage_manager; import asyncio; asyncio.run(storage_manager.init())"
```

#### 图片/视频无法显示
- 确保在管理后台正确设置了 `base_url` 参数
- `base_url` 应为服务的完整访问地址，例如：`http://your-domain.com` 或 `http://your-ip:8000`
- 检查防火墙是否开放了 8000 端口

#### 无法访问管理后台
- 确认容器正在运行：`docker ps | grep grok2api`
- 检查端口映射是否正确：`docker port grok2api`
- 尝试访问：`http://localhost:8000/login`（本地）或 `http://your-server-ip:8000/login`（远程）

<br>

## 接口说明

> 与 OpenAI 官方接口完全兼容，API 请求需通过 **Authorization header** 认证

### API 认证

所有 API 请求（除了管理接口）都需要在请求头中包含认证信息：

```bash
Authorization: Bearer YOUR_API_KEY
```

API 密钥可以在管理后台的系统配置中设置，如果未设置则不需要认证（不推荐用于生产环境）。

### 核心接口

| 方法  | 端点                         | 描述                               | 是否需要认证 |
|-------|------------------------------|------------------------------------|------|
| POST  | `/v1/chat/completions`       | 创建聊天对话（流式/非流式）         | ✅   |
| GET   | `/v1/models`                 | 获取全部支持模型                   | ✅   |
| GET   | `/images/{img_path}`         | 获取生成图片文件                   | ❌   |
| GET   | `/videos/{video_path}`       | 获取生成视频文件                   | ❌   |
| GET   | `/health`                    | 健康检查接口                       | ❌   |

### 使用示例

#### 基本对话

```bash
curl https://your-server.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "grok-3-fast",
    "messages": [
      {"role": "user", "content": "你好，介绍一下你自己"}
    ]
  }'
```

#### 流式对话

```bash
curl https://your-server.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "grok-3-fast",
    "messages": [
      {"role": "user", "content": "写一首诗"}
    ],
    "stream": true
  }'
```

#### 图像生成

在对话中直接描述需要生成的图像：

```bash
curl https://your-server.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "grok-3-fast",
    "messages": [
      {"role": "user", "content": "画一个可爱的小猫咪"}
    ]
  }'
```

#### 深度思考模式

使用支持深度思考的模型（如 grok-4-fast）：

```bash
curl https://your-server.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "grok-4-fast",
    "messages": [
      {"role": "user", "content": "请深入分析量子计算的发展前景"}
    ]
  }'
```

<br>

<details>
<summary>管理与统计接口（展开查看更多）</summary>

| 方法  | 端点                    | 描述               | 认证 |
|-------|-------------------------|--------------------|------|
| GET   | /login                  | 管理员登录页面     | ❌   |
| GET   | /manage                 | 管理控制台页面     | ❌   |
| POST  | /api/login              | 管理员登录认证     | ❌   |
| POST  | /api/logout             | 管理员登出         | ✅   |
| GET   | /api/tokens             | 获取 Token 列表    | ✅   |
| POST  | /api/tokens/add         | 批量添加 Token     | ✅   |
| POST  | /api/tokens/delete      | 批量删除 Token     | ✅   |
| GET   | /api/settings           | 获取系统配置       | ✅   |
| POST  | /api/settings           | 更新系统配置       | ✅   |
| GET   | /api/cache/size         | 获取缓存大小       | ✅   |
| POST  | /api/cache/clear        | 清理所有缓存       | ✅   |
| POST  | /api/cache/clear/images | 清理图片缓存       | ✅   |
| POST  | /api/cache/clear/videos | 清理视频缓存       | ✅   |
| GET   | /api/stats              | 获取统计信息       | ✅   |

</details>

<br>

## 可用模型一览

| 模型名称               | 计次   | 账户类型      | 图像生成/编辑 | 深度思考 | 联网搜索 | 视频生成 |
|------------------------|--------|--------------|--------------|----------|----------|----------|
| `grok-3-fast`          | 1      | Basic/Super  | ✅           | ❌       | ✅       | ❌       |
| `grok-4-fast`          | 1      | Basic/Super  | ✅           | ✅       | ✅       | ❌       |
| `grok-4-fast-expert`   | 4      | Basic/Super  | ✅           | ✅       | ✅       | ❌       |
| `grok-4-expert`        | 4      | Basic/Super  | ✅           | ✅       | ✅       | ❌       |
| `grok-4-heavy`         | 1      | Super        | ✅           | ✅       | ✅       | ❌       |
| `grok-imagine-0.9`     | -      | Basic/Super  | ✅           | ❌       | ❌       | ✅       |

<br>

## 配置参数说明

> 服务启动后，登录 `/login` 管理后台进行参数配置

| 参数名                     | 作用域  | 必填 | 说明                                    | 默认值 |
|----------------------------|---------|------|-----------------------------------------|--------|
| admin_username             | global  | 否   | 管理后台登录用户名                      | "admin"|
| admin_password             | global  | 否   | 管理后台登录密码                        | "admin"|
| log_level                  | global  | 否   | 日志级别：DEBUG/INFO/...                | "INFO" |
| image_mode                 | global  | 否   | 图片返回模式：url/base64                | "url"  |
| image_cache_max_size_mb    | global  | 否   | 图片缓存最大容量(MB)                     | 512    |
| video_cache_max_size_mb    | global  | 否   | 视频缓存最大容量(MB)                     | 1024   |
| base_url                   | global  | 否   | 服务基础URL/图片访问基准                 | ""     |
| api_key                    | grok    | 否   | API 密钥（可选加强安全）                | ""     |
| proxy_url                  | grok    | 否   | HTTP代理服务器地址（可手动输入或从代理池选择） | ""     |
| stream_chunk_timeout       | grok    | 否   | 流式分块超时时间(秒)                     | 120    |
| stream_first_response_timeout | grok | 否   | 流式首次响应超时时间(秒)                 | 30     |
| stream_total_timeout       | grok    | 否   | 流式总超时时间(秒)                       | 600    |
| cf_clearance               | grok    | 否   | Cloudflare安全令牌                      | ""     |
| x_statsig_id               | grok    | 是   | 反机器人唯一标识符                      | "ZTpUeXBlRXJyb3I6IENhbm5vdCByZWFkIHByb3BlcnRpZXMgb2YgdW5kZWZpbmVkIChyZWFkaW5nICdjaGlsZE5vZGVzJyk=" |
| filtered_tags              | grok    | 否   | 过滤响应标签（逗号分隔）                | "xaiartifact,xai:tool_usage_card,grok:render" |
| temporary                  | grok    | 否   | 会话模式 true(临时)/false               | true   |

### 代理池功能

系统支持从代理池 API 自动获取高质量代理 IP，并提供验证功能：

**功能特点：**
- 🔄 **自动获取**：从 [proxy.scdn.io](https://proxy.scdn.io) 代理池 API 自动获取代理
- ✅ **代理验证**：获取代理后自动验证其可用性
- 🎯 **协议筛选**：支持按协议类型筛选（HTTP、HTTPS、SOCKS4、SOCKS5 或全部）
- 📊 **智能选择**：在管理后台下拉列表中选择可用代理，可用代理标记 ✓，不可用标记 ✗
- 🔁 **一键刷新**：点击"获取代理"按钮即可重新获取最新代理列表

**使用方法：**
1. 登录管理后台 `/manage`
2. 进入 Setting 配置 → Grok 配置
3. 在"代理池"部分选择协议类型和数量
4. 点击"获取代理"按钮
5. 从下拉列表中选择可用的代理
6. 保存配置即可生效

**手动配置：**
您仍可以手动在 Proxy Url 输入框中输入自定义代理地址，格式如：
```
socks5://username:password@127.0.0.1:7890
```


<br>

## ⚠️ 注意事项

本项目仅供学习与研究，请遵守相关使用条款！

### 安全建议

1. **修改默认密码**：部署后立即在管理后台修改默认用户名和密码
2. **设置 API 密钥**：在管理后台配置 API 密钥以增强安全性
3. **使用 HTTPS**：生产环境建议通过反向代理（如 Nginx）配置 HTTPS
4. **防火墙配置**：仅开放必要端口，限制管理后台访问来源

### 生产环境部署建议

#### 1. 使用反向代理

建议使用 Nginx 或 Caddy 作为反向代理，提供 HTTPS 支持：

```nginx
# Nginx 配置示例
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        # 转发到本地应用（端口需与 docker-compose.yml 中的映射一致，默认为 8000）
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket 支持（如需要）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

#### 2. 数据持久化

确保数据目录持久化，避免容器重启导致数据丢失：

```yaml
volumes:
  # 使用命名卷（推荐）
  - grok_data:/app/data
  # 或使用主机目录
  - ./data:/app/data
```

#### 3. 日志管理

定期清理日志文件，避免磁盘空间不足：

```bash
# 限制日志目录大小
docker run ... -v $(pwd)/logs:/app/logs ...

# 或使用 Docker 日志驱动
docker run ... --log-driver json-file --log-opt max-size=10m --log-opt max-file=3 ...
```

#### 4. 性能优化

- **并发连接**：根据服务器配置调整 uvicorn workers 数量
- **缓存清理**：在管理后台定期清理图片/视频缓存
- **数据库优化**：使用 MySQL/Redis 存储模式以支持分布式部署

### 升级指南

```bash
# 停止服务
docker-compose down

# 拉取最新镜像
docker pull ghcr.io/a507588645/grok2api:latest

# 备份数据（重要！）
docker cp grok2api:/app/data ./data_backup

# 启动新版本
docker-compose up -d

# 查看日志确认正常运行
docker-compose logs -f
```

<br>

> 本项目基于以下项目学习重构，特别感谢：[LINUX DO](https://linux.do)、[VeroFess/grok2api](https://github.com/VeroFess/grok2api)、[xLmiler/grok2api_python](https://github.com/xLmiler/grok2api_python)
