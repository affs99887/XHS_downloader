# 下载日志、重试与图片筛选

更新代码后运行一次 `Setup.bat` 安装新增的 CPU 推理依赖。日常仍双击 `Downloader.bat`。

## 失败日志与重试

小红书、抖音和微博的每次下载都会产生独立日志：

```text
log/<平台>/<日期时间_批次编号>/
  run.log                     运行日志和错误原因
  events.jsonl                下载成功、失败、重试事件
  failed_downloads.json        尚未成功的任务及重试参数
  summary.json                批次结果和图片分类计数
  image_classification.jsonl  每张图片的判断、原路径和分类后的路径
```

下载失败时继续处理其余任务，整批结束后显示 `是否重试这 N 个失败项？[y/N]`。
输入 `y` 重试失败项；直接回车保留清单。再次失败会在本轮结束后继续询问。
小红书图集中一张失败不会阻止其他图片下载，全部媒体成功后才写入笔记完成记录。
重试会跳过已保存的媒体；原文件不会被下载到一半的文件替换。

关闭窗口后也能使用失败清单重试，替换下面的清单路径即可：

```powershell
.\Downloader.bat xhs --likes --retry-failed "log\xhs\某次批次\failed_downloads.json"
.\Downloader.bat douyin --retry-failed "log\douyin\某次批次\failed_downloads.json"
.\Downloader.bat weibo --retry-failed "log\weibo\某次批次\failed_downloads.json"
```

小红书单条笔记的清单可省略 `--likes`。喜欢列表清单使用 `--likes`，支持恢复列表分页失败。
从清单重试会保存新的批次日志；成功项会从新批次的失败清单中移除。
无有效笔记 ID 等无法重试的数据异常会保留原因，但不提供无效的重试操作。

`--no-retry` 可关闭询问。标准输入不是终端时自动保留清单，不等待输入，适合脚本调用。
仍有下载失败或图片筛选错误时返回非零退出码。

## 默认筛选：人物且能看到腿部

所有下载入口默认使用 `--image-filter legs`。媒体下载及用户选择的重试结束后，才开始筛选本批涉及的图片。

- 符合规则：保留在原目录。
- 不符合规则：移入对应下载目录下的 `弃用/`。
- 模型判断不确定：移入 `待复核/`。
- 图片损坏、模型下载失败等识别错误：保留原文件并记录错误。

分类保留相对目录结构，同名文件会增加编号，已有文件不会被覆盖。视频不参与图片分类。
腿部通过同一条腿上相邻关节的位置、可见度和画面边界判定；局部腿部、遮脸等姿态模型漏检场景由图像语义模型补充。
关节检测与语义判断均可能出错，可在分类报告中查看原因和实际采用的模型。

## 黑丝袜识别：可选实验模式

菜单选择 **5 → 2** 后，后续下载及已有图片筛选使用黑丝袜实验模式。命令行示例：

```powershell
.\Downloader.bat xhs --likes --limit 20 --image-filter stockings
.\Downloader.bat douyin "图集或主页分享文字" --image-filter stockings
.\Downloader.bat weibo "微博UID" --days 30 --image-filter stockings
```

这个模式使用本地服饰专用的 [Marqo FashionSigLIP](https://huggingface.co/Marqo/marqo-fashionSigLIP)，
对比黑丝袜、黑色长裤、运动打底裤、白丝袜、肤色丝袜、光腿等类别。
它能用于辅助筛选，但没有针对用户图片做过标注训练，不能提供经过验证的准确率。
黑丝袜和肤色丝袜、阴影、厚打底裤等接近的判断会进入 `待复核/`。
报告里的余弦相似度和分差用于排序，不是“有黑丝的概率”。

本次只读样图实验比较了通用 CLIP 与服饰模型。通用模型对黑丝袜和肤色丝袜的分差较小；
服饰模型在已人工查看的黑丝袜与白丝袜样图上有可用区分，但部分色调仍然接近。
这只能证明程序能实际运行和产生有用候选，不能作为独立准确率评测。
默认规则继续使用人物和腿部；需要更严格的黑丝筛选时再选择实验模式。

## 筛选已有文件夹

菜单选择 **4**，或执行：

```powershell
.\Downloader.bat filter "D:\图片文件夹"
.\Downloader.bat filter "D:\图片文件夹" --image-filter stockings --preview
```

`--preview` 只生成报告，不移动图片。去掉它后实际分类。
程序跳过已经在 `弃用/`、`待复核/` 内的图片；若要重新判断这些图片，可先按报告原路径恢复。

其他模式：`--image-filter person` 只筛人物；`--image-filter off` 关闭图片分类。

## 模型与部署

图片分析在本机 CPU 上运行，不上传下载图片，不需要 API Key 或显卡。
模型首次使用时联网下载到 `.runtime/models/image_filter/`，按固定版本的 SHA-256 校验后加载：

| 用途 | 来源 | 大小 |
| --- | --- | --- |
| 人物和姿态 | [OpenCV Zoo MediaPipe](https://github.com/opencv/opencv_zoo) | 合计约 17 MB |
| 局部人物和腿部语义补充 | [CLIP ViT-B/32 的 ONNX 转换](https://huggingface.co/Xenova/clip-vit-base-patch32) | 约 89 MB |
| 黑丝袜实验 | Marqo FashionSigLIP ONNX | 约 94 MB |

可提前准备模型：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\setup_image_filter.py --stockings
```

`Doctor.bat` 离线检查推理依赖及随源码提供的文本向量，不自动下载模型。
文本向量固定对应模型版本，普通运行无需文本编码模型或分词库。
开发者重新生成向量时，可单独安装 `tokenizers==0.23.3`，运行
`scripts/build_clothing_embeddings.py`（通用模型）以及带 `--fashion` 的版本（服饰模型）。
