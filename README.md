<p align="center">
  <a href="https://github.com/cv-cat/Spider_XHS" target="_blank">
    <picture>
      <img width="220" src="./author/logo.jpg" alt="Spider_XHS logo">
    </picture>
  </a>
</p>

<div align="center">

# Spider_XHS

**专业的小红书数据采集 & 全域运营解决方案 & Agent Skills**

[![Skills](https://img.shields.io/badge/skills-supported-success)](https://github.com/cv-cat/XhsSkills)
[![Python](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/nodejs-22%2F24-green)](https://nodejs.org/)
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

</div>

## Windows 新电脑使用

首次拉取后双击 **`Setup.bat`**，看到 `Setup complete` 后双击 **`Downloader.bat`**。
安装器自动准备 Python 3.11 x64、Node 22/24、锁定依赖及项目专用 Chromium；缺少兼容运行环境时自动下载，不更改全局 PATH。
支持 Windows 10/11 x64。更新代码后重跑安装器，已有 Cookie、配置和下载结果会保留。

完整步骤、登录方式、命令示例、换电脑迁移和故障处理见 [Windows 安装与使用](WINDOWS_SETUP.md)。
环境异常时双击 `Doctor.bat` 做离线检查。不要复制旧电脑的 `.venv`、`.runtime` 或 `node_modules`。

下载器现已支持批次日志、结束后询问失败重试，以及自动筛选“人物且有可见腿部”的图片。
菜单中可切换黑丝袜实验模式；不符合的图片移入“弃用”，不确定的进入“待复核”。
重试清单、已有图片筛选和模型准备方法见 [下载日志与图片筛选](IMAGE_FILTERING.md)。

---

> **在 AI 大模型爆发的时代，内容运营的竞争本质是效率竞争。**
> 本项目封装了小红书平台完整的数据采集与内容发布能力，为开发者构建 AI 运营智能体提供可靠、稳定的底层 API 支撑。

**⚠️ 本项目仅供学习交流使用，禁止任何商业化行为，如有违反，后果自负**

---

## 为什么需要这个项目？

```
采集竞品笔记 ──► [Spider_XHS] ──► 你的 AI Agent（改写 / 生成 / 分析）──► 自动上传发布
                     ▲                                                        │
                     └──────────── 获取数据 / 管理账号 ◄──────────────────────┘
```

小红书没有开放完整的内容运营接口。想要接入 AI 大模型实现内容批量采集、智能改写、一键发布，首先需要能**稳定读写平台数据**。Spider_XHS 解决的正是这个前置问题：

- 逆向还原了小红书 PC 端与创作者平台的签名算法（a1 / web_id / websectiga / sec_poison_id / gid / x-s / x-t / x-s-common / x-b3-traceid / x-xray-traceid / x-rap-param / search_id / request_id / sign / q-signature 等参数）
- 封装全部核心 HTTP 接口，签名参数已透明处理
- 同时覆盖 **数据采集**（PC端）、**内容发布**（创作者平台）、**KOL数据**（蒲公英）三大场景

**你负责接 AI 大脑，我们负责打通小红书的神经。**

---

## 成品

### repo地址： [XHS_ALL_IN_ONE](https://github.com/cv-cat/XHS_ALL_IN_ONE)

### 账号矩阵 — 多账号绑定与健康管理

支持绑定多个 PC / Creator 账号，扫码登录、手机验证码、Cookie 导入三种方式。Cookie 加密存储，2 小时自动健康巡检，过期自动通知。

<img src="https://github.com/cv-cat/XHS_ALL_IN_ONE/blob/master/static/frontend_1.jpg" width="600" />

### 素材优化 — AI 图片润色

选择草稿中的任意图片，添加参考图，输入润色指令，AI 生成优化后的图片并原位替换。当前素材和优化结果并排对比，点击即可放大预览。

<img src="https://github.com/cv-cat/XHS_ALL_IN_ONE/blob/master/static/frontend_5.jpg" width="600" />

### 发布中心 — 一键发布到小红书

预览草稿内容和图片素材，选择 Creator 账号，设置可见性和发布模式（立即/定时），发布校验通过后一键发布到小红书创作者平台。

<img src="https://github.com/cv-cat/XHS_ALL_IN_ONE/blob/master/static/frontend_6.jpg" width="600" />

---

## 🧩 Skills 支持

当前项目已经支持基于 skills 的能力接入，既可以直接作为 `Spider_XHS` 的底层能力仓库使用，也可以通过标准化 skills 方式被上层 Agent 工具链引入。

如果你希望直接复用已经封装好的 skills，可以查看 [XhsSkills](https://github.com/cv-cat/XhsSkills)。该仓库专门用于存放基于 `Spider_XHS` 封装的 Agent Skills，目前可被 `Clawbot`、`Claude Code`、`Codex` 等支持 skills 的工具直接引入与集成。

---

## ⭐ 已实现功能

| 模块 | 功能 | 状态 |
|------|------|------|
| **小红书 PC 端** | 二维码登录 / 手机验证码登录 | ✅ |
| | 获取主页所有频道 & 推荐笔记 | ✅ |
| | 获取用户主页信息 / 自己的账号信息 | ✅ |
| | 获取用户发布 / 喜欢 / 收藏的所有笔记 | ✅ |
| | 获取笔记详细内容（无水印图片 & 视频） | ✅ |
| | 搜索笔记 & 搜索用户 | ✅ |
| | 获取笔记评论 | ✅ |
| | 获取未读消息 / 评论@提醒 / 点赞收藏 / 新增关注 | ✅ |
| **创作者平台** | 二维码登录 / 手机验证码登录 | ✅ |
| | 上传图集作品 | ✅ |
| | 上传视频作品 | ✅ |
| | 查看已发布作品列表 | ✅ |
| **蒲公英平台** | 获取 KOL 博主列表 & 详细数据 | ✅ |
| | 获取博主粉丝画像 & 历史趋势 | ✅ |
| | 发起合作邀请 | ✅ |
| **千帆平台** | 获取分销商列表 & 详细数据 | ✅ |
| | 获取分销商合作品类 / 店铺 / 商品信息 | ✅ |

---

## 🤖 接入 AI 智能体

Spider_XHS 天然适合作为 AI 运营 Agent 的数据底座，以下是几种典型用法：

### 场景一：竞品笔记采集 + AI 改写 + 自动发布

```python
from apis.xhs_pc_apis import XHS_Apis
from apis.xhs_creator_apis import XHS_Creator_Apis

pc_api = XHS_Apis()
creator_api = XHS_Creator_Apis()

# 1. 采集竞品笔记
success, msg, note = pc_api.get_note_info(note_url, cookies_str)

# 2. 交给 AI 改写（接入任意大模型）
rewritten = your_ai_agent(note['content'])   # GPT / Claude / Qwen / 本地模型

# 3. 自动上传到创作者平台
creator_api.post_note({
    "title": rewritten['title'],
    "desc": rewritten['desc'],
    "media_type": "image",
    "images": [...],
    ...
}, creator_cookies_str)
```

### 场景二：关键词监控 + AI 情报分析

```python
# 搜索指定关键词的最新笔记，交给 AI 分析趋势
success, msg, notes = pc_api.search_some_note(query, require_num, cookies_str, ...)
analysis = your_ai_agent(notes)
```

### 场景三：KOL 筛选 + 智能匹配

```python
from apis.xhs_pugongying_apis import PuGongYingAPI

pgy = PuGongYingAPI()
# 获取目标类目的 KOL 数据，交给 AI 评估匹配度
kol_list = pgy.get_some_user(num=50, cookies=cookies)
best_kols = your_ai_agent(kol_list, brand_profile)
```

---

## 🎨 爬虫效果图

### 处理后的所有用户
![image](https://github.com/cv-cat/Spider_XHS/assets/94289429/00902dbd-4da1-45bc-90bb-19f5856a04ad)

### 某个用户所有的笔记
![image](https://github.com/cv-cat/Spider_XHS/assets/94289429/880884e8-4a1d-4dc1-a4dc-e168dd0e9896)

### 某个笔记具体的内容
![image](https://github.com/cv-cat/Spider_XHS/assets/94289429/d17f3f4e-cd44-4d3a-b9f6-d880da626cc8)

### 保存的 Excel
![image](https://github.com/user-attachments/assets/707f20ed-be27-4482-89b3-a5863bc360e7)

---

## 🛠️ 快速开始

### ⛳ 环境要求与安装

Windows 用户运行 `Setup.bat` 即可完成安装，详见 [Windows 安装与使用](WINDOWS_SETUP.md)。
运行基线为 Python 3.11 x64、Node.js 22/24；Python 固定版本依赖保存在 `requirements-lock.txt`，JavaScript 固定版本依赖保存在 `package-lock.json`。
开发者手动安装时应在新建的虚拟环境中安装锁文件，并执行 `python -m playwright install chromium`。

### 🎨 登录配置

默认不需要手动复制 Cookie。首次运行入口时，如果项目根目录 `.env` 不存在或没有 `COOKIES`，程序会自动调用 PC 端二维码登录：

```bash
Downloader.bat xhs --likes --limit 20
```

命令行中出现二维码后，使用小红书 App 扫码确认登录。登录成功后，cookies 会自动写入 `.env`，后续抓取 / 下载流程会继续执行。

喜欢列表下载入口同样支持自动扫码：

```bash
Likes_downloader.bat
```

如果你已经有可用 Cookie，也可以手动预置 `.env`：

```env
COOKIES='your_cookie_here'
```

> Cookie 有时效性，失效后删除 `.env` 中的 `COOKIES` 或置空，重新运行入口即可扫码更新。

### 🚀 三个平台统一入口（推荐）

Windows 下只需要记住一个文件：

```bat
Downloader.bat
```

双击它会显示中文菜单，先选小红书、抖音或微博，再粘贴分享内容。入口会自动调用
对应下载器，三个平台的登录信息与输出目录互相隔离。

也可以用一行命令直接下载：

```bat
Downloader.bat xhs "小红书笔记链接或完整分享文字"
Downloader.bat xhs --likes --limit 20
Downloader.bat douyin "抖音链接或完整分享口令"
Downloader.bat douyin --login
Downloader.bat weibo "微博UID、用户主页或带UID的作品链接" --days 30
Downloader.bat weibo --set-cookie
```

统一输出位置：

| 平台 | 默认内容 | 输出目录 |
|------|----------|----------|
| 小红书 | 单条笔记 | `download_files/xhs/notes/` |
| 小红书 | 当前账号喜欢列表 | `download_files/xhs/likes/` |
| 抖音 | 视频、图集等 | `download_files/douyin/` |
| 微博 | 指定用户最近 30 天的图片、视频、Live Photo | `download_files/weibo/` |

小红书未登录或 Cookie 过期时会自动显示二维码；抖音公开内容可以先直接尝试，受限
时从菜单选择“登录或更新抖音 Cookie”；微博公开内容可以先不带 Cookie，受限时再
配置 `weibo_cookie.txt`。

原始开发示例仍可运行：

```bash
python -m spider.spider
```

### 🎵 抖音无水印下载

项目已内置 `jiji262/douyin-downloader`，支持抖音公开视频、图集、合集、主页作品、
音乐、直播及热榜/搜索等能力。上游源码隔离在 `vendor/douyin_downloader`，不会与
现有小红书接口和 Cookie 混用。

首次安装依赖后，再安装浏览器组件：

```bash
python -m pip install -r requirements-lock.txt
python -m playwright install chromium
```

下载单个视频、图集或分享口令：

```bash
python -m spider.douyin_downloader -u "https://v.douyin.com/xxxx/"
python -m spider.douyin_downloader -u "复制打开抖音…… https://v.douyin.com/xxxx/"
```

Windows 也可以直接运行：

```bat
Douyin_downloader.bat -u "https://www.douyin.com/video/作品ID"
```

抖音当前风控较严格，建议首次使用先执行登录；部分公开作品也可以直接下载：

```bash
python -m spider.douyin_downloader login
```

登录成功后，Cookie 会写入本地 `douyin_config.yml` 和 `douyin_cookies.json`；
这两个文件均已加入 `.gitignore`。首次运行会根据
`douyin_config.example.yml` 自动生成本地配置，默认输出目录为
`download_files/douyin/`。

查看全部上游参数：

```bash
python -m spider.douyin_downloader --help
```

当前合入的上游版本、提交号和许可证记录在
`vendor/douyin_downloader/UPSTREAM.md`。

### 🧣 微博图片 / 视频下载

项目已直接内置 `dataabc/weibo-crawler`，按微博用户 ID 批量抓取主页微博，并下载
原图、视频和 Live Photo。上游源码隔离在 `vendor/weibo_crawler`，运行配置保存在
项目根目录，不会与小红书、抖音 Cookie 混用。

首次运行会根据 `weibo_config.example.json` 自动创建本地
`weibo_config.json`。直接指定一个或多个用户 ID：

```bash
python -m spider.weibo_downloader -u "1669879400"
python -m spider.weibo_downloader -u "用户ID一" -u "用户ID二" --since-date 30
```

Windows 也可以直接运行：

```bat
Weibo_downloader.bat -u "1669879400"
```

默认抓取最近 30 天，下载原创和转发微博中的图片、视频及 Live Photo，结果写入
`download_files/weibo/`。也可以编辑 `weibo_config.json`，在
`user_id_list` 中长期维护多个用户 ID。

公开微博可尝试不带 Cookie 抓取；遇到访问限制、可见范围不足或验证码时，在
`weibo_config.json` 的 `cookie` 字段填写微博网页 Cookie，或设置
`WEIBO_COOKIE` 环境变量。Cookie 文件也受支持，例如：

```json
{
  "cookie": "weibo_cookie.txt"
}
```

入口同时保留了上游 Flask API：

```bash
python -m spider.weibo_downloader --serve --port 5000
```

该上游的定位是“按用户 ID 抓取主页时间线”。统一入口可以从常见用户主页或
`weibo.com/数字UID/作品ID` 链接中自动提取 UID，但实际仍会按该用户的时间线批量
抓取，并不是只下载链接中的单条微博。当前合入的提交号和许可证状态记录在
`vendor/weibo_crawler/UPSTREAM.md`；该上游在本次合入的提交中未提供许可证，
对外分发或商用前应先取得上游作者授权。

### 🐳 Docker 部署（可选）

```bash
docker build -t xhs-downloader .
docker run --rm -it --init --shm-size=1g xhs-downloader
```

默认运行三平台统一入口。数据持久化、Cookie 配置及无桌面容器的抖音登录限制见
[Windows 使用说明中的 Docker 章节](WINDOWS_SETUP.md#docker可选)。
构建会排除本机 Cookie、配置、下载文件和虚拟环境。

---

## 📁 项目结构

```
Spider_XHS/
├── spider/
│   ├── __init__.py
│   └── spider.py                    # 主入口：爬虫调用示例
├── apis/
│   ├── xhs_pc_apis.py               # 小红书PC端完整API（采集）
│   ├── xhs_creator_apis.py          # 创作者平台API（上传发布）
│   ├── xhs_pc_login_apis.py         # PC端登录（二维码/手机验证码）
│   ├── xhs_creator_login_apis.py    # 创作者平台登录
│   ├── xhs_pugongying_apis.py       # 蒲公英平台API（KOL数据）
│   └── xhs_qianfan_apis.py          # 千帆平台API（分销商数据）
├── xhs_utils/
│   ├── common_util.py               # 初始化工具（读取.env / 自动登录）
│   ├── cookie_util.py               # Cookie解析
│   ├── data_util.py                 # 数据处理（Excel保存、媒体下载）
│   ├── xhs_util.py                  # PC端签名算法封装
│   ├── xhs_creator_util.py          # 创作者平台签名算法封装
│   ├── xhs_pugongying_util.py       # 蒲公英平台工具
│   └── xhs_qianfan_util.py          # 千帆平台工具
├── static/
│   ├── xhs_main_260411.js           # PC端签名核心JS（最新版）
│   ├── xhs_rap.js                   # PC端 x-rap-param JSVMP 补环境生成脚本
│   ├── xhs_creator_260411.js        # 创作者平台签名核心JS（最新版）
│   └── ...
├── Setup.bat                        # Windows 一键安装
├── Doctor.bat                       # 离线环境检查
├── Downloader.bat                   # 三平台统一入口
├── WINDOWS_SETUP.md                 # Windows 部署与使用说明
├── .env.example                     # 空白 Cookie 模板；真实 .env 不进入 Git
├── requirements.txt
├── Dockerfile
└── package.json
```

---

## 🗝️ 注意事项

- `spider/spider.py` 是爬虫入口，可根据需求修改调用逻辑
- `apis/xhs_pc_apis.py` 包含所有 PC 端数据接口
- `apis/xhs_creator_apis.py` 包含创作者平台发布接口
- Cookie 有时效性，失效后需重新获取
- 建议配合代理（proxies 参数）使用，降低封号风险

---

## 🍥 更新日志

| 日期 | 说明 |
|------|------|
| 23/08/09 | 首次提交 |
| 23/09/13 | API 更改 params 增加两个字段，修复图片无法下载，修复部分页面无法访问报错 |
| 23/09/16 | 修复较大视频编码问题，加入异常处理 |
| 23/09/18 | 代码重构，加入失败重试 |
| 23/09/19 | 新增下载搜索结果功能 |
| 23/10/05 | 新增跳过已下载功能，获取更详细的笔记和用户信息 |
| 23/10/08 | 上传至 PyPI，可通过 pip install 安装 |
| 23/10/17 | 搜索下载新增排序方式（综合 / 热门 / 最新） |
| 23/10/21 | 新增图形化界面，上传至 release v2.1.0 |
| 23/10/28 | Fix Bug：修复搜索功能隐藏问题 |
| 25/03/18 | 更新 API，修复部分问题 |
| 25/06/07 | 更新 search 接口，区分视频和图集下载，新增创作者平台 API |
| 25/07/15 | 更新 xs version56 & 小红书创作者接口 |
| 26/04/11 | 重构创作者平台 API（图集 / 视频上传），新增蒲公英 KOL 数据 API，新增千帆分销商 API，签名算法升级至最新版 |
| 26/04/28 | 更新 PC 端搜索与笔记详情风控参数，新增 `search_id` 当前算法与 `x-rap-param` 本地 JSVMP 生成，补充 `a1`、`web_id`、`websectiga` 等签名参数说明 |

---

## 🧸 额外说明

1. 感谢 Star ⭐ 和 Follow，项目会持续更新
2. 作者联系方式在主页，有问题随时联系
3. 欢迎 PR 和 Issue，也欢迎关注作者其他项目
4. 如果此项目对您有帮助，欢迎请作者喝一杯奶茶 ~~（开心一整天 😊）

<div align="center">
  <img src="./author/wx_pay.png" width="380px" alt="微信赞赏码">
  <img src="./author/zfb_pay.jpg" width="380px" alt="支付宝收款码">
</div>

---

## 📈 Star 趋势

<a href="https://www.star-history.com/#cv-cat/Spider_XHS&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=cv-cat/Spider_XHS&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=cv-cat/Spider_XHS&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=cv-cat/Spider_XHS&type=Date" />
  </picture>
</a>

---

## 🍔 交流群

如果你对爬虫和 AI Agent 感兴趣，请加作者主页 wx 通过邀请加入群聊

ps: 请加群4、17、18，人满或者过期 issue | wx 提醒

| group14 | group17 | group18 |
|:--:|:--:|:--:|
| <img width="280" alt="group14" src="https://github.com/user-attachments/assets/4ff4e202-7fc2-42f7-910a-e12d55456bd1" /> | <img width="280" alt="group17" src="https://github.com/user-attachments/assets/6406398d-a4c7-4b08-a92c-496ea10a4440" /> | <img width="280" alt="group18" src="https://github.com/user-attachments/assets/57f6a18c-d9d0-4343-b2eb-c32e1e991115" /> |





