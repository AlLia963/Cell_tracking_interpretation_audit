# 采用任务、计算成本与完整性责任补证

本轮只补缺失的任务成本与责任证据，不重做已完成的全量科学实验。协议保存后才执行测量。研究例子来自既有 D47，事后选择已经披露，不增加生物学样本。

固定任务：从 D47 的 reference/prediction 原始 NPZ，在 7 µm、原有缩放与 calculated-float64-distance 精确二进制和目标下，判断帧 50/51/52 的 reference path 156000000073→157000000073→158000000073 是否允许 joint pair recovery=1。

比较四种回答：canonical 单图、独立边投影、完整共享图穷举、已有 certified projection。前两者不承担完整共同可实现性保证。后两者获得相同原始坐标、边、gate 和目标，不预设优劣。

新增测量为三个独立新进程的仪器重复，不是新实验样本。分别记录输入读取、全片 canonical match（保留原前端实际实现开销）、三个完整 frame family 的构造、有限集合 factor certificate、直接原始 gated partial-injection 穷举基线、两种查询、witness verification、序列化，以及进程高水位 working set。只比较同一任务；不由毫秒小样本推断普遍提速。

直接基线独立遍历每个原始 gate 内候选与 unmatched，拒绝非 injective，按最大基数/最小 exact integer sum 保留全部最优 map；在输出冻结前不读已有 family 答案。原有 producer family 与该穷举集合逐 frame 全量比较。查询结果与原 D47 只在计算完后对比。

完整性责任探针：删去中间一个合法最优 map，展示单纯 supplied-family schema/membership 可以通过且错误缩窄单边 visibility；原始候选的独立穷举可识别缺失。另验证不存在的 witness index 和过小 query cap 必须拒绝。此为软件前提测试，不是新自然缺陷。

复用既有 27 constructed cases/54 comparisons 的阶段耗时、11760 witness replays、1216 additional completed reports 和 cap/negative controls。只读取现存统计文件，不重新运行该 cohort。报告 construction 和 query 分开；RSS 为整个新进程的峰值，包含解释器/依赖，不解释为算法独占内存。

没有快于普通 constrained baseline 的成立条件也保留结果。采用价值限定为交付明确输入、可检查完整性证据、共享查询、witness/refusal 的同一任务接口，不以代码包装替代科学创新，不推断人类工作量或修复准确率。
