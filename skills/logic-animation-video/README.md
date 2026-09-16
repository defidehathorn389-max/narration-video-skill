# 中文逻辑谜题动画 Skill

把思维谜题制作成约两分钟的 **16:9、1080p 中文配音 MP4**，沿用灰底、黑白手绘人物、黄色重点道具的二维解谜画风。

## 从这里开始

- Agent 使用说明：[`SKILL.md`](SKILL.md)
- 用户确认偏好：[`references/user-preferences.md`](references/user-preferences.md)
- 完整案例：[`references/rope-case-study.md`](references/rope-case-study.md)

## 本地复现

需要 Python 3.10+、可用中文字体。建议在隔离环境安装：

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
pip install -r requirements.txt
python scripts/check_rope_logic.py
python scripts/render_rope_demo.py --check
python scripts/render_rope_demo.py --draft
python scripts/render_rope_demo.py
python scripts/validate_video.py deliverables/rope-45-1080p.mp4 --expected-seconds 122 --full-hd
```

Windows 可以使用 `.venv\Scripts\activate`。字体默认读取 Linux 上的 Noto Sans CJK；其他系统通过环境变量提供字体：

```bash
export CHINESE_FONT=/path/to/Chinese-Regular.ttf
export CHINESE_FONT_BOLD=/path/to/Chinese-Bold.ttf
```

`imageio-ffmpeg` 提供 FFmpeg 可执行文件，通常无需系统额外安装 `ffmpeg`。首次安装依赖需要网络；安装完成后，示例使用随包图片和配音，可离线渲染。

## 输出

- `deliverables/rope-45-1080p.mp4`：约 122 秒、1920×1080、30 fps。
- `deliverables/rope-45-draft.mp4`：960×540、15 fps 草稿。
- `examples/rope-45/两根绳子_横版封面.jpg`：封面。
- `examples/rope-45/两根绳子_字幕.srt`：字幕。
- `examples/rope-45/checks/`：检查帧。

逐帧渲染是 CPU 任务，速度取决于机器。脚本打印进度。`--check` 仅生成音频中间文件与分镜，不渲染全片。

## 在 Agent 中安装

将本目录整体放入目标 Agent 支持的 Skill 目录；入口为带 YAML frontmatter 的 `SKILL.md`。仓库布局可采用 `skills/logic-animation-video/`，也可以将本包作为独立仓库。具体路径以所用 Agent 的约定为准。

## 文件来源与凭据

示例图片和音频为本项目生成资产；代码和文档为本项目制作。未附参考创作者的原视频、商标或片尾水印。代码与文档沿用仓库根目录的 MIT 许可证；生成图片和音频的使用、再分发仍需遵守相应生成服务条款。

**本包不包含 GitHub 令牌或其他密钥。** 不通过聊天传递新凭据；仓库发布应使用平台安全授权或已配置的本地 Git 凭据管理器。
