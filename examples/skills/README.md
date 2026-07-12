# Skill Installer

第 12 章的本地 Skill 安装参考实现。Skill 包由 `skill.json`、`SKILL.md` 和可选参考文件组成；安装器验证名称、权限和依赖后原子复制到 Host 管理目录，并记录来源与校验和。

```bash
cd python
python -m unittest -v test_main.py
python main.py --root .agent/skills install /path/to/skill
python main.py --root .agent/skills update /path/to/skill
python main.py --root .agent/skills list
python main.py --root .agent/skills remove skill-name
```

当前只支持可信本地目录。Git 下载、签名、远程市场和沙箱属于生产扩展，不在此离线示例中。
