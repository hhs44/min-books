"""基线迁移:8 个 schema 全部表

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-08

完整 DDL 见 v2 spec §6.3 + §13(审计)+ §11(DLQ)+ §12(cost 表)

注意:schema 本身由 infrastructure/postgres/init/02-schemas.sql 创建(9 个 schema),
本迁移只创建 8 个业务 schema 的表 + audit.audit_log(基线完整)。

asyncpg 不支持多语句 prepared statement,因此每个 DDL 语句单独 op.execute()。
"""
from alembic import op

# revision identifiers
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === shared schema ===
    op.execute("""
        CREATE TABLE shared.books (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title VARCHAR(255) NOT NULL,
            genre VARCHAR(100),
            language VARCHAR(10) DEFAULT 'zh',
            config_json JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE shared.chapters (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            book_id UUID REFERENCES shared.books(id) ON DELETE CASCADE,
            chapter_number INTEGER NOT NULL,
            title VARCHAR(255),
            content TEXT,
            status VARCHAR(50) DEFAULT 'draft',
            word_count INTEGER DEFAULT 0,
            version INTEGER DEFAULT 1,
            draft_content TEXT,
            draft_status VARCHAR(20) DEFAULT 'none',
            idempotency_key VARCHAR(100),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(book_id, chapter_number)
        )
    """)
    op.execute("CREATE INDEX idx_chapters_book ON shared.chapters(book_id)")
    op.execute("""
        CREATE TABLE shared.book_settings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            book_id UUID REFERENCES shared.books(id) ON DELETE CASCADE,
            setting_type VARCHAR(50) NOT NULL,
            content_json JSONB,
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(book_id, setting_type)
        )
    """)
    op.execute("""
        CREATE TABLE shared.interaction_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            book_id UUID REFERENCES shared.books(id) ON DELETE CASCADE,
            mode VARCHAR(50) DEFAULT 'auto',
            transcript_json JSONB DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE shared.global_config (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            config_key VARCHAR(255) UNIQUE NOT NULL,
            config_value JSONB NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE shared.genre_templates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) UNIQUE NOT NULL,
            description TEXT,
            template_json JSONB NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE shared.daemon_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            book_id UUID REFERENCES shared.books(id) ON DELETE CASCADE UNIQUE,
            schedule_json JSONB DEFAULT '{}'::jsonb,
            enabled BOOLEAN DEFAULT false,
            last_run_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE shared.monthly_bills (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            month DATE UNIQUE NOT NULL,
            total_cost_usd DECIMAL(10, 2) NOT NULL,
            breakdown_json JSONB NOT NULL,
            generated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # === state schema ===
    op.execute("""
        CREATE TABLE state.truth_files (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            book_id UUID REFERENCES shared.books(id) ON DELETE CASCADE,
            file_type VARCHAR(50) NOT NULL,
            content JSONB,
            version INTEGER DEFAULT 1,
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(book_id, file_type)
        )
    """)
    op.execute("CREATE INDEX idx_truth_files_content_gin ON state.truth_files USING gin (content)")
    op.execute("""
        CREATE TABLE state.state_snapshots (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            book_id UUID REFERENCES shared.books(id) ON DELETE CASCADE,
            chapter_number INTEGER,
            snapshot_json JSONB NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # === llm schema ===
    op.execute("""
        CREATE TABLE llm.llm_providers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            provider VARCHAR(100) NOT NULL,
            model VARCHAR(100) NOT NULL,
            cost_per_1k_input_tokens DECIMAL(10, 6) NOT NULL,
            cost_per_1k_output_tokens DECIMAL(10, 6) NOT NULL,
            currency VARCHAR(10) DEFAULT 'USD',
            effective_from DATE NOT NULL,
            UNIQUE(provider, model, effective_from)
        )
    """)
    op.execute("""
        CREATE TABLE llm.llm_calls (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            book_id UUID,
            pipeline_run_id UUID,
            task_id UUID,
            agent_id VARCHAR(100),
            node_id VARCHAR(100),
            provider VARCHAR(100) NOT NULL,
            model VARCHAR(100) NOT NULL,
            endpoint VARCHAR(255),
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            latency_ms INTEGER,
            cost_estimate DECIMAL(10, 6),
            success BOOLEAN NOT NULL DEFAULT true,
            error_type VARCHAR(50),
            trace_id VARCHAR(32),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_llm_calls_book_date ON llm.llm_calls(book_id, created_at)")
    op.execute("CREATE INDEX idx_llm_calls_date ON llm.llm_calls(created_at)")
    op.execute("CREATE INDEX idx_llm_calls_agent_date ON llm.llm_calls(agent_id, created_at)")
    op.execute("""
        CREATE TABLE llm.cost_rollup_minute (
            bucket TIMESTAMPTZ PRIMARY KEY,
            total_cost_usd DECIMAL(10, 4) NOT NULL,
            prompt_tokens BIGINT NOT NULL,
            completion_tokens BIGINT NOT NULL,
            call_count INTEGER NOT NULL,
            error_count INTEGER NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE llm.cost_rollup_day (
            day DATE PRIMARY KEY,
            total_cost_usd DECIMAL(10, 2) NOT NULL,
            prompt_tokens BIGINT NOT NULL,
            completion_tokens BIGINT NOT NULL,
            call_count INTEGER NOT NULL,
            error_count INTEGER NOT NULL,
            top_model VARCHAR(100),
            top_model_cost_usd DECIMAL(10, 2),
            top_book_id UUID,
            top_book_cost_usd DECIMAL(10, 2),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # === notification schema ===
    op.execute("""
        CREATE TABLE notification.notification_channels (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            book_id UUID REFERENCES shared.books(id) ON DELETE CASCADE,
            channel_type VARCHAR(50) NOT NULL,
            config_json JSONB NOT NULL,
            enabled BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE notification.alert_dedup (
            alert_key VARCHAR(200) PRIMARY KEY,
            last_sent_at TIMESTAMPTZ NOT NULL
        )
    """)

    # === audit schema ===
    op.execute("""
        CREATE TABLE audit.audit_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            event_type VARCHAR(50) NOT NULL,
            service_name VARCHAR(100),
            source_ip INET,
            user_agent TEXT,
            user_id VARCHAR(100),
            details JSONB,
            occurred_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_audit_log_time ON audit.audit_log(occurred_at)")
    op.execute("CREATE INDEX idx_audit_log_type ON audit.audit_log(event_type)")
    op.execute("CREATE INDEX idx_audit_log_source_ip ON audit.audit_log(source_ip)")

    # === planner schema ===
    op.execute("""
        CREATE TABLE planner.episodes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            book_id UUID NOT NULL,
            chapter_number INTEGER,
            intent_json JSONB NOT NULL,
            outcome_score FLOAT,
            embedding VECTOR,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            archived_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX idx_planner_episodes_book ON planner.episodes(book_id)")
    op.execute("CREATE INDEX idx_planner_episodes_unarchived ON planner.episodes(book_id) WHERE archived_at IS NULL")
    op.execute("""
        CREATE TABLE planner.preferences (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            book_id UUID NOT NULL,
            preference_type VARCHAR(50) NOT NULL,
            preference_json JSONB NOT NULL,
            confidence FLOAT NOT NULL DEFAULT 0.5,
            source_episode_ids UUID[],
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(book_id, preference_type)
        )
    """)
    op.execute("""
        CREATE TABLE planner.prompt_templates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            template_name VARCHAR(100) UNIQUE NOT NULL,
            template_content TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # === writer schema ===
    op.execute("""
        CREATE TABLE writer.style_corpus (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            book_id UUID NOT NULL,
            fingerprint_json JSONB NOT NULL,
            source VARCHAR(50),
            embedding VECTOR,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_writer_style_corpus_book ON writer.style_corpus(book_id)")
    op.execute("""
        CREATE TABLE writer.voice_profiles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            book_id UUID NOT NULL,
            character_name VARCHAR(100),
            voice_json JSONB NOT NULL,
            embedding VECTOR,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE writer.vocabulary (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            book_id UUID NOT NULL,
            word VARCHAR(100),
            frequency INTEGER DEFAULT 1,
            style_tag VARCHAR(50),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE writer.prompt_templates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            template_name VARCHAR(100) UNIQUE NOT NULL,
            template_content TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # === reviewer schema ===
    op.execute("""
        CREATE TABLE reviewer.audit_history (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            book_id UUID NOT NULL,
            chapter_number INTEGER,
            issues_json JSONB NOT NULL,
            severity VARCHAR(20),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_reviewer_audit_history_book ON reviewer.audit_history(book_id)")
    op.execute("""
        CREATE TABLE reviewer.error_patterns (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            pattern_name VARCHAR(100) UNIQUE NOT NULL,
            description TEXT,
            pattern_json JSONB NOT NULL,
            frequency INTEGER DEFAULT 1,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE reviewer.fix_success_rates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            error_pattern_id UUID REFERENCES reviewer.error_patterns(id),
            attempts INTEGER DEFAULT 0,
            successes INTEGER DEFAULT 0,
            rate DECIMAL(5, 4),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE reviewer.radar_cache (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            scan_id VARCHAR(100) UNIQUE NOT NULL,
            result_json JSONB NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            expires_at TIMESTAMPTZ
        )
    """)

    # === orchestrator schema ===
    op.execute("""
        CREATE TABLE orchestrator.agent_registry (
            agent_id VARCHAR(100) PRIMARY KEY,
            service_name VARCHAR(100) NOT NULL,
            name VARCHAR(100) NOT NULL,
            version VARCHAR(20) NOT NULL,
            card_json JSONB NOT NULL,
            endpoint VARCHAR(255) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            last_heartbeat_at TIMESTAMPTZ DEFAULT NOW(),
            registered_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_agent_registry_service ON orchestrator.agent_registry(service_name)")
    op.execute("CREATE INDEX idx_agent_registry_capability ON orchestrator.agent_registry USING gin ((card_json->'capabilities'))")
    op.execute("""
        CREATE TABLE orchestrator.pipeline_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            pipeline_id VARCHAR(100) NOT NULL,
            book_id UUID NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            dag_definition JSONB NOT NULL,
            checkpoints JSONB DEFAULT '{}'::jsonb,
            error JSONB,
            started_at TIMESTAMPTZ DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX idx_pipeline_runs_book ON orchestrator.pipeline_runs(book_id)")
    op.execute("CREATE INDEX idx_pipeline_runs_status ON orchestrator.pipeline_runs(status) WHERE status = 'running'")
    op.execute("""
        CREATE TABLE orchestrator.writing_tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            book_id UUID NOT NULL,
            chapter_id UUID,
            task_type VARCHAR(50) NOT NULL,
            pipeline_run_id UUID REFERENCES orchestrator.pipeline_runs(id),
            status VARCHAR(50) DEFAULT 'pending',
            config_json JSONB DEFAULT '{}'::jsonb,
            result_json JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
    """)
    op.execute("""
        CREATE TABLE orchestrator.dlq (
            pipeline_run_id UUID PRIMARY KEY,
            book_id UUID,
            chapter_number INTEGER,
            failed_node_id VARCHAR(100),
            error_type VARCHAR(50),
            error_message TEXT,
            error_stack TEXT,
            checkpoints_at_failure JSONB,
            llm_calls_summary JSONB,
            occurred_at TIMESTAMPTZ,
            status VARCHAR(20) DEFAULT 'pending'
        )
    """)

    # 种子 LLM providers(单条 INSERT,multi-row)
    op.execute("""
        INSERT INTO llm.llm_providers (provider, model, cost_per_1k_input_tokens, cost_per_1k_output_tokens, effective_from) VALUES
        ('openai', 'gpt-4o', 0.0025, 0.01, '2026-01-01'),
        ('openai', 'gpt-4o-mini', 0.00015, 0.0006, '2026-01-01'),
        ('anthropic', 'claude-3-5-sonnet', 0.003, 0.015, '2026-01-01'),
        ('anthropic', 'claude-3-5-haiku', 0.0008, 0.004, '2026-01-01'),
        ('deepseek', 'deepseek-chat', 0.00014, 0.00028, '2026-01-01')
    """)

    # 种子全局配置(LLM 成本告警阈值)
    op.execute("""
        INSERT INTO shared.global_config (config_key, config_value) VALUES
        ('llm_cost_alert_daily_usd',         '20'::jsonb),
        ('llm_cost_alert_monthly_usd',       '500'::jsonb),
        ('llm_cost_alert_per_book_usd',      '100'::jsonb),
        ('llm_cost_alert_spike_multiplier',  '3'::jsonb)
    """)


def downgrade() -> None:
    # 倒序 drop
    for schema in ["orchestrator", "reviewer", "writer", "planner",
                   "audit", "notification", "llm", "state", "shared"]:
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
