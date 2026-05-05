# fuck-u-code 自动工作流说明

本仓库通过 GitHub Actions 接入 `fuck-u-code`，用于自动生成代码质量分析报告。

## 工作流触发方式

- 向 `main` 发起 Pull Request 时自动运行。
- `main` 分支收到 push 时自动运行。
- 每周自动运行一次。
- 也可以在 GitHub Actions 页面手动运行。

## 安全边界

- 工作流只使用 `contents: read` 权限，不能向仓库写入代码。
- 分析步骤设置了 `continue-on-error: true`，报告工具异常时不会阻断正常提交。
- 输出只写入 GitHub Actions 临时工作区里的 `reports/fuck-u-code-report.md`，不会提交回仓库。
- 当前接入只改动工作流、配置和说明文件，不改插件主逻辑。

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
