# fuck-u-code 自动工作流说明

本仓库通过 GitHub Actions 接入 `fuck-u-code`，用于自动生成代码质量分析报告，并由 `github-actions[bot]` 接管 `assets/FuckUCodeScore.svg` 的分数更新。

## 工作流触发方式

- 向 `main` 发起 Pull Request 时自动运行。
- `main` 分支收到 push 时自动运行。
- 每周自动运行一次。
- 也可以在 GitHub Actions 页面手动运行。

## Bot 接管评分徽章

工作流会先执行：

```bash
npx -y -p eff-u-code fuck-u-code analyze .
```

然后读取 `reports/fuck-u-code-report.md`，由 `scripts/update_fuck_u_code_score.py` 提取分数并重新生成两份 SVG：

```text
assets/FuckUCodeScore.svg
astrbot_plugin_volcengine_asr/assets/FuckUCodeScore.svg
```

在 `main` push、定时任务或手动触发时，如果 SVG 分数发生变化，工作流会用 `github-actions[bot]` 自动提交：

```text
chore: update fuck-u-code score badge
```

Pull Request 事件只生成报告和 artifact，不会向分支写回 SVG，避免外部 PR 或审查分支产生意外提交。

## 安全边界

- 工作流使用 `contents: write` 权限，目的是允许 `github-actions[bot]` 在 `main` 上写回分数 SVG。
- PR 事件不会执行写回步骤。
- 分析步骤设置了 `continue-on-error: true`，报告工具异常时不会阻断正常提交。
- 报告仍只作为 GitHub Actions job summary 和 artifact 输出，不提交回仓库。
- bot 只提交两份 `FuckUCodeScore.svg`，不改插件主逻辑。

## 分析范围

仓库根目录的 `.fuckucoderc.json` 会排除以下内容：

- Git、缓存和临时目录。
- 已打包的 zip 文件。
- 内置 `ffmpeg` 二进制文件。
- 第三方 license 目录。
- 本地 release 草稿 JSON。

这样可以避免报告被打包产物、二进制文件和临时文件干扰。

## 查看报告

每次运行后可以在 GitHub Actions 的 job summary 中直接查看报告，也可以下载 `fuck-u-code-report` artifact。

## 手动刷新

需要立即刷新分数时，在 GitHub Actions 页面手动运行 `fuck-u-code` workflow 即可。正常情况下不需要人工编辑 SVG 里的数字。
