# 多平台音乐下载器（MusicHub）

> 一个自托管的、运行在 Docker 容器里的多平台音乐下载与管理工具。第一版支持**网易云音乐**和 **QQ 音乐**两大平台官方接口，提供 Web UI 完成扫码登录、歌单浏览、批量下载、自动同步、本地库管理。
>
> **平台扩展说明**：架构层抽象出统一的 `Platform` 接口，未来新增酷我（`docs/` 下已有完整接口规范，作为后续版本的扩展资料）或其他平台时，只需新增一个适配模块，不影响核心业务逻辑。

---

## 一、项目目标

把"听到一首好歌 → 想保存到本地高质量收藏"这件事变成一个**纯一键操作**：

1. 浏览器打开容器服务，扫码登录两个平台账号一次。
2. 在 Web UI 上浏览每日推荐 / 热门 / 我喜欢 / 我创建 的歌单。
3. 点选**单曲、歌单、专辑**或粘贴链接 → 后台自动下载、嵌入封面/歌词/ID3 标签 → 按用户配置的语种/歌手/专辑目录结构保存。
4. 长期任务：订阅热门歌单或自动拉取平台 Top 榜，定期同步新增曲目；本地已下载的歌**永不重复下载**。
5. 自动按订阅的歌单生成 `m3u/m3u8` 播放列表，供本地播放器（Foobar2000、Plex、Roon、车机）直接读取。

---

## 二、功能清单（已与用户确认）

### 2.1 登录与账号管理

- 应用级访问密码：打开 Web UI 先输入访问密码，默认 `musichub`，可在「设置 → 安全」修改
- 两平台扫码登录：网易云（weapi 加密二维码）、QQ 音乐（QQ 扫码 + 微信扫码）
- Cookie 持久化到 SQLite，过期时前端弹窗提醒重新扫码
- 单用户场景，每个平台支持单账号

### 2.2 浏览与发现

| 入口 | 来源 |
|---|---|
| 每日推荐 | 网易云每日推荐、QQ `get_hot_recommend` |
| 热门歌单 | 同上 |
| 我的歌单 | 网易云"我的歌单"、QQ"创建/收藏" |
| 我喜欢 | 网易云的"我喜欢的音乐"歌单、QQ "我喜欢的歌曲" |
| 搜索 | 两平台并发搜索歌曲、专辑（结果去重合并） |
| URL 导入 | 粘贴 `music.163.com / y.qq.com` 任意歌曲/歌单/专辑链接，自动识别并跳转详情 |

### 2.3 下载

- **粒度**：单曲、歌单（整体下载）、专辑（整体下载）、批量勾选
- **去重**：以 `(歌名 + 主歌手 + 专辑)` 为唯一键，**跨平台只下一份**。同名歌不同专辑版本视为两首
- **音质降级**：用户在设置里选"最高音质"，下载时按平台支持降级直到拿到链接
  - 网易云：`lossless`（FLAC）→ `exhigh`（320k MP3）→ `standard`（128k MP3）
  - QQ：`F000`（FLAC）→ `O801`（OGG 640k）→ `M800`（320k MP3）→ `M500`（128k MP3）
- **元数据嵌入**（用户可选）：
  - 封面图片（嵌入到音频文件 + 同名 `.jpg` 旁存）
  - 歌词（嵌入 + 同名 `.lrc` 旁存）
  - ID3 标签 / FLAC tags（歌名、歌手、专辑、年份、流派）
- **并发**：默认 3 路，1-10 可调
- **重试**：单曲失败 3 次重试，间隔 2/5/10 秒

### 2.4 文件组织

- **目录结构**（用户二选一）：
  - 模式 A（简化）：`<歌手>/<歌曲>.<ext>`
  - 模式 B（推荐）：`<歌手>/<专辑>/<歌曲>.<ext>`
- **文件名格式**（用户三选一）：
  - 仅歌名：`七里香.flac`
  - 歌名+歌手：`七里香 - 周杰伦.flac`
  - 歌名+歌手+专辑：`七里香 - 周杰伦 - 七里香.flac`
- **非法字符**：`/ \ : * ? " < > |` 自动替换为空格

### 2.5 自动化

- **订阅指定歌单**（手动添加）：每隔 N 小时同步，新增的歌曲自动入下载队列
- **自动拉热门**（可勾选）：每天定时拉取两平台热门 Top X 歌单并入库订阅
- **自动同步任务**优先级低于用户手动触发的任务

### 2.6 M3U / M3U8 歌单生成

- 每个订阅的歌单自动生成对应的 `.m3u8` 文件
- 路径模式可配置（绝对路径 / 相对路径 / 自定义前缀）
- 输出格式：

  ```text
  #EXTM3U
  #PLAYLIST:华语精选

  #EXTINF:-1,周杰伦 - 七里香
  ../周杰伦/七里香.flac

  #EXTINF:-1,林俊杰 - 江南
  ../林俊杰/江南.mp3
  ```

### 2.7 Web UI 增强功能（用户确认全要）

| 功能 | 说明 |
|---|---|
| **全平台搜索** | 两平台并发搜索，结果去重合并，可直接下载或加入收藏 |
| **在线试听** | 浏览器 `<audio>` 试听低音质 URL，下载前听一下版本对不对 |
| **本地库浏览** | 已下载歌曲按语种/歌手/专辑筛选、搜索、删除 |
| **统计面板** | 总曲数、总占用空间、各语种占比、各平台占比、Top 10 歌手、最近 30 天下载趋势 |
| **URL 导入** | 粘贴任意两平台链接 → 自动识别跳详情或直接下载 |

热门歌单分类交互：

- 后端仍保留平台原始分类值，例如 `主题·ACG`、`场景·夜店`、`流派·R&B`，确保请求参数不丢语义。
- 前端按前缀分组展示为 `主题 / 场景 / 心情 / 年代 / 流派 / 语种` 等标题，chip 文案隐藏前缀，仅显示 `ACG / 夜店 / R&B`。
- 无前缀分类自动归入 `分类` 组，兼容网易云等普通分类列表。
- 订阅页动态热门分类为分组 pill 多选（前缀分组 + 短标签），支持 `全选` / `清空所选`；选中态仅在列表中高亮，避免与顶部摘要重复堆叠。平台返回的 `全部` / `全部分类` / `全选` 这类操作项不会作为普通分类展示或提交。当一次选择较多分类时，提交前会二次确认“将创建多少个父订阅、预计最多维护多少个子歌单”。
- 自定义添加已改为单项流程：`1 选择平台和类型` → `2 搜索并确认一个歌单/专辑/歌手` → `3 可选全平台聚合`。自定义添加一次只创建一个订阅；歌手/专辑开启 `全平台聚合` 会自动用主平台已选名称搜索另一平台，并展开候选列表让用户确认对应项。
- 自定义添加的单选结果采用紧凑已选卡片替代输入框，避免“输入框内容”和“已选提示”上下重复；需要更换时点击 `重新选择` / `清除`。

发现页订阅 M3U8 选项：

- 在发现页订阅每日推荐、单个歌单、歌单详情、专辑详情时，会先弹出订阅确认框。
- 确认框默认勾选 `生成 M3U8 播放列表`；取消勾选后只创建订阅和下载任务，不在 `_m3u` 目录生成播放列表。
- 热门歌单、排行榜、我的歌单的批量订阅同样支持该开关，并会把选择写入每个新建订阅的 `generate_m3u` 字段。
- 订阅页的动态热门歌单支持多选分类，但会按“每个分类一个父订阅”创建独立任务；每个任务可选择“保留历史入选”或“严格保持 TopN”。默认“保留历史入选”，例如民谣 Top5 中的 A 歌单第二天掉到 Top6 时仍继续订阅，只新增新入榜歌单，不自动删除 A。

---

## 三、技术栈

### 3.1 后端

| 用途 | 选型 |
|---|---|
| 语言 | Python 3.11+ |
| Web 框架 | FastAPI（自动 OpenAPI 文档） |
| ASGI 服务 | Uvicorn |
| HTTP 客户端 | httpx（通用平台） + qqmusic-api-python/niquests（QQ 音乐适配） |
| 加密算法 | pycryptodome（AES）+ 内置 hashlib（MD5） |
| 大整数运算 | 内置 `pow(base, exp, mod)`（裸 RSA） |
| 数据库 ORM | SQLAlchemy 2.0（async） + Alembic（迁移） |
| 数据库 | SQLite（默认，单文件） |
| 任务调度 | APScheduler（无外部依赖） |
| 音频元数据 | mutagen（MP3/FLAC/OGG 全格式） |
| 二维码生成 | qrcode + Pillow |
| 日志 | loguru（开箱即用） |
| 配置管理 | pydantic-settings + .env |

### 3.2 前端

| 用途 | 选型 |
|---|---|
| 框架 | Vue 3 + Composition API |
| 构建工具 | Vite 5 |
| UI 组件库 | Naive UI |
| CSS | TailwindCSS |
| 状态管理 | Pinia |
| 路由 | Vue Router 4 |
| HTTP 客户端 | axios |
| 实时通信 | 原生 WebSocket（下载进度推送） |
| 图标 | @vicons（Naive UI 配套） |

### 3.3 部署

- 单 Docker 镜像（多阶段构建）
- 默认端口 5173（Docker 对外与容器内 FastAPI 均使用 5173）
- 挂载点：`/music`（音乐输出）、`/config`（数据库 + Cookie + 配置）

---

## 四、系统架构图

```
┌──────────────────────────────────────────────┐
│              浏览器 (Vue 3 + Naive UI)        │
└──────────────┬─────────────────┬──────────────┘
               │ HTTP/REST       │ WebSocket
               ▼                 ▼
┌──────────────────────────────────────────────┐
│           FastAPI 路由层 (api/)              │
│  /api/auth  /api/discover  /api/download     │
│  /api/library  /api/settings  /api/stats     │
│  /ws/progress（下载进度推送）                  │
└──────────────┬───────────────────────────────┘
               ▼
┌──────────────────────────────────────────────┐
│           核心服务层 (services/)              │
│ ┌─auth     ─ 两平台扫码登录、Cookie 管理 ─┐  │
│ ├─discover ─ 推荐 / 我的 / 搜索 / URL 解析┤  │
│ ├─resolve  ─ 歌单/专辑展开 → 歌曲列表    ┤  │
│ ├─download ─ 音质降级 + 并发下载 + 重试  ┤  │
│ ├─tag      ─ mutagen 写入元数据         ┤  │
│ ├─organize ─ 语种判定 + 路径组织 + 命名  ┤  │
│ ├─m3u      ─ m3u8 文件生成              ┤  │
│ └─dedupe   ─ 去重判定 + 跨平台合并      ┘  │
└──────────────┬───────────────────────────────┘
               ▼
┌──────────────────────────────────────────────┐
│       平台适配层 (platforms/)                │
│ ┌─base       ─ 统一抽象接口，未来扩展用    ┐ │
│ ├─netease    ─ weapi/eapi 加密 + 接口实现  ┤ │
│ └─qq         ─ musicu.fcg 接口 + 微信登录  ┘ │
└──────────────┬───────────────────────────────┘
               ▼
┌──────────────────────────────────────────────┐
│          基础设施层                           │
│ ┌─crypto    ─ AES/RSA/MD5/XOR 通用工具     ┐│
│ ├─scheduler ─ APScheduler 定时任务         ┤│
│ ├─db        ─ SQLAlchemy 模型 + 仓储模式   ┤│
│ ├─config    ─ pydantic-settings           ┤│
│ └─logging   ─ loguru 全局日志              ┘│
└──────────────────────────────────────────────┘
```

---

## 五、目录结构

```
下载音乐/
├── readme.md                  ← 本文件，项目总规划
├── docs/                      ← 已有的接口规范文档
├── docker-compose.yml
├── Dockerfile                 ← 多阶段构建
├── .env.example
│
├── backend/                   ← Python 后端
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/               ← 数据库迁移
│   ├── app/
│   │   ├── main.py            ← FastAPI 入口
│   │   ├── config.py          ← 全局配置
│   │   ├── api/               ← 路由
│   │   │   ├── auth.py
│   │   │   ├── discover.py
│   │   │   ├── download.py
│   │   │   ├── library.py
│   │   │   ├── settings.py
│   │   │   ├── stats.py
│   │   │   └── ws.py
│   │   ├── services/          ← 业务层
│   │   │   ├── auth_service.py
│   │   │   ├── discover_service.py
│   │   │   ├── resolve_service.py
│   │   │   ├── download_service.py
│   │   │   ├── tag_service.py
│   │   │   ├── organize_service.py
│   │   │   ├── m3u_service.py
│   │   │   └── dedupe_service.py
│   │   ├── platforms/         ← 平台适配
│   │   │   ├── base.py        ← 抽象基类（Platform 接口契约）
│   │   │   ├── netease/
│   │   │   └── qq/
│   │   ├── crypto/            ← 加密算法
│   │   │   ├── netease_weapi.py
│   │   │   ├── netease_eapi.py
│   │   │   ├── netease_linux.py
│   │   │   └── qq_hash33.py
│   │   ├── db/                ← 数据库
│   │   │   ├── models.py
│   │   │   ├── session.py
│   │   │   └── repositories/
│   │   ├── scheduler/         ← 定时任务
│   │   │   ├── jobs.py
│   │   │   └── runner.py
│   │   └── utils/
│   └── tests/
│
└── frontend/                  ← Vue 前端
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.js
    ├── tsconfig.json
    ├── index.html
    └── src/
        ├── main.ts
        ├── App.vue
        ├── router/
        ├── stores/            ← Pinia
        ├── api/               ← axios 封装
        ├── views/
        │   ├── Discover.vue   ← 浏览/搜索
        │   ├── Library.vue    ← 本地库
        │   ├── Tasks.vue      ← 任务列表
        │   ├── Stats.vue      ← 统计面板
        │   └── Settings.vue   ← 设置
        ├── components/
        └── composables/
```

---

## 六、数据库设计（关键表）

### 6.1 `songs` 已下载歌曲（**去重核心**）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT | 歌名（原始） |
| name_norm | TEXT | 标准化歌名（去空格、繁简、半全角统一）|
| artist | TEXT | 主歌手 |
| artist_norm | TEXT | 标准化主歌手 |
| album | TEXT | 专辑名 |
| album_norm | TEXT | 标准化专辑名 |
| duration_ms | INTEGER | 时长 |
| file_path | TEXT | 本地文件相对路径 |
| file_size | INTEGER | 文件大小（字节） |
| audio_format | TEXT | mp3 / flac / ogg |
| bitrate | INTEGER | 实际码率 |
| has_cover | BOOLEAN | 是否嵌入封面 |
| has_lyric | BOOLEAN | 是否有歌词 |
| created_at | DATETIME | 下载时间 |

唯一约束：`UNIQUE(name_norm, artist_norm, album_norm)` ← **跨平台去重的核心**

### 6.2 `song_sources` 歌曲的多平台来源

| 字段 | 说明 |
|---|---|
| song_id | 外键 → songs.id |
| platform | netease / qq |
| platform_song_id | 平台内 ID（网易 id / QQ songmid）|
| max_quality | 该来源能取到的最高音质 |

### 6.3 `playlist_subscriptions` 订阅的歌单

| 字段 | 说明 |
|---|---|
| id | PK |
| platform | netease / qq |
| platform_playlist_id | |
| name | 歌单名 |
| auto_added | 是否由"自动拉热门"添加 |
| sync_interval_hours | 同步间隔（默认 24） |
| last_sync_at | |
| m3u_file_path | 输出的 m3u8 路径 |
| enabled | 是否启用 |

### 6.4 `download_tasks` 下载任务

| 字段 | 说明 |
|---|---|
| id | PK |
| target_type | song / playlist / album |
| target_id | |
| platform | |
| status | pending / running / success / failed / skipped_dup |
| priority | 0=auto，10=manual |
| error_msg | |
| created_at / updated_at | |

### 6.5 `accounts` 平台账号

| 字段 | 说明 |
|---|---|
| platform | netease / qq |
| cookie_json | 完整 Cookie |
| user_id / nickname / vip_type / avatar_url | 顶部 Header / 设置页展示账号信息 |
| expires_at | 过期估算时间 |

### 6.6 `settings` 全局设置

key-value 形式存储用户配置（音质、并发数、目录模式、文件命名格式等）。

---

## 七、配置项一览（设置页可视化编辑）

| 分组 | 配置项 |
|---|---|
| **下载** | 最高音质、并发数、失败重试次数、是否限速 |
| **元数据** | 是否嵌入封面、是否嵌入歌词、是否旁存 .lrc、是否旁存 .jpg、是否写 ID3 标签 |
| **目录** | 二级目录模式（A/B）、文件命名格式 |
| **自动化** | 是否启用"自动拉热门"、热门 Top X、订阅同步间隔 |
| **M3U** | 是否生成、路径模式、相对路径前缀 |
| **平台账号** | 两平台 Cookie 管理（网易云 + QQ 音乐） |

---

## 八、API 接口规划（草案）

### 8.1 认证

```
POST   /api/auth/qr/{platform}       获取扫码登录二维码（platform = netease|qq）
GET    /api/auth/qr/{platform}/poll  轮询扫码状态
POST   /api/auth/qq/wechat           QQ 音乐微信扫码登录辅助接口
DELETE /api/auth/{platform}          登出
GET    /api/auth/status              两平台登录状态汇总
```

### 8.2 发现

```
GET    /api/discover/recommend?platform=...        每日推荐
GET    /api/discover/hot?platform=...              热门歌单
GET    /api/discover/my-playlists?platform=...     我的歌单
GET    /api/discover/playlist/{platform}/{id}      歌单详情（展开歌曲）
GET    /api/discover/album/{platform}/{id}         专辑详情
GET    /api/discover/song/{platform}/{id}          单曲详情
GET    /api/search?q=...&type=song|album           全平台搜索
POST   /api/discover/parse-url                     URL 导入解析
GET    /api/discover/preview/{platform}/{id}       试听 URL（低音质）
```

### 8.3 下载

```
POST   /api/download/song      { platform, id }
POST   /api/download/playlist  { platform, id }
POST   /api/download/album     { platform, id }
POST   /api/download/batch     { items: [...] }
GET    /api/download/tasks?status=...     任务列表
DELETE /api/download/tasks/{id}           取消任务
WS     /ws/progress                       进度推送
```

### 8.4 本地库

```
GET    /api/library/songs?lang=...&artist=...&q=...   按条件查询
DELETE /api/library/songs/{id}                        删除（同时删文件）
GET    /api/library/artists                            歌手列表
GET    /api/library/albums                             专辑列表
```

### 8.5 订阅与 M3U

```
GET    /api/subscriptions                  订阅列表
POST   /api/subscriptions                  添加订阅
DELETE /api/subscriptions/{id}             取消订阅
POST   /api/subscriptions/{id}/sync        立即同步
POST   /api/m3u/regenerate                 重新生成所有 m3u
```

### 8.6 设置 & 统计

```
GET    /api/access/status                  访问会话状态
POST   /api/access/login                   输入访问密码，返回会话 token
POST   /api/access/password                修改访问密码
POST   /api/access/logout                  退出访问会话
GET    /api/settings
PUT    /api/settings
GET    /api/stats/overview                 总览
GET    /api/stats/trend                    趋势
```

---

## 九、Docker 部署

### 9.1 docker-compose.yml

```yaml
services:
  musichub:
    image: eianz/musichub:latest
    container_name: musichub
    restart: unless-stopped
    ports:
      - "5173:5173"
    volumes:
      - ./music:/music
      - ./config:/config
```

端口、时区、`MUSIC_DIR`/`CONFIG_DIR`/`LOG_LEVEL` 等默认值已在镜像构建时写入；需要调试可在服务下增加 `environment`。仓库里的 **`docker-compose.yml`** 仅拉取 **`eianz/musichub:latest`**（无需源码）。开发者本地从 Dockerfile 构建：`docker build -t eianz/musichub:latest .`

### 9.2 Docker Hub 自动构建（GitHub Actions）

源码仓库：<https://github.com/ffoocn/MusicHub>。

向 **`main` 或 `master`** 推送代码，或推送 **`v*` 语义化标签**（如 `v1.0.0`）时，仓库中的工作流会自动构建根目录 `Dockerfile` 并推送到 Docker Hub 镜像 **`eianz/musichub`**。

**一次性配置（GitHub 仓库 → Settings → Secrets and variables → Actions → New repository secret）：**

| Name | 说明 |
|------|------|
| `DOCKERHUB_USERNAME` | Docker Hub 用户名（例如 `eianz`） |
| `DOCKERHUB_TOKEN` | Docker Hub **Access Token**（在 [Docker Hub Account Settings → Security](https://hub.docker.com/settings/security) 创建；不要用账户登录密码） |

推送默认分支时通常会打上 **`latest`** 以及当前 **`git` 提交短 SHA** 等标签；打 `v1.2.3` 类标签时会额外打上对应版本号标签。

也可在 Actions 页面对 **Publish Docker image** 工作流手动 **Run workflow**（`workflow_dispatch`）。

拉取预构建镜像示例：

```bash
docker pull eianz/musichub:latest
```

部署时复制 **`docker-compose.yml`**（或与 §9.1 示例等价），执行 **`docker compose pull && docker compose up -d`** 即可；镜像名与 CI 推送的 **`eianz/musichub:latest`** 一致。

**CI 构建失败排查**：

- **前端 `npm run build` / `vue-tsc`**：根目录 `.gitignore` 须用 **`/music/`**（仅忽略仓库根目录），不能用宽泛的 `music/`，否则会误忽略 `frontend/src/components/music/`。
- **Docker 登录 `Password required`**：`DOCKERHUB_TOKEN` 未填或为空。**删除 GitHub 仓库再新建后，Actions Secrets 会清空**，须在 Settings → Secrets 中重新添加 Docker Hub **Access Token**（不要用账户登录密码），并与工作流中的名称一致：`DOCKERHUB_USERNAME`、`DOCKERHUB_TOKEN`。

### 9.3 启动后

1. 浏览器打开 `http://<host>:5173`
2. 进入"账号" → 扫码登录两个平台（网易云 + QQ 音乐）
3. 进入"设置" → 配置音质 / 目录结构 / 语种分类 / 自动化
4. 进入"发现" → 浏览或搜索 → 下载
5. 文件保存在 `./music` 下，按语种分类
6. m3u8 歌单自动生成在 `./music/_m3u/` 下

---

## 十、开发路线图（分阶段交付）

为避免一次性开发周期过长，规划成 5 个里程碑，每个里程碑结束都能在 Docker 里跑起来看到效果：

### ✅ Milestone 1：项目骨架 + 加密与平台适配核心（已完成）

- ✅ 建项目目录、Dockerfile、依赖文件、数据库 ORM 模型
- ✅ 实现 4 套加密算法 + 21 个单元测试通过（网易云 weapi / eapi / linux api、QQ hash33）
- ✅ 两平台 client（登录、搜索、单曲、歌单、专辑、下载 URL）
- ✅ 后端 + 前端能跑空架子，前端打开能看到首页
- ✅ CLI 测试脚本能扫码登录、能搜歌、能下载一首单曲

### ✅ Milestone 2：完整下载链路 + 元数据写入（已完成）

- ✅ 音质降级（按设置 lossless → exhigh → standard 顺序尝试）、并发下载、失败重试（默认 3 次，间隔 2/5/10s）
- ✅ mutagen 写入 ID3v2.4 / FLAC vorbis comment、封面（APIC/Picture）、歌词（USLT）
- ✅ 语种判定服务：默认四分类（中文/欧美/日韩/其他），按 Unicode 字符段 + 歌手关键字白名单匹配
- ✅ 目录组织：`<语种>/<歌手>/<专辑>/<歌曲>.<ext>` 或 `<语种>/<歌手>/<歌曲>.<ext>`
- ✅ 文件命名：仅歌名 / 歌名+歌手 / 歌名+歌手+专辑 三选一
- ✅ 跨平台去重：`(name_norm, artist_norm, album_norm)` 三元组 + 时长 ±5s 辅助判断
- ✅ 设置页 UI：「下载偏好」「目录与命名」「语种分类」可视化配置 + 自动保存
- ✅ 搜索页 UI：双平台合并、封面/时长/平台标签、一键下载
- ✅ Cookie 字符串导入登录作为兜底（应对扫码不能完整换 cookie 的场景）
- ✅ **端到端验证**：网易云已登录 → 搜索 → 一键下载 →
  `中文/毛不易/平凡的一天/消愁 - 毛不易.flac` (24MB lossless) +
  `消愁 - 毛不易.lrc` 旁存 + 入库 + 二次点同首歌 `skipped_dup=True`

> **已知问题**（推迟到 M3 处理）：
> - 网易云 `register/anonimous` 接口需要 `cloudmusicDllEncode` 算法生成 username，未实现，但目前不影响核心功能。

### Milestone 3：歌单/专辑批量 + 任务系统 + 进度推送 ✅ 已完成

后端：

- ✅ `DownloadTask` 模型扩展：`parent_task_id` 父子关联、`source_subscription_id` /
  `sync_run_id` / `source_type` 来源追踪，以及完整来源列表
  `source_subscription_ids_json` / `sync_run_ids_json` / `source_types_json`、`payload_json`、`started_at` /
  `finished_at`、`file_path`、`audio_format`、`bitrate`、`quality`、`file_size`、`error_msg`
- ✅ `services/task_manager.py` 异步任务队列 + worker pool（默认 3 路并发，从 settings 读）
  - 单例 `TaskManager.get()`，应用 `lifespan` 启动 / 关闭
  - 服务重启时自动恢复未完成的 `running`/`queued` 任务
  - 队列调度：每个 worker 取 `task_id` → 加载 `payload_json` 还原 `SongInfo`
    → 调用 `download_song()` → 持久化结果 + 广播事件
  - 父任务（playlist/album）自动聚合子任务进度
  - 支持取消未开始的任务（已 running 不可取消）
  - 下载流通过 progress callback 节流回写 `progress/file_size` 并实时广播
  - 队列暂停状态持久化到 `queue.paused`，服务重启后自动恢复
  - 复用已有 queued/running 任务时会追加当前订阅来源，下载完成后按所有来源订阅刷新 M3U
  - running 任务完成前会重新读取最新来源，避免下载中途被其他订阅复用后漏刷新 M3U
  - 删除订阅时，共享 queued/pending 任务只移除该订阅来源，不误取消其他订阅仍需要的下载
  - 若任务仍有 `manual/playlist_download/album_download` 来源，删除订阅不会取消用户主动发起的排队下载
  - 同一首歌的入队查找/来源合并/任务创建用 key 锁串行化，避免并发 Sync 覆盖来源列表
  - 歌单/专辑批量下载复用单曲入队去重逻辑，父任务通过 `child_task_ids` 聚合复用任务，不改写复用任务原有 `parent_task_id`
- ✅ `services/local_file_service.py` 统一清理音频主体和 `.lrc/.jpg/.jpeg/.png/.webp` sidecar
  - 本地库删除失败时保留数据库记录，避免 UI 失去管理入口
  - 任务批量删除和下载失败清理复用同一套删除语义
- ✅ 数据库轻量迁移：`init_db()` 内置 `_auto_migrate`，新增字段自动 `ALTER TABLE ADD COLUMN`
- ✅ API：
  - `POST /api/download/song`（异步入队，`?sync=true` 可同步）
  - `POST /api/download/songs`（多首批量入队）
  - `POST /api/download/playlist`（歌单展开 + 父子任务）
  - `POST /api/download/album`（专辑展开 + 父子任务）
  - `GET  /api/discover/playlist/{platform}/{id}` 歌单详情 + 完整曲目
  - `GET  /api/discover/album/{platform}/{id}` 专辑详情 + 完整曲目
  - `GET  /api/tasks` 列表（按状态筛选 + 分页）
  - `GET  /api/tasks/summary` 各状态计数（顶部角标用）
  - `GET  /api/tasks/{id}` 详情含子任务
  - `DELETE /api/tasks/{id}` 取消
  - `DELETE /api/tasks?status=success` 清理历史
- ✅ WebSocket `/api/tasks/ws` 实时推送
  - 内置 `_Broadcaster`：每个订阅者一个 `asyncio.Queue`
  - 事件：`task.created`、`task.updated`
  - 队列溢出时丢最旧消息

前端：

- ✅ `stores/tasks.ts` Pinia store：连 WS、自动重连、缓存任务 Map
- ✅ `views/Tasks.vue` 任务页：状态分类筛选、实时进度条、取消/清理
- ✅ `views/PlaylistDetail.vue` / `AlbumDetail.vue` 详情页 + 多选批量下载 + 整体下载（建父任务）
- ✅ `components/SongListTable.vue` 公共歌曲列表（多选 / 单首 / 整体下载）
- ✅ `components/UrlImportPanel.vue` URL 导入：网易云 / QQ 链接自动识别
- ✅ Discover 搜索结果：多选 + 批量入队，专辑名可点击跳详情页
- ✅ AppLayout 顶部角标：实时显示运行中数量（badge）

**验收（已通过）**：

- 入队 3 首网易云 → 3 路并发同时跑 → 4 秒下完两首 MP3 / FLAC → WebSocket 推送 8 条事件
  （3 个 `task.created` + 6 个 `task.updated`）
- 网易云"飙升榜"歌单详情 API 一次拿回 100 首曲目，可整体入队

### Milestone 4：订阅 + 自动化 + M3U 生成 ✅ 已完成

后端：

- ✅ `PlaylistSubscription` 模型扩展：`target_type`（playlist/album）/ `description` /
  `creator` / `tracks_json`（曲目 ID 快照，用于 diff）/ `last_sync_new_count` /
  `last_error` / `updated_at`
- ✅ `services/sync_service.py`：
  - 拉远端歌单/专辑 → 当前曲目列表
  - 与 `tracks_json` 做 diff，找出"本次新增"
  - 调 `dedupe.find_existing` + `SongSource` 双重过滤本地已有
  - 本地已有歌曲会补齐当前远端曲目的 `SongSource`，保证 `tracks_json` 能命中 M3U
  - 数据库记录存在但本地文件丢失时会重新下载，并更新原 Song 文件字段
  - 搜索兜底下载成功时会同时登记原始 ID 和实际下载 ID 的 `SongSource`
  - 搜索兜底只接受同名、同主歌手、时长接近的高置信度候选，避免错绑翻唱/Remix
  - 把"新增 + 未下载"的歌交给 `TaskManager.enqueue_song(priority=0)`
  - Sync report 区分 `enqueued`（新建任务）和 `already_queued`（复用已有 queued/running 任务）
  - 每次 Sync 写入 `sync_runs` 摘要，并把逐首处理结果写入 `sync_run_items`
  - 同步成功后立即触发 m3u 生成
- ✅ Meta 自动子订阅删除语义：
  - 用户主动删除 `auto_added` 子订阅时，会写入父订阅 `meta_config.suppressed_child_ids`
  - 后续 `_sync_meta` / `_sync_meta_hot_category` 不再自动恢复被用户隐藏的子订阅
- ✅ `services/m3u_service.py`：UTF-8 m3u8 + `#EXTINF` + 绝对路径，
  Foobar / VLC / Plex 可直接打开；生成时会过滤不存在的本地文件路径和异常 `SongSource` 映射
- ✅ 入库与删除一致性：
  - 命中已有且已有文件仍存在时，不用新下载路径覆盖 `Song.file_path`，重复下载文件会被清理
  - 删除本地文件以主体音频删除/缺失作为 DB 可删除条件，sidecar 失败不会保留不可播放记录
- ✅ `services/scheduler.py`：APScheduler `AsyncIOScheduler`
  - 启动时按 `sync_interval_hours` 给所有启用订阅注册 IntervalTrigger
  - 新订阅默认 30 秒后跑一次首同步
  - 增删改订阅时自动 `register/unregister`
  - `misfire_grace_time=120s` + `coalesce=True` 避免错过执行
- ✅ SQLite WAL 模式 + `busy_timeout=30s`：解决 worker / 同步 / API 三方并发
  写入冲突（`database is locked`）
- ✅ 删除订阅拆成短事务并对 SQLite 写锁做重试，避免批量删除父子订阅时因后台任务写入而 500
- ✅ API：
  - `GET    /api/subscriptions`
  - `POST   /api/subscriptions`（拉远端获取名/创建者/封面）
  - `PUT    /api/subscriptions/{id}`（启用/禁用、改间隔）
  - `DELETE /api/subscriptions/{id}`
  - `POST   /api/subscriptions/{id}/sync`（立即同步并返回 SyncReport）
  - `POST   /api/subscriptions/sync_all`
  - `GET    /api/subscriptions/sync_runs` / `GET /api/subscriptions/sync_runs/{id}/items`
  - `POST   /api/m3u/generate` / `POST /api/m3u/generate/{id}`

前端：

- ✅ `components/SubscriptionsManager.vue` 订阅管理 UI（添加 / 启用切换 / 立即同步 / 删除 /
  重建 m3u），URL 自动识别 ID
- ✅ 歌单详情页 / 专辑详情页"订阅自动同步"按钮（歌单 24h，专辑 168h 默认）

**验收（已通过）**：

- 订阅"网易云飙升榜"歌单 → 立即同步 → 远端 100 首全部检测为新增 → 100 个子任务入队
- 3 路并发下载 → 19 首成功后取消余下排队任务
- 自动生成 `_m3u/[netease] 飙升榜.m3u8`，含 `#EXTM3U` 头 + `#EXTINF:duration,artist - title` +
  绝对本地路径，可被本地播放器直接读取
- 重启服务后 scheduler 自动恢复 sub#1 的下次同步时间（next_run 基于上次 last_sync_at + 间隔）

### Milestone 5：增强功能（试听、本地库、统计） ✅ 已完成

后端：

- ✅ `api/preview.py` `GET /api/preview/song/{platform}/{id}?quality=standard`：
  返回平台的 `standard` 直链（约 128k MP3）+ 元数据（封面、时长、歌手、专辑）
- ✅ `api/library.py` 本地库：
  - `GET /api/library/songs` 多维度筛选（关键词 / 语种 / 歌手 / 专辑 / 排序 / 分页）
  - `GET /api/library/artists`、`/albums`、`/categories` 聚合维度
  - `GET /api/library/song/{id}` 单曲详情
  - `GET /api/library/stream/{id}` 本地音频流，**支持 Range 断点续传**（HTML5 audio 拖动进度条）
- ✅ `api/stats.py` 统计概览：总数 / 大小 / 时长 / 带词 / 带封面 +
  按格式 / 语种 / 平台 / 音质 / 任务状态 / 近 14 天每日下载

前端：

- ✅ `stores/player.ts` + `components/PlayerBar.vue`：
  - 单例 HTMLAudioElement，全 app 共享
  - `playRemote(platform, id)` 在线试听（请 `/api/preview/song`）
  - `playLocal(LibrarySong)` 本地流（`/api/library/stream/{id}`）
  - 底部固定播放条：封面 + 标题 + 进度条 + 拖动 seek + 音量 + 暂停/恢复
  - 主内容区动态留 padding，避免被遮挡
- ✅ `views/Library.vue` 本地库：关键词搜索 / 语种 / 歌手 / 排序 / 分页 + "播放"按钮一键听
- ✅ `views/Stats.vue` 统计面板：4 个 KPI 卡 + 4 张内置极简条形图 +
  14 天柱状图 + 任务状态 tag 云（不引入 echarts，零额外依赖）
- ✅ Discover 搜索结果：每行加"试听 ▶"按钮（标准音质流）
- ✅ URL 导入解析：在 M3 已完成（粘贴网易/QQ 链接自动识别歌曲/歌单/专辑跳转或入队）

**验收（已通过）**：

- 在 Discover 搜歌 → 点试听 ▶ → 底部播放条加载在线 MP3 立刻播放
- 在 Library 点本地歌 → 直接走 `/api/library/stream` 本地流（Range 支持）
- 统计页一眼看到：MP3 1 首 / FLAC 18 首；网易云 18 首；带词 18 / 带封面 19；
  最近 14 天柱状图所有下载集中在今天

### Milestone 6：发现页（每日推荐 / 热门歌单 / 我的歌单）✅ 已完成

后端 — `app/platforms/base.py` 新增 5 个默认空实现，平台按需重写，新加平台不强制实现：

- `recommend_songs(limit)` — 每日推荐歌曲
- `recommend_playlists(limit)` — 首页推荐歌单（个性化）
- `top_lists()` — 官方排行榜目录
- `hot_playlists(category, limit, offset)` — 分类热门歌单
- `user_playlists(user_id, limit, offset)` → `(created, collected)` 二元组 — 我创建/收藏

NetEase 实现：

- 每日推荐：`/weapi/v3/discovery/recommend/songs`（空 payload）
  + 风控兜底：拿不到时自动回退到飙升榜（id=19723756）前 N 首，
  保证用户在该 tab 永远看到内容
- 推荐歌单：`/weapi/personalized/playlist`（匿名也能拿）
- 排行榜：`/weapi/toplist/detail`（一次拿到 60+ 个榜单元数据）
- 分类歌单：`/weapi/playlist/list?cat={category}&order=hot`
- 我的歌单：`/weapi/user/playlist?uid={user_id}`
  → 按 `subscribed` 字段拆分 created / collected

QQ 暂用 base 默认空实现（musicid/qm_keyst 完全到位前不返回），
未来登录链路稳定后可补全。

API 路由 — `app/api/discover.py` 新增 5 个端点：

- `GET /api/discover/recommend/songs?platform=&limit=`
- `GET /api/discover/recommend/playlists?platform=&limit=`
- `GET /api/discover/toplists?platform=`
- `GET /api/discover/hot/playlists?platform=&category=&limit=&offset=`
- `GET /api/discover/my/playlists?platform=` → `{ created, collected, logged_in, nickname }`

前端：

- ✅ `components/PlaylistGrid.vue`：自适应网格的歌单卡片，
  显示封面 + 标题 + 创建者 + 曲目数 + 播放量；点击进入 `PlaylistDetail`
- ✅ `components/DailyPanel.vue`：每日推荐综合页 — 30 首歌曲表
  （多选 + 单首试听 + 单首下载 + 一键全下）+ 12 张推荐歌单卡片
- ✅ `components/HotPlaylistsPanel.vue`：分类 chips 现在通过 `GET /api/discover/hot/playlist-categories?platform=…` 动态拉取（网易云广场分类 ≈70；QQ 来自 `y.qq.com/n/ryqq_v2/category` SSR 全量目录 ≈80，按 `分组 · 名称` 展示），默认仅显示前 24 个 chip，多余的折叠到「更多分类」按钮，点击后展开/收起；切换平台会自动重新拉分类并重置选中项
  + 「分类热门 ↔ 官方排行榜」二档切换
- ✅ `components/MyPlaylistsPanel.vue`：未登录有引导文案；
  登录后分两区展示 — 我创建（含红心歌单）+ 我收藏
- ✅ `views/Discover.vue` — 把原有 3 个空 `n-empty` tab 替换为上述真实组件

**验收（已通过）**：

- `/recommend/songs?limit=5` → 5 首歌（兜底成功，拿到飙升榜前 5）
- `/recommend/playlists?limit=5` → 5 个个性化推荐歌单（含封面/曲目数/百万级播放量）
- `/toplists` → 62 个官方榜单（飙升 / 新歌 / 原创 / 热歌 / 中文说唱 / 古典 / 电音 / 全球说唱 ...）
- `/hot/playlists?category=华语&limit=4` → 4 个华语热门歌单
- `/my/playlists` → `logged_in=True nick="张白易安"` created=2 collected=4
- `/recommend/playlists?platform=qq` → `[]`（预期，QQ 未实现）
- 前端 4 个新文件全部通过 Vite HMR，组件内不报 lint
- 浏览器打开 Discover → 切到三个新 tab 均能看到内容；点歌单卡片正确进入详情页

---

## 十一、关键技术风险与缓解方案

| 风险 | 缓解 |
|---|---|
| 平台接口频繁变更 | 平台适配层全部抽象成接口，加监控埋点；接口失败时降级到下一档音质 / 下一个平台 |
| Cookie 过期没察觉 | 定期检测账号接口返回，过期前端弹通知 |
| 高音质付费内容拿不到 URL | 失败时按音质降级，最低降到 128k；记录失败原因 |
| QQ QRC 加密歌词解析复杂 | 第一版只用 LRC 普通歌词；QRC 列入 Milestone 5 备选 |
| 跨平台去重误判（同名不同歌） | 以 `(歌名 + 主歌手 + 专辑)` 标准化后做唯一键，并加入"时长容忍度 ±5s"作为辅助判断 |
| 下载并发被风控 | 默认 3 路并发 + User-Agent 轮换 + Cookie 透传 |
| 大歌单下载长时间运行 | 任务可断点续做，重启后从未完成的任务继续 |
| 后续扩展第三个平台 | `platforms/base.py` 定义统一接口契约，新增 `platforms/kuwo/` 目录即可，业务层零改动 |

---

## 十二、致后续维护者

- 每完成一个 Milestone，更新本 readme 的"开发路线图"对应阶段为 ✅
- 接口文档以 `docs/` 下原始文件为准；如有变更，先更新 `docs/`，再改代码
- 加密相关代码必须配套单元测试，因为这是最容易踩坑且 debug 困难的部分
- 平台抽象基类（`platforms/base.py`）是核心契约，新增平台时遵循该接口

---

**项目状态：M1 + M2 + M3 + M4 + M5 + M6 全部完成 ✅ — 自托管音乐管家 v1.1 发现页就绪**

TailAdmin UI 迁移进度：
- 已完成 TailAdmin 基础设施、应用壳层、通用业务组件、发现页、详情页、本地库、播放器、订阅、任务、统计、设置和账号管理的主要替换。
- 通用组件已补齐：`MusicCard`、`MusicButton`、`MusicBadge`、`MusicTabs`、`MusicTable`、`MusicEmpty`、`MusicModal`、`MusicFormField`、`MusicPlatformBadge`、`MusicSectionHeader`、`MusicToast`、`MusicConfirmDialog`、`MusicQrLoginState`；账号管理扫码状态和 Cookie 导入弹窗已接入统一组件。
- 前端已移除 Naive UI / `@vicons` 业务源码残留；`cd frontend && npm run build` 通过，TailAdmin 滚动条 CSS 的 minify 警告已修复。
- Milestone 10 已继续推进热加载 QA：统一了任务清理、任务取消、订阅删除、订阅添加弹窗的 TailAdmin modal / confirm 体系；本地热加载下主要业务路由和核心 API smoke 通过。
- 已修复 1024px 左右本地库/订阅页截图中出现的侧边栏覆盖主内容问题：sidebar 状态断点统一到 TailAdmin `xl`/1280px，主内容区增加横向溢出保护，移动/平板抽屉遮罩层级也已调整；1280-1535px 桌面宽度默认使用窄侧栏，订阅表格在该宽度下使用紧凑列宽，保证操作按钮可见。
- 平台视觉已从文字标签升级为图标：新增 `MusicPlatformIcon`，前端 public 资源中加入 `QQ音乐.png` / `网易云音乐.png`，订阅、任务、搜索、详情、歌曲列表、歌单卡片、播放器和账号状态均使用平台 icon 原图展示，不额外添加背景、边框和阴影。
- 统计页已 1:1 对齐 TailAdmin Stocks Dashboard 版式（`https://nextjs-demo.tailadmin.com/stocks`）：
  - **Row 1**：4 张指标卡（圆形 icon + 标题/副标题 + 大数字 + 趋势徽章）；
  - **Row 2**：左 2/3 "下载趋势" 折线区域图（SVG，含 14 天/7 天/全部 tab 切换、虚线网格、平滑贝塞尔）+ 右 1/3 "格式分布" 小柱图；
  - **Row 3**：左 2/3 "平台总览" 横向滚动卡片（带左右翻页箭头、订阅同步/查看曲库 按钮）+ 右 1/3 "任务状态" watchlist 列表；
  - **Row 4**：整宽 "分布矩阵" 表格（含搜索框、占比进度条、状态徽章），把音频格式/音质/平台维度统一成 Latest Transactions 风格的行。
- 修复了平台图标在统计页中被外层 flex 撑成超大色块的问题：`MusicPlatformIcon` 改为内联像素尺寸（xs 18 / sm 22 / md 28 / lg 36），不再依赖 Tailwind `size-*` 类受外层布局影响。
- 订阅与自动化页已按 TailAdmin Marketing + SaaS Activities 的混合版式重写：
  - **Row 1**：左 2/3 订阅明细表格（搜索 + 平台/类型筛选 + 隐藏自动 + 行内启停/调间隔/同步/删除/翻页）+ 右 1/3 来源构成（按平台 + 按类型双段式进度条列表）；
  - **Row 2**：左 2/3 同步活跃度趋势 SVG 折线区域图（14 天 / 7 天 / 全部 tab）+ 右 1/3 同步活动时间线（SaaS Activities 风格，按 last_sync_at 倒序展示状态彩色图标 + 名称 + 同步详情 + 相对时间）；
  - （已移除与订阅明细重复的「我的订阅」横滑卡片区；**添加订阅**弹窗：顶部为 **动态热门歌单**——平台下拉；分类在 `GET /api/discover/hot/playlist-categories` 拉取（网易云 `playlist/catalogue`；QQ 抓 `https://y.qq.com/n/ryqq_v2/category` SSR 注入的 `__INITIAL_DATA__.categories`，覆盖 热门 / 主题 / 场景 / 心情 / 年代 / 流派 / 语种 共约 80 项，失败时回退 `music.web_category_svr.get_hot_category`）后可多选，但提交时按分类拆成多个独立父订阅；选取方式支持 **播放量排名靠前** / **随机**，掉榜处理支持 **保留历史入选** / **严格保持 TopN**（`meta_config`: `categories`, `pick_mode`, `drop_policy`, `top_n`, `pool_size`；旧数据仅 `category` 仍兼容）；**其他一键订阅**收起到 `<details>`；自定义搜索/ID 仍在下方。）
  - 已移除原有的 4 张指标卡（全部订阅/已启用/同步成功率/即将到期），统计指标交给"来源构成"和"同步活跃度"承担，让页面顶部更聚焦于操作层（订阅明细 + 来源分布）。
  - 所有现有业务能力完整保留：列表/筛选/分页/添加订阅 modal（内含快速订阅 + 搜索建议 + 跨平台聚合 + ID/URL）/ 同步/删除/启停/m3u 重建。
- 本地库 `/library` 已按 TailAdmin File Manager 原版比例重整：
  - 页面外层使用 `grid grid-cols-12 gap-6`，All Media / Recent Files 占 12 列，中间 All Folders / Storage Details 为 `8:4`。
  - All Media 拆成 header 与 content 两段，媒体卡片使用原版 `52px` 图标、`rounded-2xl` 卡片和三列栅格。
  - All Folders 使用原版 `px-6 py-6 / xl:py-[27px]` 卡片比例；最新下载的歌手卡片仅作概览展示，已移除无实际功能的「查看全部」和三点菜单；Storage Details 放大为接近原版的 donut 区域；Recent Files 表格行高改为 `py-[18px]`。
  - Recent Files / 最近添加已改为完整本地歌曲表格：支持页内全选、逐行选择、批量删除本地文件与库记录，底部分页统一复用发现页 `MusicPagination`。
- 剩余重点是更细的桌面/移动端视觉截图 QA、扫码登录实测、订阅同步实测、远端试听实测；Docker 构建链路按当前计划后续适配时再验。
- 顶栏右上区域已对齐 TailAdmin（`https://nextjs-demo.tailadmin.com/`）风格：
  - 移除原有的「任务 chip」「实时连接 chip」「独立设置按钮」三块；
  - 新增 `components/layout/header/NotificationDropdown.vue`：圆形铃铛按钮 + ping 红点（基于本地 `lastSeenTaskId`，打开下拉即清零），下拉列出最近 6 条**父任务**作为通知（封面/状态点/平台 icon/相对时间/状态文案），底部「查看全部任务」跳 `/tasks`；
  - `HeaderAccountChip.vue` 重写：触发器去掉外边框，更接近 TailAdmin 紧凑 chip 样式；下拉新增「实时连接」状态行（来自 `tasksStore.connected`，已连接 / 连接中…）和「设置」「管理账号」两条菜单项；
  - 顶栏右侧最终只剩 `[ThemeToggler] [Notification] [HeaderAccountChip]` 三个元素，视觉与 TailAdmin Dashboard 保持一致。
- 顶栏「智能搜索框」已上线（`components/layout/header/SearchBar.vue`）：
  - 输入关键词回车 → 跳转 `/discover?q=...`，`SearchPanel` 通过监听 `route.query.q` 自动触发搜索；
  - 应用顶栏对齐 TailAdmin File Manager 原版的 `sticky top-0` 语义：顶栏位于主内容容器内，随侧边栏展开/折叠产生的主区域位移一起变化；布局祖先不再使用 `overflow-x-hidden`，避免破坏 sticky 吸顶。
  - 折叠侧边栏菜单项统一为 TailAdmin 接近的 `h-11` 行高和 `24px` 图标容器，避免不同 SVG 原始尺寸造成折叠态图标不一致。
  - 粘贴 `music.163.com` / `y.qq.com` 链接自动识别 → 歌曲直接调 `downloadApi.song` 入队，歌单/专辑跳详情页；
  - 解析逻辑抽离到 `utils/parseMusicUrl.ts`，与 `UrlImportPanel.vue` 共用同一套规则；
  - 输入框下方实时展示 hint："识别为 网易云 · 歌单，按 Enter 打开详情" / "按 Enter 搜索 「关键词」"；
  - `⌘/Ctrl + K` 全局快捷键聚焦搜索框。
- Discover 页布局重构（`views/Discover.vue`）：
  - 左侧导航移除「搜索」「链接导入」两个 tab，仅保留「平台推荐（song / playlist 模式）」与「歌单（热门 / 排行榜 / 我的）」两组；
  - 平台 segmented pill tabs 从左侧 aside 迁移到右侧主区域顶部，让「网易云 / QQ 音乐」与下方推荐 / 歌单内容直接对齐；
  - 主区域改为 flex column 布局：顶部固定平台切换栏，下方 panel 容器自身 `overflow-y-auto`，避免 sticky body 被外层撑出；
  - 进入页面默认落在该平台的第一个推荐项；当 URL 上带 `?q=` 时主区域强制渲染 `SearchPanel`，平台切换栏自动隐藏（搜索本身是跨平台聚合）；
  - 用户点击左侧 nav 时若仍带着 `?q=` 会被 `router.replace` 清掉，回到普通模式。

完整功能清单：
- 应用级访问密码：首次默认 `musichub`，登录后可在「设置 → 安全」修改；后端 API 同步校验会话 token
- 多平台（网易云 + QQ 音乐）扫码登录 + Cookie 导入；登录后顶部 Header 实时展示账号头像、昵称、VIP
- 关键词搜索 / URL 导入 / 单曲 / 歌单 / 专辑 — 可批量勾选 / 整体下载
- 异步任务系统（3 路 worker + WebSocket 实时进度推送）
- 跨平台去重（标准化 + 时长 ±5s 容忍）
- 高音质优先 + 自动降级 + ID3/FLAC 标签 + 嵌入封面 + LRC 旁存
- 用户配置目录布局（`<歌手>/<歌曲>` 或 `<歌手>/<专辑>/<歌曲>`）+ 文件名规则
- 订阅自动同步（APScheduler）+ M3U8 播放列表自动生成
- 在线试听 + 本地试听（Range 断点续传）+ 底部播放器
- 本地库浏览（多维度筛选）+ 统计面板

## 最近修复 / 改动（2026-05）

- **QQ 平台实现迁移到 `qqmusic-api-python` 0.5.x**：
  - `backend/app/platforms/qq/client.py` 已从手写 `httpx` 调用改为官方风格库适配器，统一走 `Client/Login/Search/Song/Songlist/Album/Singer/Recommend/Top/User/Lyric` 模块。
  - 新增 `backend/app/platforms/qq/credential.py` 与 `backend/app/platforms/qq/mappers.py`，把项目 cookie 持久化结构与库的 `Credential` 双向映射，并把库模型映射到项目统一 `Platform` dataclass。
  - 鉴权路由 `POST /api/auth/qr/qq` 支持 `type=mobile`（QQ 音乐 APP 扫码），同时保留 `qq / wx` 两种方式；`check_login` 增加 `refresh_credential` 兜底，降低凭证误判过期概率。
- **QQ 登录后正确显示昵称、VIP**：`_fetch_user_profile` 主路径改为
  `c.y.qq.com/rsc/fcgi-bin/fcg_get_profile_homepage.fcg`（cookie 透传后稳定返回
  `data.creator.nick / headpic`），`musicu vipinfo` 作为 VIP 兜底。
- **QQ 下载漏封面修复**：歌曲解析兼容更多接口的字段命名
  （`album.mid / albumMID / albummid`），缺 album_mid 时降级用主歌手
  `T001R500x500M000<singerMid>.jpg`，下载阶段还会用 `get_song` 详情接口再拉一次
  完整封面 URL，确保所有 QQ 歌曲都能写入封面。
- **登录后顶部 Header 显示账号头像**：
  - 后端 `Account` 表新增 `avatar_url`，QQ 兜底到 `q.qlogo.cn` 头像 CDN，
    网易云从 `nuser/account/get` 的 `profile.avatarUrl` 提取。
  - 前端新增 `useAccountsStore` Pinia store + `HeaderAccountChip`，
    Header 实时展示头像 + 平台 icon + 昵称 + VIP 状态，下拉里列出所有已登录账号。
- **目录布局简化**：
  - 移除「语种顶层」目录、移除「语种分类」配置 / API / 数据表 / 数据库列。
  - 新版可选布局：
    - 简化：`<歌手>/<歌曲>.flac`
    - 完整（推荐）：`<歌手>/<专辑>/<歌曲>.flac`
  - 已下载的旧文件保留原路径不会迁移，新下载按新布局保存。

## 十三、本地开发快速启动

**推荐（仓库根目录，自动带 `PYTHONPATH`、释放 5173、只热重载 `backend/app`）：**

```bash
cd <仓库根目录>
chmod +x scripts/run-backend.sh   # 仅需一次
./scripts/run-backend.sh
```

进程假死或端口被占时，直接再执行一次 `./scripts/run-backend.sh` 即可先杀再起。

若怀疑 **热重载 / 文件监视** 导致异常，可关 reload：

```bash
RELOAD=0 ./scripts/run-backend.sh
```

自检：`curl -m 5 http://127.0.0.1:5173/api/health`

```bash
# 后端（备选：在 backend 子目录）
cd backend
PYTHONPATH=. CONFIG_DIR=../.local_dev/config MUSIC_DIR=../.local_dev/music \
  uvicorn app.main:app --host 127.0.0.1 --port 5173 --reload --reload-dir app
```

若本机没有安装 `uv` / 全局 `uvicorn`，可在仓库根用 `.venv`（**勿漏 `PYTHONPATH=backend`**）：

```bash
cd <仓库根目录>
CONFIG_DIR=./config MUSIC_DIR=./music PYTHONPATH=backend \
  .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 5173 --reload --reload-dir backend/app
```

**常见故障**：在根目录执行 `uvicorn` 但**未**设置 `PYTHONPATH=backend` 时，进程会立刻退出，表现为「启动不了 / 像卡住」；请用上面的 `run-backend.sh` 或显式导出 `PYTHONPATH`。

```bash
# 前端
cd frontend
npm install
npm run dev   # http://127.0.0.1:5174，代理后端 5173
```

本地开发打开 `http://127.0.0.1:5174`，到「设置 → 账号管理」扫码登录，到「发现」搜索并点下载。

## 十四、Docker 部署

仅使用 Docker Hub 镜像（推荐，与根目录 **`docker-compose.yml`** 一致）：

```bash
docker compose pull && docker compose up -d
# 访问 http://localhost:5173
```

克隆仓库后从源码本地构建镜像：`docker build -t eianz/musichub:latest .`，再 **`docker compose up -d`** 会使用本地该标签（与 compose 中镜像名一致）。


数据卷：
- `/music`：下载的音乐文件（按目录布局保存）
- `/config`：SQLite 数据库 + 应用配置
