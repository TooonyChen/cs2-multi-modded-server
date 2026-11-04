# CS2 Multi Modded Server

一个 Docker Compose 项目运行 **1 个 updater + N 个 CS2 服务器**。游戏、插件二进制和材质共享一份安装，每服保留独立配置、插件数据、日志和端口。基于 [Kus 的 CS2 Modded Server](https://github.com/kus/cs2-modded-server)；[上游归属和模组清单](docs/UPSTREAM.md)，源码遵循 [LGPL-3.0](LICENSE)。

## 快速开始

需要 Linux amd64、Docker Engine 和 Docker Compose v2.24+，本地 Linux 文件系统、足够的 CS2 安装磁盘空间，以及 Steam 网络访问。默认公开镜像为 `ghcr.io/tooonychen/cs2-multi-modded-server:0.1.0`，无需编译或 GHCR 登录。

```sh
git clone https://github.com/TooonyChen/cs2-multi-modded-server.git
cd cs2-multi-modded-server
mkdir -p private data/shared data/instances/server1 data/instances/server2 data/instances/server3
for n in 1 2 3; do cp runtime/server.env.example private/server$n.env; done
# 编辑 private/serverN.env：每服独立 GSLT（STEAM_ACCOUNT）和强 RCON_PASSWORD
# 按需编辑 compose.yaml 的 MAP / EXEC 等设置
docker compose up -d
docker compose logs -f updater
```

首次启动由 updater 下载完整 CS2，再启动 server1 / server2 / server3。镜像提供运行环境和 SteamCMD；下载的游戏内容仍受 Valve/Steam 条款约束。默认宿主机端口为 27015 / 27016 / 27017（UDP 游戏、TCP RCON）；请用防火墙限制 RCON 的访问。

**默认 `force` 自动更新会中断对局**：updater 先停止所有游戏进程，取得独占锁，再更新共享安装，成功后恢复。可选 `UPDATE_POLICY=empty docker compose up -d`：仅在所有配置实例最近均确认 0 位真人时开始更新；离线、超时或未知状态均延期。检查周期默认 300 秒，可通过 `CHECK_INTERVAL` 修改。

## 配置与日常操作

- `compose.yaml`：唯一默认部署入口。增加第 N 服时复制 server3 service，修改 INSTANCE_ID、env_file、宿主机端口和实例目录，并将 ID 加入 updater 的 INSTANCE_IDS。
- `private/serverN.env`：各服凭据，禁止提交。`data/shared/` 是私有中央资源 overlay；`data/instances/serverN/` 是各服独立数据。这些目录均被 Git 和镜像构建排除。
- `game/csgo/`：保留的公共模组资源，updater 只读挂载后应用到共享安装。配置默认值仅首次复制到实例；已有私有配置不会被更新覆盖。
- 每服首次准备完成后，可直接编辑 `data/instances/serverN/cfg/`、`addons/`、`logs/`。运行文件归 UID/GID 10001 所有，宿主机编辑需相应权限。

```sh
docker compose ps
docker compose logs -f server1
docker compose stop             # 停止项目，保留数据
# 升级运行环境镜像（默认仍固定为 0.1.0）
docker compose pull
docker compose up -d
```

用 `CS2_IMAGE=ghcr.io/tooonychen/cs2-multi-modded-server:<版本>` 或 `@sha256:<digest>` 选择其他发布版本。共享游戏和协调状态默认位于 `cs2-multi_game` / `cs2-multi_control` 本地 Docker volumes。不要对实际数据运行 `down --volumes`。

## 开发与运维文档

- [架构、更新失败恢复和配置所有权](docs/OPERATIONS.md)
- [导入已有服和私有资源](docs/MIGRATION.md)
- [构建、测试及目录说明](docs/DEVELOPMENT.md)
- [实际验证及边界](docs/VALIDATION.md)

自动化验证覆盖离线进程夹具和真实容器协调；完整 CS2 下载、真人加入、插件兼容性和模式面板交互仍需隔离环境验收。迁移与生产切换需另外执行。
