-- infrastructure/postgres/init/02-schemas.sql
-- 9 个 schema(详见 v2 spec §6.2)
CREATE SCHEMA IF NOT EXISTS shared;
CREATE SCHEMA IF NOT EXISTS state;
CREATE SCHEMA IF NOT EXISTS llm;
CREATE SCHEMA IF NOT EXISTS notification;
CREATE SCHEMA IF NOT EXISTS planner;
CREATE SCHEMA IF NOT EXISTS writer;
CREATE SCHEMA IF NOT EXISTS reviewer;
CREATE SCHEMA IF NOT EXISTS orchestrator;
CREATE SCHEMA IF NOT EXISTS audit;  -- 独立审计 schema(详见 §13)
