# 开发说明

英文版: [development.md](./development.md)

建议开发顺序：

1. 先打通 extension 和 sidecar 的通信握手
2. 再做侧边栏基础 UI
3. 再做 Writer 选区提取
4. 接着做 mock provider 和本地 OpenAI 兼容 provider
5. 再做安全格式动作链路
6. 再做“预览后审批”的内容编辑链路
7. 然后补历史记录和审计日志
8. 最后补 Calc 和 Impress 的最小切片

当前开发前提：

- Python 3.11 及以上
- 优先 Windows 开发
- 使用单独的 LibreOffice 测试 profile 安装和调试扩展
