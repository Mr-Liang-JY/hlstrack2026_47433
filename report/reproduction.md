# 复现步骤

## 1. 确认版本和硬件

板卡为 PYNQ-Z2，器件为 xc7z020clg400-1。HDMI 使用 OUT 接口，当前信号是 720p60。算法输入为 128×128，预编译硬件不支持通过更改 Python 数组大小直接切换算法分辨率。

电脑依赖见根目录 requirements.txt。板卡依赖由 PYNQ 3.0.1 镜像提供。数据来源、原视频哈希、ROI 和裁剪参数位于 `data/input/source.json`。

## 2. 不上板的完整检查

从仓库根目录执行：

```powershell
python build/reproduce.py check
python build/reproduce.py verify-evidence
python build/reproduce.py recheck --run final_gc_release
python skill/scripts/check_examples.py
```

第一条自动创建 `build/work/runtime`。其内的 `rtl`、`python`、`scripts` 和 `out` 是已验证程序所需布局。硬件与软件源文件不会因为仓库分层而改变；字体和厂商板卡目录仅在这个被忽略的目录恢复原名。

应得到 13 项软件测试通过。最终板测恢复检查应得到 151 帧、4,947,968 个幅值/边缘像素值、零像素差异和零 ROI/质心差异。这里只重新计算和核对历史板测数据，不等同于本次重新执行了 PL。

## 3. 从源码构建硬件

```powershell
python build/reproduce.py simulate --vivado 'D:/Xilinx/Vivado/2024.2/bin/vivado.bat'
python build/reproduce.py hardware --vivado 'D:/Xilinx/Vivado/2024.2/bin/vivado.bat'
```

仿真必须得到六条测试通过。实现后的时序报告必须没有负 setup/hold 路径，DRC Error 必须为零。导出程序以源码快照核对当前 RTL 和 XDC，生成同一轮构建的 bit、hwh 和 manifest。

脚本通过 `AWARD_PYTHON` 传递当前 Python，并用隔离模式 `-I` 调用清单导出程序，避免 Vivado 注入的 PYTHONHOME/PYTHONPATH 造成标准库版本冲突。

新生成的比特流可能因工具、时间戳或实现选择而与预编译哈希不同。应使用新生成的完整配套文件重新验证，不能只替换 bit 或跳过哈希检查。

## 4. 用预编译版本上板

解压 `board/packages/award_video_runtime.zip`。该包与此前在独立板卡目录实测的文件逐字节一致。其 SHA-256 为 `ea3a16d0f8f076a62d171335cf0487da94dbf06e1d9aef31829adcafd7cd79be`。

Notebook 第 1 格检查文件，第 2 格执行完整处理与播放，第 3 格请求停止并黑屏。处理进度打印在 Notebook 输出中；默认先完成离线处理再显示，期间保持黑屏。播放完三遍后自动黑屏。不要将灯亮或加载成功作为功能正确性的唯一证据。

正式版本在每帧 PL 运算后检查像素幅值、边缘和 ROI 统计。任何不一致都会明确失败，不会偷偷切换成软件结果继续显示。

## 5. 修改后运行

在电脑修改 `src/rtl` 或 `src/constraints` 后重新执行 hardware。对 Vivado 工程结构的修改应在新的工作目录重新创建工程。修改 PS 程序后，prepare 会同步源码；prepare 不会把新构建的硬件覆盖回旧预编译版本。

完整仓库在板卡可执行：

```sh
python3 board/run_demo.py --loops 3 --decoder opencv
python3 board/black_screen.py
```

也可以导出新的板端 ZIP：

```powershell
python build/reproduce.py export-board --output build/work/award_video_board.zip
```

运行输出在 `build/work/runtime/results`，不纳入 Git。若要形成新的赛事证据，另存原始输入、运行命令、源码/硬件哈希、CSV、原始数组和失败结果，不能覆盖当前参考数据。

## 6. 恢复任一历史原始数组

`data/evidence/index.json` 给出档案、成员、原始字节数和 SHA-256。下面命令恢复噪声频谱组：

```powershell
python build/reproduce.py restore --run board_noise_spectral
python build/reproduce.py recheck --run board_noise_spectral
```

并非每个历史目录都包含完整视频缓存。`recheck` 用于索引中具备完整输入、输出和缓存的运行。黑屏联动目录复用了处理缓存，不代表又执行了一次 151 帧算法测试，其 `test_scope` 已注明。

## 7. 当前已验证范围

实测仅覆盖 PYNQ-Z2。通用 DMA 工具在 Sobel 和独立直通两类 Overlay 上验证过；迁移到另一块板卡必须重新构建硬件和核对接口。电脑端测试、仿真、板端处理、HDMI 握手与显示器观感是不同证据，不互相替代。
