# Provider 配置说明

英文版: [provider-config.md](./provider-config.md)

当前本地配置方式：

- PowerShell 开发脚本和验证脚本会先读取工作区根目录的 `.env`，再读取 `libreoffice-ai-agent/.env`。
- 如果进程环境变量里已经有同名值，就以进程环境变量为准。
- 仓库里提供了一个示例文件：[../.env.example](../.env.example)。

当前实现里会读取的 OpenRouter 变量：

- `OPENROUTER_API_KEY` 或 `LOAIA_OPENROUTER_API_KEY`
- `LOAIA_DEFAULT_PROVIDER`
- `LOAIA_DEFAULT_MODEL`

这个仓库推荐的 OpenRouter 默认值：

- `LOAIA_DEFAULT_PROVIDER=openrouter`
- `LOAIA_DEFAULT_MODEL=openai/gpt-4.1-mini`

本地配置优先级：

1. 进程环境变量
2. 工作区根目录 `.env`
3. `libreoffice-ai-agent/.env`

当前 MVP 表面支持的 Provider 类型：

- OpenAI 兼容接口
- Anthropic
- Gemini
- OpenRouter

推荐的 OpenRouter 配置示例：

```env
OPENROUTER_API_KEY=replace-with-your-key
LOAIA_DEFAULT_PROVIDER=openrouter
LOAIA_DEFAULT_MODEL=openai/gpt-4.1-mini
```

如果你要切回本地 OpenAI 兼容服务，可以用：

```env
LOAIA_DEFAULT_PROVIDER=openai-compatible
LOAIA_DEFAULT_MODEL=local-default
```

当前敏感信息处理方式：

- OpenRouter 现在直接从环境变量 `OPENROUTER_API_KEY` 或 `LOAIA_OPENROUTER_API_KEY` 读取密钥。

后续目标：

- 远程 API Key 放到 Windows Credential Manager
- 非敏感默认设置放到 profile 作用域设置文件里
