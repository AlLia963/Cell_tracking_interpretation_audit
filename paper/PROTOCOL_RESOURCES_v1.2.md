# 本轮证据任务：四份意见驱动，旧科学实验不重跑

冻结于执行前。原四份审稿已完整文本阅读；10-08第三份明确看过前两份，不能计为第三个独立盲审。

1. 从既有D43冻结输入网格按参数取对角三例：n32/k2/v2、n64/k4/v3、n128/k8/v5；不按结果选择。仅补测此前缺少的分阶段成本/进程峰值，不重新生成输入或重复模型推理。两种原有对应约定、whole-frame和certified-projection表示，各3个独立进程重复。construction包括canonical matching与完整frame families；factor、dependency、query、witness extension/replay、serialization分别记录。Windows PeakWorkingSet为进程累计高水位，不能称某阶段专属内存。历史D43全27例54比较直接复用，不把三例当新的泛化实验或证实独有速度优势。
2. 对D47原始固定图仅执行新的交付路径与责任探针：实际调用supplied-family API测试合法省略及非法schema；真实CLI重建后使用显式witness重放入口测试合法、越界、错误值及破坏的family成员。缺少family覆盖证明时可以认证已见证的值，不能拒绝未见值为全域不可实现。原v1.1坏见证测试只是Python索引异常，原schema-pass常量没有API调用，必须更正证据级别。
3. 交付candidate从原git tracked源文件复制，增加显式输入task/replay入口与README，版本/源码manifest冻结；不带原竞赛数组、不推GitHub。实际数据验证只在LOCAL ONLY目录，输入/旧repo不改。
4. 正文减少重复、补loss附近的对应选择解释、CCA全称及A别名、实际report schema；将确定性、完整性与拒绝责任准确写入Algorithm1、方法、SI及SourceData。不得据此宣称新的TP收益、真人效率、算法优于同信息基线或自动Accept。
