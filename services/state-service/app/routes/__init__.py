"""State Service 路由集合(详见 v2 plan §Phase C)。

- truth: 7 真相文件 CRUD(GET / PUT,带乐观并发)
- snapshots: 状态快照(POST / GET)
- config: 共享全局配置(GET / PUT)
- memory: 记忆检索占位(GET 501,v3 defer)
"""
