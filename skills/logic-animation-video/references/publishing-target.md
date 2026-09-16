# 仓库集成位置

- 仓库：https://github.com/defidehathorn389-max/narration-video-skill
- Skill 目录：skills/logic-animation-video/
- 入口：SKILL.md
- 集成方式：新增独立 Skill，不替换仓库原有视频流程。

## 使用

在本 Skill 目录中安装 requirements.txt，再依次运行逻辑检查、分镜预览和渲染脚本。详见 README.md。父仓库默认忽略 WAV，本目录用局部 .gitignore 显式保留 8 段源旁白；生成的音频中间文件仍被忽略。

更新通过独立功能分支和 PR 进行，不强推，不自动覆盖原有内容。认证信息不进入 Git 文件、远程 URL 或本 Skill 的素材。

references/validation-record.md 记录早期打包时的检查状态；远程是否已合并，以 GitHub 分支和 PR 状态为准。
