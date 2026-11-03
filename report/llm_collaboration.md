# 大模型协作与自我纠错

## 记录范围

`llm/transcript_redacted.jsonl` 来自本机四段项目会话，共 187 条去重后的用户与助手公开消息。保留原有 UTC 时间；本地时间为 UTC+8。每条记录带 record_id、session、role、phase 和公开文字。export_scope.json 说明导出与脱敏范围。

这不是包含工具、系统提示词和内部推理的完整原始转储。它是供参赛材料核对的公开对话记录，去除了本机路径、私网地址、图片和应用引用。早期回答反映当时阶段，不代表最终状态；最终能力以板测和验证文件为准。

## 分工与评价方式

用户提出题目方向、平台、显示设备、输入变更和学习需求；大模型参与软硬件划分、代码草拟/修改、测试设计及排错。工程脚本、仿真、参考比对和板测结果决定某个建议是否被保留。没有把模型建议本身当作测量数据，没有补写不存在的人工复测或假提交记录。

## 关键纠错索引

| 问题 | 当时判断或建议 | 观察后修正 | 记录与证据 |
|---|---|---|---|
| 摄像头没有稳定更新 | 试图从 DVP 摄像头实时输入 | 正式版本改为离线视频，摄像头仅列历史试验 | 对话 m0138–m0139；development_history.md |
| 帧缓存 LUT 超标 | 原始 RAM 读出选择不利于 BRAM 推断 | 两组独立同步读寄存器，之后再选择 | 对话 m0145；当前 axis_framebuffer.v |
| 阈值按亮度下调 | 预期适应暗场景 | 开发集中出现背景伪边缘，改用梯度可检出性与噪声统计后冻结 | adaptive_policy.py；frozen_policy.json |
| FFT 的贡献不清楚 | 只比较 fixed 与 spectral | 增加 time、spatial 与旧频谱组，保留无优势条件 | board_algorithm_scores.json；holdout 原始 CSV |
| 播放偶发长停顿 | 先排除显示缓存临时读盘 | RAM 预加载仍停顿，记录逐帧时序后调整有限播放段 GC | 对话 m0181–m0182；final_release 与 final_gc_release |
| 干净构建导出失败 | 外部 Python 受 Vivado 环境影响 | 加 -I 隔离环境，重新导出配套清单 | 对话 m0177；build/scripts/build_bitstream.tcl |
| 优化基线不够强 | 先与 NumPy 对照 | 补充优化 OpenCV、预热和交替运行顺序，报告约 1.09 倍而非只展示较大比值 | ps_final_comparison/summary.json |

对话 ID 对应 JSONL 的 record_id，未将上述表格中的归纳改写成虚假的原始提示词。可直接在记录中搜索相应编号核对。

## 提炼为 Skill

反复出现的配对、长度、缓存和超时问题被提炼为通用 PYNQ 工具。通用 DmaRunner 只处理声明的 AXI DMA 契约；Sobel 启动、ROI 和完成判定留给适配器。直通 Overlay 是第二场景，避免把换一段视频当成跨题目复用。

两类真实板测、元数据负例和模拟设备故障测试分别保存，不混淆证据层次。第二块板卡尚未验证。完整使用方法与失效条件在 skill/readme.md 和 skill/troubleshooting.md。
