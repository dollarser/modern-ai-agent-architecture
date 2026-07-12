# Plugin Manager

第 14 章的本地 Plugin 安装参考实现。安装器只治理包、Manifest、权限、依赖、启停、来源和校验和，不直接导入或执行第三方代码；`entrypoint` 是 Host 预先注册的可信 Factory ID。

```bash
cd python
python -m unittest -v test_main.py
python main.py --root .agent/plugins install /path/to/plugin
python main.py --root .agent/plugins update /path/to/plugin
python main.py --root .agent/plugins disable plugin-name
python main.py --root .agent/plugins remove plugin-name
```

生产实现还需要签名、发布者信任、兼容性求解、进程沙箱、资源配额和安全更新策略。
