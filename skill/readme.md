# PYNQ Overlay 部署、DMA 验证与结果复核

本工具包把硬件文件配对、AXI DMA 传输、参考比对和失败恢复整理为可配置流程。通用部分不依赖运动频谱、ROI 或某个固定算法；Sobel 相关控制只放在适配器中。

## 适用范围

- PYNQ 框架下的 AXI DMA 简单模式。
- 具备 MM2S 与 S2MM 的配套 Overlay，可声明输入/输出形状及 dtype。
- 已验证设备为 PYNQ-Z2；已验证任务为独立 DMA 直通和 Sobel 图像处理。
- 未验证 scatter-gather、其他 DMA 控制器或跨板卡直接复用比特流。

## 文件

| 路径 | 用途 |
|---|---|
| scripts/pynq_tools.py | 通用元数据检查、DMA 传输、超时/错误处理与数组比对 |
| scripts/check_examples.py | 配置正例与缺文件、缺 IP、长度超限、超时配置等负例检查 |
| scripts/run_sobel_adapter.py | 作品专用寄存器启动和 ROI 适配器入口 |
| examples/loopback.json | 独立直通配置，不依赖 Sobel 或频谱 |
| examples/award_sobel.json | 当前作品配置 |
| hardware | 配套直通 bit、hwh 和原始构建清单 |
| runtime | 已板测旧布局的配套脚本和配置，由构建入口在工作目录恢复 |
| troubleshooting.md | 按症状组织的排查顺序、失败条件和恢复方式 |

## 电脑端检查

从仓库根目录执行：

```powershell
python skill/scripts/pynq_tools.py check skill/examples/loopback.json
python skill/scripts/pynq_tools.py check skill/examples/award_sobel.json
python skill/scripts/check_examples.py
```

此时不下载 Overlay。程序解析 HWH，核对 DMA/IP、简单模式、传输大小和清单哈希；输出中的 `board_test=NOT_RUN` 是正确标注，不代表已执行了硬件。

## 板端独立直通

仅在 PYNQ 上运行，会加载直通 Overlay，替换当前 PL 设计：

```sh
python3 skill/scripts/pynq_tools.py loopback skill/examples/loopback.json --output build/work/loopback_test
```

正常结果为 4096 个 uint32 值完全一致，mismatches=0。输入、实际输出和结果 JSON 写入指定新目录。目录已经存在时拒绝覆盖。

## 板端 Sobel 适配

```sh
python3 skill/scripts/run_sobel_adapter.py --output build/work/sobel_skill_test
```

适配器只添加阈值、ROI、启动脉冲和完成状态检查，实际传输复用同一个 DmaRunner。三幅图像的幅值/边缘打包输出和 ROI 统计应全部一致。执行后显示保持黑屏。

## 改成自己的任务

复制一个配置，修改 bitfile、manifest、dma_ip、必要 IP、输入/输出 shape、dtype 和 timeout_s。路径相对于配置文件；字节数按 shape×dtype.itemsize 计算，不能把元素个数当成 DMA 字节长度。需确保硬件实际发出的 TLAST、数据位宽、TKEEP、长度和驱动契约一致。

先在电脑运行 check，再在板卡执行 transfer。算法需要控制寄存器时，提供 start/ready 适配器，不把算法寄存器写死在通用传输类中。跨板卡需要重新构建对应 bit/hwh，不可只改文件名。

## 失败条件与输出

缺文件、缺 IP、哈希不一致、非简单模式、非法 shape、超出 DMA 长度上限和非法超时都明确失败。结果比对支持精确值或数值容差，会记录差异数、首个差异位置与最大绝对误差。非有限值不作为有效测量。

运行中 DMA 错误或超时会记录 TX/RX 状态，并尝试复位。只有确认 DMA 停止访问内存后才释放缓冲区。复位不能完成时保留缓冲并报告失败，需要人工确认板卡状态后恢复。

## 验证依据与提炼过程

两类实际板测结果在 `board/results/skill_loopback_final/result.json` 与 `board/results/skill_sobel_final/result.json`。前者精确比对 4096 个值；后者三帧共 49152 个打包像素且 ROI 正确。配置负例和超时/错误恢复负例由电脑端测试验证，其中 DMA 故障负例使用模拟设备，不写成真实板卡故障实验。

工具来自几类开发观察：bit/hwh 文件配对错误需要在加载前发现；DMA 长度应从实际数组字节数推导；接收缓存写入哨兵后必须 flush；超时需要保存状态并按顺序复位；只有比较硬件输出与黄金参考才能确认正确。相关提示词、回答和纠错记录见 `report/llm_collaboration.md`。

原始直通构建清单中的 NOT_RUN 是构建时状态，后续板测证据单独保存，未回写或篡改原记录。本工具不是另一个大模型，也不要求训练模型。
