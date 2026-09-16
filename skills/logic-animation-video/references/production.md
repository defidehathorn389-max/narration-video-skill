# 工具链与制作操作

## 工具职责

- `generate_image`：生成角色姿态或独立道具 PNG。
- `add_voice` / `generate_speech`：试听注册、分段合成旁白。跨会话要重新确认可用音色。
- Python / Pillow：确定性画面、中文文字、图层与动态路径。
- OpenCV：读取视频、提取参考关键帧、辅助抠图。
- NumPy：时间模型、音效、音频数据。
- `imageio_ffmpeg`：提供 FFmpeg 可执行路径。
- `present_file`：打开最终 MP4。不要只打开分镜图。

若环境没有这些特定工具，可用等价工具，但保持真实选声、实际生成资产、可下载成片等交付要求。

## 参考视频获取

以真实 HTTP 状态、Content-Type、文件头和解码结果为准。网页工具可能失败而直接下载成功，也可能页面显示文件名却无法获取媒体。不能从加载页推断已观看内容。对临时签名 URL 不做长期依赖；用户允许获取时，保存文件到工作目录。

本包没有包含参考视频，也没有保存其临时下载链接。

## FFmpeg 不在 PATH 时

原环境直接运行 `ffprobe` / `ffmpeg` 返回命令不存在，改为：

```python
import imageio_ffmpeg
ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
```

时长和分辨率可先用 OpenCV / wave 读取。更严格的音视频流检查通过 FFmpeg 输出完成。不要每次都要求安装系统级软件。

## 渲染结构

```text
当前时间 t
  ├─ 查找旁白场景与局部进度 u
  ├─ 推导逻辑状态（燃烧分钟、火线坐标）
  ├─ 绘制背景与生成图片图层
  ├─ 绘制当前道具与动作
  ├─ 绘制因果反馈、时钟、时间轴
  └─ 按同一时间 t 烧录字幕
```

Pillow 帧以 RGB24 管道送入 FFmpeg，不保存数千张全尺寸帧。案例关键参数：

```text
-f rawvideo -pix_fmt rgb24 -s 1920x1080 -r 30 -i -
-i audio/narration-effects.wav
-c:v libx264 -preset fast -crf 19 -pix_fmt yuv420p
-c:a aac -b:a 160k -movflags +faststart -shortest
```

`-shortest` 不替代尾音处理。必须先让音频与计划帧时长接近，预留自然片尾。

## 文件布局

```text
SKILL.md
README.md
requirements.txt
references/
scripts/
examples/rope-45/
  character.png
  thinker.png
  narration.json
  audio/01.wav ... 08.wav
deliverables/               # 成片，默认不提交
```

脚本通过自身路径定位项目，不依赖 `/home/user` 之类工作区绝对路径。中文字体用环境变量或 Linux 默认路径。不要把原会话 workspace 路径当用户机器路径。

## 已遇到的绘制坑

1. **生长动画半径过小**：圆弧 inset 大于圆半径，会出现 `x1 must be greater than or equal to x0`。小于最低绘制半径时跳过细节。
2. **零长度填充条**：右端坐标减去边距后可能小于左端坐标。只在宽度足够时绘制，或钳制坐标。
3. **道具遮住标签**：水果/火焰上升后可能压到箱号或公式。查看运动终点与中间点，而不仅是初始帧。
4. **封面泄露答案**：选择框循环停在正确选项会泄题。封面单独关闭提示高亮。
5. **生成图片角色不一致**：优先编辑参考图，不把明显不同角色视作同一人。
6. **低分辨率假高清**：本例坐标、字体、路径以 1.5 倍直接绘制；草稿模式只用于预览。
7. **音频字数不能代替时长**：同样字数不同声音时长差别明显，必须测量。
8. **执行工具超时**：离线渲染可用较长的一次性命令；需要跨调用存活的任务用进程工具。避免手写轮询或启动后不管理进程。

## 性能与可重复性

- 缓存字体与人物尺寸，不在每帧重复加载文件。
- 只缓存合理数量的姿态/缩放，避免内存无限增加。
- 音效随机数固定种子。
- --check 先检查关键帧；--draft 生成小尺寸；最终再出 1080p。
- 日志写到输出目录，出现编码失败要检查退出码而非只看文件存在。
