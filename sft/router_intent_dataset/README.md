# Router Intent Dataset

这是一份给 `Badminton Coach` 路由层做 SFT 的单任务数据集。

目录说明：

- `generate_dataset.py`: 可复现的数据生成脚本
- `train.json`: 训练集，300 条
- `validation.json`: 验证集，60 条
- `test.json`: 测试集，60 条

数据格式：

- `instruction`: 固定任务描述模板之一
- `input`: 用户原始输入
- `output`: 模型应输出的标准 JSON 字符串

`instruction` 只使用 3 个等价模板轮换：

1. `请根据用户输入输出标准 JSON，只返回 JSON，不要解释。`
2. `你是羽毛球教练 Agent 的结构化意图分类器。请识别意图并返回 JSON。`
3. `这是一个路由分类任务。请基于用户输入返回结构化 JSON 结果。`

这样做的原因：

- 不让 `instruction` 完全一样，降低对单一前缀的过拟合
- 又不把任务描述放得过散，避免在小数据集里引入无意义噪声

标签 schema 与当前项目代码对齐：

- `primary_intent`: `prematch | postmatch | health | fallback`
- `secondary_intents`: 复合意图列表
- `slots`: 当前消息里可直接抽到的少量关键信息
- `missing_slots`: 当前还缺哪些关键槽位
- `risk_level`: `low | medium | high`
- `confidence`: 0 到 1
- `needs_clarification`: 是否建议先澄清
- `clarification_reason`: 澄清原因，没有则为 `null`

当前数据集重点覆盖：

- 单意图：`prematch` / `postmatch` / `health`
- mixed intent
- 高风险健康信号 override
- 低置信度与需澄清输入
- 口语、省略、短句、轻微噪声表达
- `fallback` bad cases

重新生成数据：

```bash
cd sft/router_intent_dataset
python3 generate_dataset.py
```

第一轮训练 YAML：

- `router_intent_qwen25_lora_v1.yaml`
- `evaluate_predictions.py`: 结构化路由评估脚本

如果已经把数据同步到服务器，并注册进 `/root/LLaMA-Factory/data/dataset_info.json`，可以直接用：

```bash
cd /root/LLaMA-Factory
export OMP_NUM_THREADS=1
llamafactory-cli train /root/router_intent_dataset/router_intent_qwen25_lora_v1.yaml
```

训练 / 预测完成后，可以用下面的命令看真正有意义的业务指标：

```bash
python3 /root/router_intent_dataset/evaluate_predictions.py \
  /root/LLaMA-Factory/saves/Qwen2.5-7B-Instruct/lora/eval_2026-04-18-23-01-21/generated_predictions.jsonl
```

这个脚本会输出：

- JSON 合法率
- schema 精确命中率
- `primary_intent` 准确率
- `secondary_intents` 准确率
- `risk_level` 准确率
- `needs_clarification` 准确率
- `high_risk` 召回率
