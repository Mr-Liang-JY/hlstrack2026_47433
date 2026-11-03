# 测试输入与原始证据

`input/source.json` 记录公开视频来源、许可、裁剪、ROI、帧率元数据和原始 SHA-256。公开视频及其灰度派生帧遵循源页面标注的 CC BY-SA 4.0，自写代码的 MIT 许可不覆盖这些数据。

`input/prepared_frames.npz` 是 151 帧、128×128 的预处理输入。controlled_noise 与 controlled_weak 为可重复生成的合成矩形运动，包含已知几何轮廓、位置和 0.8 Hz 真值；它们不代表真实相机的测量精度。

`evidence/index.json` 描述 17 组原始数组档案。压缩为 NPZ 时只改变存储形式，不改变原始字节，恢复后按原始 SHA-256 校验。共保留 61 个原始数组文件，309069312 字节；JSON、CSV 和软件快照位于 `board/results`。

校验：`python build/reproduce.py verify-evidence`。恢复与比对：`python build/reproduce.py recheck --run final_gc_release`。数据正文里的早期路径已经脱敏，原始数值数组未改动。

`history` 保存早期采样与 FFT 实验。这里的历史信号不是当前真实视频的标注真值，不能混用来计算真实视频误差。
