"""agent-reviewer-service 的 agent 模块包。

模块在被 main.py 导入时,通过 @register_agent 装饰器把自己注册到全局 AgentRegistry。
共 9 个 agent:
- ContinuityAuditor:33 维度连续性审计(主)
- ReviserAgent:根据 audit issues 修复
- StateValidator:真相文件一致性校验(纯逻辑)
- PostWriteValidator:跨章重复 + 硬规则 spot-fix(纯逻辑)
- ObserverAgent:从章节正文抽取事实(LLM)
- SettlerAgent:把 Observer 的 delta 写入 state-service
- AIGCDetector:AI 生成内容检测(纯规则)
- SensitiveWordsDetector:敏感词 / PII 检测(纯规则)
- RadarAgent:市场趋势扫描(NATS 周期触发)
"""
