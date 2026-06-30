# Memo Example

This file shows the expected rough input format for copied AI conversations.

The format should be loose. Users should be able to copy a whole conversation without spending time cleaning it.

---

## 2026-06-30 - Local Knowledge Base Idea

User:

重点还是自生长吧，先不管和 AI 对话框里聊的东西了，我需要构建一个真正的可以自生长的知识库，比如我有一个本地的文件夹专门作为知识库，里面放着不同类型的文件夹。

Assistant:

这个方向接近一个完整的 local-first personal knowledge system。重点不是让 AI 一次性扫描整个文件夹，而是建立文件扫描、解析、索引、AI 总结、用户确认、Markdown 输出的管道。

User:

得需要专业文档整理一下，规划一下阶段，先建个 github 仓库把相关文档都放进去，要不然容易忘。

---

## Expected Output

The tool should generate:

- raw conversation archive
- conversation summary
- durable knowledge notes
- suggested tags
- links to related notes

It should preserve the difference between:

- user original thought
- assistant response
- AI-generated later summary

