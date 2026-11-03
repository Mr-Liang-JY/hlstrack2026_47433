# 来源与许可

## 自写代码

当前 RTL、PS 驱动、测试、构建入口、通用校验工具和文档按根目录 license.txt 的 MIT 条款提供。许可不覆盖下述第三方数据、字体及 AMD 工具生成物，不以 MIT 重新授权它们。保留原有项目贡献者署名，不写入个人身份和学校信息。

## 视频与派生数据

- 发布者：Open Educational Resources / Open Source Physics @ Singapore。
- [来源页面](https://www.sg.iwant2study.org/ospsg/index.php/interactive-resources/physics/02-newtonian-mechanics/09-oscillations/225-tracker-modeling-in-spring-mass-system)
- [原视频](https://iwant2study.org/lookangejss/02_newtonianmechanics_8oscillations/trz/springmass/videos/Spring%20and%20mass.mp4)
- 源页面标注 CC BY-SA 4.0：[许可](https://creativecommons.org/licenses/by-sa/4.0/)。
- 修改：裁剪、缩放到 128×128、灰度、Gaussian 3×3、边缘处理及显示叠加。原视频与其派生图像/数据按适用的 CC BY-SA 4.0 处理，不能只按代码的 MIT 条款再发布。
- 原始哈希和处理参数见 data/input/source.json。源视频没有独立频率真值标定。

## 字体

DejaVu Sans 字体存为 data/input/dejavu_sans.ttf，字节与原 DejaVuSans.ttf 一致；完整字体许可保存在 data/input/license_dejavu.txt。构建兼容目录恢复旧字体名。字体只用于已生成的字形 ROM和电脑参考渲染。

## 板卡与引脚资料

PYNQ-Z2 板卡定义保留 TUL 厂商信息；来源为 [Xilinx/PYNQ v3.0.1](https://github.com/Xilinx/PYNQ/tree/v3.0.1/boards/Pynq-Z2)。上游 BSD-3-Clause 许可文本存为 build/board_files/license_pynq.txt。仓库将版本目录规范为 a_0，文件内容不变；工作目录恢复为 A.0。

HDMI、按钮和 LED 引脚参考 [官方 base.xdc](https://raw.githubusercontent.com/Xilinx/PYNQ/v3.0.1/boards/Pynq-Z2/base/vivado/constraints/base.xdc)，上游 Copyright (C) 2022 Xilinx, Inc. 的 BSD-3-Clause 注释保留在 XDC 中。

## 工具与器件库

Processing System、Clocking Wizard、AXI DMA、GPIO、Interconnect 等为 Vivado 生成的 AMD IP；OSERDESE2、OBUFDS 以及 UNISIM 为对应器件原语/仿真库。它们受各自工具/IP 许可约束。本仓库提供必要构建脚本和预编译硬件，不公开 Vivado 安装目录、生成 IP 缓存或厂商工具源码。

[OSERDESE2 原语说明](https://docs.amd.com/r/2022.2-English/ug953-vivado-7series-libraries/OSERDESE2)；[PYNQ DMA 文档](https://pynq.readthedocs.io/en/v3.0.1/pynq_libraries/dma.html)。

## 摄像头历史试验

src/history/camera_trial 只保留自写的数字接口试验。厂家原始教学 PDF、嵌套压缩包、初始化寄存器表和未经确认许可的参考实现未收入本仓库。没有把摄像头试验描述为当前已完成的实时功能。

## 会话记录

report/llm 中为本项目相关公开消息的脱敏整理，保留协作角色、阶段性错误与修正。未公开系统指令、内部推理、账户凭据、私网地址和附件图片。原始对话中的外部公开参考链接保留其来源含义，不视为本项目作者身份。
