"""agent-writer-service 的 agent 模块包。

模块在被 main.py 导入时,通过 @register_agent 装饰器把自己注册到全局 AgentRegistry。
共 7 个 agent:
- WriterAgent:正文生成 + 字数治理
- PolisherAgent:润色
- LengthNormalizer:字数压缩/扩展
- ConsolidatorAgent:章节合并(纯逻辑)
- ChapterAnalyzerAgent:章节分析(情感曲线 / 节奏 / 关键词)
- StyleAnalyzer:文风指纹提取(写 writer.style_corpus)
- ShortFictionWriterAgent:短篇专用
"""
