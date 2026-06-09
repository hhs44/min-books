"""agent-planner 服务的所有 agent 模块(在 import 时通过 @register_agent 自动注册)。

包含(v3 Phase B 4 agents):
- architect:建书生成基础设定(story_bible / style_guide / book_rules / character_matrix)
- planner:从作者意图 → 章节意图(ChapterIntent)
- composer:纯逻辑上下文编排 + 规则栈编译(不调 LLM)
- foundation_reviewer:审核 ArchitectAgent 输出
"""
