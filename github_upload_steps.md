# GitHub 上传步骤

本地文件已整理，尚未替你创建、连接或发布远端仓库。建议仓库名：`hlstrack2026_47433`。上传整个文件夹的内容，而不是只上传整理 ZIP；GitHub 不会自动把一个 ZIP 展开成源码。

## 方法一：PowerShell 与 Git

电脑已具备 Git 时采用此方法。先在文件资源管理器打开仓库文件夹，在地址栏输入 powershell 后回车。确认能看到 readme.md、src、sim、build、board、data、skill、report。

先检查：

```powershell
python build/verify_repository.py
```

在 GitHub 网站登录自己的账号，点右上角 + → New repository。Name 填 hlstrack2026_47433，选择 Public。不要再次勾选初始化 README、gitignore 或 license，因为本地已经有这些文件。点击 Create repository。

回到 PowerShell。下面两项必须换成自己的 GitHub 用户名和 GitHub Settings → Emails 中显示的 noreply 地址；使用仓库局部配置，不改变其他项目：

```powershell
git init -b main
git config --local user.name 'your_github_username'
git config --local user.email 'your_github_noreply_email'
git add .
git status --short
git commit -m 'Add FPGA motion spectrum project'
git remote add origin https://github.com/your_github_username/hlstrack2026_47433.git
git push -u origin main
```

首次推送可能打开浏览器授权。按 Git 的登录窗口完成，不要把密码或 token 写入命令、配置文件、README 或聊天记录。若仓库已经初始化过，跳过 init；若 origin 已存在，先运行 git remote -v 核对，不盲目重复添加或强制推送。

如果推送提示远端存在新提交，先确认是不是在网站创建了 README。不要直接使用 --force；保留本地文件，检查远端内容后再合并。

## 方法二：GitHub Desktop

安装并登录 GitHub Desktop。在仓库文件夹执行一次 git init -b main 后，用 File → Add local repository 选择当前文件夹。核对 Changes 列表，填写提交说明并 Commit to main。点击 Publish repository，Name 使用 hlstrack2026_47433，取消 Keep this code private，再点击 Publish repository。

如使用隐私邮箱，发布前在 Git 设置中选择自己的 noreply 邮箱。不要保留示例用户名或邮箱。

## 上传后核对

1. 首页能渲染 readme.md，能点开 report/design_report.pdf 和 skill/readme.md。
2. 能看到 src、sim、build、board、data、skill、report 七个目录，而不是只有一个 ZIP。
3. build/work、虚拟环境、Vivado 中间工程、日志中的本机信息和凭据没有进入仓库。
4. 仓库为 Public，license.txt 可见，来源与许可说明完整。
5. 用新的本地目录 git clone 一次，按 readme.md 运行电脑检查。
6. 将网站显示的实际仓库 URL 填入赛事系统。只有完成此步骤，才算真正公开到 GitHub。

## 大文件

GitHub 浏览器单文件限制为 25 MiB，普通 Git 单文件超过 100 MiB 会被拒绝。本仓库把原始数组无损分组压缩，现有各单文件均小于 25 MiB；无需为了本批文件启用 Git LFS。文件较多，推荐 Git 或 GitHub Desktop，而不是分批网页拖拽。

压缩的原始证据位于 data/evidence，索引含原始哈希。board/packages 中的独立运行包需要保留，但不应再把外部整仓 ZIP 拷入仓库形成重复备份。视频录制、签署授权书和个人照片按赛事系统单独处理，不把签名和身份资料放到公开源码中。

## 官方参考

- [通过 GitHub Desktop 添加已有项目](https://docs.github.com/en/desktop/adding-and-cloning-repositories/adding-an-existing-project-to-github-using-github-desktop)
- [GitHub 大文件说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
- [设置提交邮箱](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address)
