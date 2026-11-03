# CS2 多实例共享安装

Fork of [kus/cs2-modded-server](https://github.com/kus/cs2-modded-server), retaining its LGPL-3.0 license and original history. Original instructions: [README.upstream.md](README.upstream.md).

一个 Docker Compose 项目同时管理更新 sidecar 和任意数量的 CS2 实例。示例提供 server1 / server2 / server3，游戏、插件二进制和材质只有一份共享安装；每服独立配置、插件数据、日志和端口。**默认 force 自动更新会中断正在进行的对局**：先停止所有实例的游戏进程，等待独占锁，再更新共享安装，成功后恢复。没有 Docker socket 挂载，也不需要 privileged / SYS_ADMIN。

```sh
mkdir -p multi/private data/shared data/instances/server{1,2,3}
for n in 1 2 3; do cp multi/server.env.example multi/private/server$n.env; done
# 编辑各服私有 env，设置各自的 GSLT 和强 RCON_PASSWORD
# 编辑 multi/compose.yaml 中各服 MAP / EXEC 等配置
# 首次启动会下载完整 CS2，需要足够磁盘空间与 Steam 网络访问
docker compose -f multi/compose.yaml up -d --build
docker compose -f multi/compose.yaml logs -f updater
```

可选空服更新：`UPDATE_POLICY=empty docker compose -f multi/compose.yaml up -d`。只有 INSTANCE_IDS 列出的全部实例最近均确认 0 位真人才开始；离线、超时、解析失败或未知状态均延期。检查周期默认 300 秒，可用 CHECK_INTERVAL 修改。首次安装无需等待还未启动的实例。

增加第 N 个服：复制 server3 的 service，修改 INSTANCE_ID、env_file、宿主机端口和独立宿主机目录，并将新 ID 加入 updater 的 INSTANCE_IDS。复用 x-server anchor 即可；每个容器内仍使用 27015，宿主机端口必须不同。无需按服复制游戏安装或建立第二个 Compose 项目。

- [架构、更新失败恢复和配置所有权](multi/README.md)
- [导入现有服、已有模式和私有资源](multi/MIGRATION.md)
- [实际验证及边界](multi/VALIDATION.md)

本仓库交付不修改生产服；自动化测试使用离线进程夹具，未声称真人加入、模式面板交互或 CS2 实战已验证。
