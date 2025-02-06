# cherry-studio-sync-dav

使用本项目作为 Webdav 服务器，可以让你的 Cherry Studio 支持合并从多设备上传的备份，从而间接实现同步功能。**注意：和 KnowledgeBase 相关的合并功能暂时没有实现。**

### Usage

推荐使用 Docker Compose 部署，拷贝 `docker-compose.sample.yml` 到 `docker-compose.yml`，然后自行修改 Webdav 的用户名和密码即可。
