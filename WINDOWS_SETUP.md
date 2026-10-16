# Windows 安装与使用

适用：Windows 10 / 11，Intel / AMD 64 位电脑。需要联网；不支持用此安装器直接部署 Windows ARM64。

## 新电脑首次安装

1. 安装 Git，在准备存放项目的文件夹打开 PowerShell，执行：

   ```powershell
   git clone https://github.com/affs99887/XHS_downloader.git
   cd XHS_downloader
   ```

2. 双击项目根目录的 **`Setup.bat`**，等待出现 `Setup complete`。
3. 双击 **`Downloader.bat`**，选择小红书、抖音或微博，然后粘贴链接。

也可以下载仓库 ZIP，完整解压后双击 `Setup.bat`。不要在 ZIP 压缩包预览窗口内运行。

安装器会依次完成：

- 优先复用 Python 3.11 x64；缺失时从 python.org 下载 3.11.9 官方安装器，验证数字签名后安装到项目 `.runtime/python311/`。
- 创建项目自己的 `.venv`，按 `requirements-lock.txt` 安装固定版本依赖。
- 优先复用带有 npm 的 Node.js 22/24；否则从 nodejs.org 下载 Node.js 24.22.0，验证 SHA-256 后解压到 `.runtime/node/`。
- 使用 `package-lock.json` 安装 JavaScript 依赖，下载项目专用的 Chromium 到 `.runtime/browsers/`。
- 仅在文件不存在时创建 `.env`、`douyin_config.yml`、`weibo_config.json`，最后执行离线环境检查。

不会更改全局 PATH，不会切换电脑上其他项目的 Node 版本。安装缓存和临时文件也保存在项目 `.runtime/` 下，避免依赖其他 Windows 用户的缓存目录权限。重复运行不会清空 Cookie、配置或下载结果。下载和安装失败时会显示出错步骤并返回非零退出码，修复后重新运行即可。

需要 Git 之外的运行环境时，安装器会自动准备。首次下载浏览器可能较慢，过程中不要关闭窗口。项目应放在当前用户有写入权限的目录；不需要以管理员身份运行。

### 国内网络加速（可选）

安装器默认从 python.org、nodejs.org、PyPI、npm 官方源和 Playwright 官方下载点取文件，国内直连可能很慢或超时。安装器会原样沿用当前窗口的环境变量，所以可以先在 PowerShell 里指定国内镜像源，再从同一个窗口启动安装器。镜像源是把官方文件同步到国内的下载站点，内容和官方一致。

```powershell
$env:PIP_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple"
$env:npm_config_registry = "https://registry.npmmirror.com"
$env:PLAYWRIGHT_DOWNLOAD_HOST = "https://npmmirror.com/mirrors/playwright"
.\Setup.bat
```

三个变量分别决定 Python 依赖、JavaScript 依赖和 Chromium 浏览器从哪里下载。双击 `Setup.bat` 不会带上这些变量，必须在设好变量的同一个 PowerShell 窗口里运行。Python 和 Node 安装包本身没有镜像变量；这两步下载慢时，先手动安装官方 Python 3.11 x64 或 Node 22/24，安装器会直接复用，不再下载。

## 日常使用

推荐双击 `Downloader.bat` 使用中文菜单。命令行示例（在项目目录打开 PowerShell）：

```powershell
.\Downloader.bat xhs "小红书笔记链接或完整分享文字"
.\Downloader.bat xhs --likes --limit 20
.\Downloader.bat douyin "抖音作品、图集或主页链接"
.\Downloader.bat douyin --login
.\Downloader.bat weibo "微博数字UID或用户主页" --days 30
.\Downloader.bat weibo --set-cookie
```

微博作品链接如果带有 UID，仍然是按该用户的时间线批量抓取，并非只下载链接中的单条微博。默认最近 30 天；`m.weibo.cn/detail/...` 这类没有 UID 的作品链接不支持直接识别，请改用用户主页或数字 UID。

| 平台 | 登录方式 | 默认输出目录 |
| --- | --- | --- |
| 小红书 | 首次或登录过期后，在终端扫码 | `download_files/xhs/notes/`、`download_files/xhs/likes/`；单独双击 `Likes_downloader.bat` 时写到 `download_files/likes/` |
| 抖音 | 先尝试公开内容；受限时选择登录，打开浏览器后手动登录并回终端确认 | `download_files/douyin/` |
| 微博 | 公开内容可先尝试；受限时通过菜单设置网页 Cookie，输入不会回显 | `download_files/weibo/` |

下载器使用网站接口，账号权限、Cookie 时效和网站风控仍会影响下载结果。环境检查通过代表本机环境准备完成，不代表登录有效或所有链接都能成功下载。

## 更新与重新部署

在项目目录执行：

```powershell
git pull --ff-only
.\Setup.bat
```

更新后重跑安装器会同步锁定的依赖和浏览器版本。若修改过源码导致 Git 提示冲突，先保留自己的修改，再处理冲突；不要直接丢弃改动。

换电脑只需重新拉取代码并运行安装器。**不要复制旧电脑的 `.venv`、`.runtime` 或 `node_modules`。** 移动整个项目目录后也应重新运行 `Setup.bat`。

登录文件不进入 Git，新电脑需要重新登录。若要保留历史下载与去重记录，可自行复制整个 `download_files/`；抖音的根目录数据库 `dy_downloader.db` 也可一并迁移。小红书点赞的去重记录是输出目录下的 `downloaded_notes.jsonl` 和 `downloaded_note_ids.txt`，`Downloader.bat xhs --likes` 与 `Likes_downloader.bat` 输出目录不同、记录互不共享，两个入口都用过就两个目录都要复制。不要将 Cookie、数据库、下载内容提交到远程仓库。

## 环境检查与常见问题

双击 **`Doctor.bat`**。它会检查 Python、锁定依赖、Node 模块、小红书本地签名、三个平台模块导入、FFmpeg、Chromium 离线启动以及目录写入权限。检查不登录账号、不访问平台接口、不下载媒体，也不输出 Cookie。

自动化调用可使用：

```powershell
.\Setup.bat -NoPause
.\Doctor.bat --no-pause
```

| 提示或现象 | 处理方式 |
| --- | --- |
| Python / Node / 模块缺失 | 重新运行 `Setup.bat`，不要只在全局环境安装依赖 |
| `Doctor.bat` 提示 `DLL load failed`，导入 cv2 失败 | 系统缺少微软 Visual C++ 2015-2022 运行库 x64 版，这是很多 Windows 程序共用的一组系统文件，opencv-python 不自带。从微软官网 <https://aka.ms/vs/17/release/vc_redist.x64.exe> 安装后重跑 `Doctor.bat` |
| `.venv` 不兼容或来自旧电脑 | 关闭项目运行进程，将 `.venv` 重命名为 `.venv.old`，再运行安装器；保留配置和下载目录 |
| 下载依赖或 Chromium 超时 | 检查网络或公司代理后重试；国内网络可按上文「国内网络加速」设置镜像源后重跑。安装器沿用系统的代理环境变量，不内置本机代理地址 |
| Python 数字签名、Node 校验失败 | 停止执行该下载文件，检查系统时间、证书与网络后重试；不要跳过校验 |
| 安装器被安全软件阻止 | 查看被阻止的具体文件；可先自行安装官方 Python 3.11 x64、Node 22/24，再运行安装器 |
| 小红书登录失败 | 关闭下载器，清空本地 `.env` 的 `COOKIES` 值后重新扫码；勿把 Cookie 贴进公开日志 |
| 抖音打开浏览器失败 | 运行 `Doctor.bat`，再重跑安装器安装项目专用 Chromium |
| 微博没有下载或访问受限 | 确认 UID、时间范围和网页 Cookie；检查终端平台返回的信息 |

## Docker（可选）

Windows 桌面使用优先选择上述安装器。Docker 镜像安装同一份 Python 依赖、Node 模块、Chromium 和 Linux 浏览器依赖，使用统一下载入口。

```powershell
docker build -t xhs-downloader .
docker run --rm -it --init --shm-size=1g --mount "type=bind,source=$($PWD.Path)\download_files,target=/app/download_files" xhs-downloader
```

运行前在宿主机创建 `download_files` 目录。需要小红书已有登录态时，在运行参数中增加 `--env-file .env`；该文件应由自己在本机创建。镜像构建会排除 Cookie、数据库、下载结果、本地运行环境和 Git 元数据。

普通 Docker 容器没有桌面显示服务，**不能直接使用抖音默认的弹窗登录流程**。需要该流程时使用 Windows 安装器。已有登录态的自动化任务应单独挂载自己的抖音配置，并将其中 `browser_fallback.headless` 设为 `true`。容器内临时创建的配置和登录信息不会自动保留到宿主机。

Docker 配置与 Windows 安装验证应分开看待：只有实际构建和运行成功才能确认目标机器的 Docker 环境可用。
