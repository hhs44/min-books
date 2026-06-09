-- infrastructure/postgres/init/03-users.sql
-- 9 个 service user + GRANT 矩阵(详见 v2 spec §6.4)
-- 密码:开发环境统一用 'minbook_dev'(与 .env POSTGRES_PASSWORD 一致;
-- MemoryClient 默认 fallback 也是 'minbook_dev')
-- 生产部署:用户应自己覆盖这些密码(走 PG 端 ALTER USER 或单独的 secret 加载脚本)
-- 表级 GRANT 包在 DO 块里:允许表在 Alembic 0001 之后再创建
DO $$
BEGIN
    CREATE USER svc_gateway     WITH PASSWORD 'minbook_dev';
    CREATE USER svc_book        WITH PASSWORD 'minbook_dev';
    CREATE USER svc_state       WITH PASSWORD 'minbook_dev';
    CREATE USER svc_pipeline    WITH PASSWORD 'minbook_dev';
    CREATE USER svc_planner     WITH PASSWORD 'minbook_dev';
    CREATE USER svc_writer      WITH PASSWORD 'minbook_dev';
    CREATE USER svc_reviewer    WITH PASSWORD 'minbook_dev';
    CREATE USER svc_llm         WITH PASSWORD 'minbook_dev';
    CREATE USER svc_notify      WITH PASSWORD 'minbook_dev';
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- === shared schema ===
-- 所有人可读,book-service 独占写,llm-gateway 写账单
GRANT USAGE ON SCHEMA shared TO svc_gateway, svc_book, svc_state, svc_pipeline,
                              svc_planner, svc_writer, svc_reviewer, svc_llm, svc_notify;
GRANT SELECT ON ALL TABLES IN SCHEMA shared TO svc_gateway, svc_state, svc_pipeline,
                                                    svc_planner, svc_writer, svc_reviewer, svc_llm, svc_notify;
-- book-service 后续会接管 shared.books / shared.chapters / shared.book_settings 的写权限
-- 这里给 book-service ALL,再用 REVOKE 收回其他人的写权限(下面的 REVOKE 段)
GRANT ALL ON ALL TABLES IN SCHEMA shared TO svc_book;
-- 默认权限:book-service 在 shared schema 里未来建的表自动获得 ALL
ALTER DEFAULT PRIVILEGES IN SCHEMA shared GRANT ALL ON TABLES TO svc_book;

-- shared.monthly_bills 由 Alembic 0001 创建
DO $$
BEGIN
    EXECUTE 'GRANT INSERT, UPDATE ON shared.monthly_bills TO svc_llm';
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- === state schema(state-service 独占) ===
GRANT USAGE ON SCHEMA state TO svc_state, svc_planner, svc_writer, svc_reviewer;
GRANT ALL ON ALL TABLES IN SCHEMA state TO svc_state;
GRANT SELECT ON ALL TABLES IN SCHEMA state TO svc_planner, svc_writer, svc_reviewer;
ALTER DEFAULT PRIVILEGES IN SCHEMA state GRANT ALL ON TABLES TO svc_state;
ALTER DEFAULT PRIVILEGES IN SCHEMA state GRANT SELECT ON TABLES TO svc_planner, svc_writer, svc_reviewer;

-- === llm schema(llm-gateway 独占) ===
GRANT USAGE ON SCHEMA llm TO svc_llm, svc_reviewer, svc_writer, svc_planner, svc_pipeline, svc_notify;
GRANT ALL ON ALL TABLES IN SCHEMA llm TO svc_llm;
ALTER DEFAULT PRIVILEGES IN SCHEMA llm GRANT ALL ON TABLES TO svc_llm;
-- llm.llm_calls:其它服务可 INSERT(由 agent / pipeline 调 LLM 时写日志)
DO $$
BEGIN
    EXECUTE 'GRANT INSERT ON llm.llm_calls TO svc_reviewer, svc_writer, svc_planner, svc_pipeline, svc_notify';
    EXECUTE 'GRANT SELECT ON llm.llm_calls TO svc_reviewer, svc_writer, svc_planner, svc_pipeline, svc_notify';
EXCEPTION WHEN undefined_table THEN NULL; END $$;
ALTER DEFAULT PRIVILEGES IN SCHEMA llm GRANT INSERT, SELECT ON TABLES TO svc_reviewer, svc_writer, svc_planner, svc_pipeline, svc_notify;

-- === notification schema(notification-service 独占) ===
GRANT USAGE ON SCHEMA notification TO svc_notify, svc_pipeline, svc_llm;
GRANT ALL ON ALL TABLES IN SCHEMA notification TO svc_notify;
ALTER DEFAULT PRIVILEGES IN SCHEMA notification GRANT ALL ON TABLES TO svc_notify;
-- notification.alert_dedup:llm-gateway 写入告警去重键,pipeline 可读
DO $$
BEGIN
    EXECUTE 'GRANT INSERT, SELECT ON notification.alert_dedup TO svc_llm';
    EXECUTE 'GRANT SELECT ON notification.alert_dedup TO svc_notify, svc_pipeline';
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- === planner schema ===
GRANT USAGE ON SCHEMA planner TO svc_planner;
GRANT ALL ON ALL TABLES IN SCHEMA planner TO svc_planner;
ALTER DEFAULT PRIVILEGES IN SCHEMA planner GRANT ALL ON TABLES TO svc_planner;

-- === writer schema ===
GRANT USAGE ON SCHEMA writer TO svc_writer;
GRANT ALL ON ALL TABLES IN SCHEMA writer TO svc_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA writer GRANT ALL ON TABLES TO svc_writer;

-- === reviewer schema ===
GRANT USAGE ON SCHEMA reviewer TO svc_reviewer;
GRANT ALL ON ALL TABLES IN SCHEMA reviewer TO svc_reviewer;
ALTER DEFAULT PRIVILEGES IN SCHEMA reviewer GRANT ALL ON TABLES TO svc_reviewer;

-- === orchestrator schema(pipeline-orchestrator 独占) ===
GRANT USAGE ON SCHEMA orchestrator TO svc_pipeline, svc_planner, svc_writer, svc_reviewer, svc_llm;
GRANT ALL ON ALL TABLES IN SCHEMA orchestrator TO svc_pipeline;
ALTER DEFAULT PRIVILEGES IN SCHEMA orchestrator GRANT ALL ON TABLES TO svc_pipeline;
DO $$
BEGIN
    EXECUTE 'GRANT SELECT ON orchestrator.writing_tasks TO svc_llm';  -- FK 关联
    EXECUTE 'GRANT INSERT, UPDATE ON orchestrator.agent_registry TO svc_planner, svc_writer, svc_reviewer, svc_llm';
    EXECUTE 'GRANT SELECT ON orchestrator.agent_registry TO svc_pipeline';
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- === audit schema(gateway 写,所有服务可读) ===
GRANT USAGE ON SCHEMA audit TO svc_gateway, svc_state, svc_pipeline, svc_planner,
                                svc_writer, svc_reviewer, svc_llm, svc_notify, svc_book;
GRANT ALL ON ALL TABLES IN SCHEMA audit TO svc_gateway;
GRANT SELECT ON ALL TABLES IN SCHEMA audit TO svc_state, svc_pipeline, svc_planner,
                                                  svc_writer, svc_reviewer, svc_llm, svc_notify, svc_book;
ALTER DEFAULT PRIVILEGES IN SCHEMA audit GRANT ALL ON TABLES TO svc_gateway;
ALTER DEFAULT PRIVILEGES IN SCHEMA audit GRANT SELECT ON TABLES TO svc_state, svc_pipeline, svc_planner,
                                                                svc_writer, svc_reviewer, svc_llm, svc_notify, svc_book;

-- === 防御性 REVOKE:防止 reviewer prompt 注入后篡改书库 ===
-- 这些表在 Alembic 0001 之后才存在,用 DO 包起来允许暂未建表
DO $$
BEGIN
    -- shared.chapters(由 book-service 独占)
    EXECUTE 'REVOKE INSERT, UPDATE, DELETE ON shared.chapters FROM svc_reviewer, svc_planner, svc_writer, svc_llm, svc_notify, svc_pipeline, svc_state, svc_gateway';
    EXECUTE 'GRANT SELECT ON shared.chapters TO svc_reviewer, svc_planner, svc_writer, svc_llm, svc_notify, svc_pipeline, svc_state, svc_gateway';
    -- shared.books
    EXECUTE 'REVOKE INSERT, UPDATE, DELETE ON shared.books FROM svc_reviewer, svc_planner, svc_writer, svc_llm, svc_notify, svc_pipeline, svc_state, svc_gateway';
    EXECUTE 'GRANT SELECT ON shared.books TO svc_reviewer, svc_planner, svc_writer, svc_llm, svc_notify, svc_pipeline, svc_state, svc_gateway';
    -- state.truth_files
    EXECUTE 'REVOKE INSERT, UPDATE, DELETE ON state.truth_files FROM svc_reviewer, svc_planner, svc_writer, svc_llm, svc_notify, svc_pipeline, svc_gateway';
    EXECUTE 'GRANT SELECT ON state.truth_files TO svc_reviewer, svc_planner, svc_writer, svc_llm, svc_notify, svc_pipeline, svc_gateway';
EXCEPTION WHEN undefined_table THEN NULL; END $$;
