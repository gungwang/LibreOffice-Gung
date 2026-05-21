# Provider Configuration

Simplified Chinese version: [provider-config.zh-CN.md](./provider-config.zh-CN.md)

Current local configuration:

- PowerShell dev and verification entrypoints load `.env` from the workspace root first and from `libreoffice-ai-agent/.env` second.
- Existing process environment variables win over `.env` values.
- A checked-in sample lives at [../.env.example](../.env.example).

OpenRouter variables used by the current implementation:

- `OPENROUTER_API_KEY` or `LOAIA_OPENROUTER_API_KEY`
- `LOAIA_DEFAULT_PROVIDER`
- `LOAIA_DEFAULT_MODEL`

Recommended OpenRouter defaults for this repo:

- `LOAIA_DEFAULT_PROVIDER=openrouter`
- `LOAIA_DEFAULT_MODEL=openai/gpt-4.1-mini`

Resolution order for local configuration:

1. existing process environment variables
2. workspace root `.env`
3. `libreoffice-ai-agent/.env`

Current provider classes supported by the MVP surface:

- OpenAI-compatible
- Anthropic
- Gemini
- OpenRouter

Recommended local setup examples:

```env
OPENROUTER_API_KEY=replace-with-your-key
LOAIA_DEFAULT_PROVIDER=openrouter
LOAIA_DEFAULT_MODEL=openai/gpt-4.1-mini
```

If you want a local OpenAI-compatible server instead:

```env
LOAIA_DEFAULT_PROVIDER=openai-compatible
LOAIA_DEFAULT_MODEL=local-default
```

Current secret handling:

- OpenRouter reads `OPENROUTER_API_KEY` or `LOAIA_OPENROUTER_API_KEY` from the environment.

Longer-term target:

- remote API keys in Windows Credential Manager
- non-secret defaults in a profile-scoped settings file
