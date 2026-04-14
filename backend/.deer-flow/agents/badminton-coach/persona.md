# Badminton Coach Persona Assets

当前 coach 的人格不再直接从这个文件注入。

运行时入口改为：
- `SOUL.md`：稳定的教练身份、职责边界、安全规则
- `personalities/<personality_id>/persona.md`：可切换的人格表达
- `personalities/<personality_id>/meta.json`：人格标签、说明、结构化 style 配置

默认人格由 `config.yaml` 中的 `default_personality` 指定。
当前默认值：`guodegang`

这个文件保留为兼容说明，避免后续继续把人格内容写回根目录。
