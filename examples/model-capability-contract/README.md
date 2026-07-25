# Model Capability Contract

用一个确定性的 Provider 验证 Host 不应只依赖模型名称，而应根据能力快照决定 Tool Calling、Structured Output、Streaming、Usage 和 Cancel 是否可用。

```bash
cd python
python -m unittest -v

cd ../typescript
npm install
npm test
```
