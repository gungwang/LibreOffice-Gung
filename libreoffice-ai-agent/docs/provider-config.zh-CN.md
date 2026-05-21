# Provider 配置说明

英文版: [provider-config.md](./provider-config.md)

MVP 计划支持的 Provider 类型：

- OpenAI 兼容接口
- Anthropic
- Gemini
- OpenRouter

第一阶段推荐的本地模型接入方式：

- 任何 OpenAI 兼容的本地服务

敏感信息存储目标：

- 远程 API Key 放到 Windows Credential Manager
- 非敏感默认设置放到 profile 作用域设置文件里
