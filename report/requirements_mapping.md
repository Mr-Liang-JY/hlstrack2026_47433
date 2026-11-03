# 提交要求对照

| 指南内容 | 当前文件 | 状态 |
|---|---|---|
| 完整工程源码 | src、build/reproduce.py、src/constraints | 已整理；正式版本与历史试验区分 |
| 仿真与正确性 | sim/benches、sim/results、board/results | 已有测试与原始依据 |
| 综合、实现、资源和时序 | build/reports/optimized、build/reports/baseline、board/results/clean_rebuild | 已保留报告及比较口径 |
| 上板工程与结果 | board/overlay、board/packages、board/results | 有真实板测与独立部署证据 |
| 测试数据与参考 | data/input、data/evidence、data/history | 原始数组无损压缩并附 SHA-256 |
| 可复现构建 | build/reproduce.py、report/reproduction.md | 有具体入口和已验证版本 |
| 技能包及适用/失败条件 | skill/readme.md、examples、scripts、troubleshooting.md | 两类任务实测；跨板卡未验证 |
| 设计与优化报告 | report/design_report.md、design_report.pdf | 本轮整理 |
| 大模型协作记录 | report/llm_collaboration.md、report/llm | 187 条脱敏公开消息与纠错索引 |
| 开源许可 | license.txt、third_party.md、data/input/license_dejavu.txt | 自写代码 MIT，第三方各自许可 |
| 公共仓库 | github_upload_steps.md | 本轮只准备文件，由本人上传 |
| 演示视频 | 不生成占位假视频 | 按本轮要求暂不录制 |
| 实物照片和签名材料 | 不公开身份和签名 | 本人按赛事系统要求另行提交 |

文件名全部使用小写英文、数字、下划线或连字符；readme.md 作为指南 README 的入口。被 Git 忽略的构建工作目录允许恢复工具/旧运行时需要的原名，不作为公开源码命名。没有创建空的 hls 目录，因为当前实现使用 Verilog RTL 与 PS 软件。
