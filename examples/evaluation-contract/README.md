# Evaluation Contract

最小可运行的 Agent 评估工程：读取版本化 JSON 用例，执行确定性 Tool 轨迹，并同时检查最终状态、允许/禁止 Tool、调用次数、安全边界和版本元数据。

```bash
cd python
python -m unittest -v
python main.py ../cases/readonly.json

cd ../typescript
npm install
npm test
```

它不评估自然语言质量，也不把 LLM-as-Judge 当作唯一真值；它演示的是轨迹级硬断言，适合作为真实模型评估集的基础执行器。
