-- JARVIS v3 — Full Database Schema
-- Run this once on Supabase SQL editor

-- Users
CREATE TABLE IF NOT EXISTS j_users (
    username      TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    display_name  TEXT,
    role          TEXT DEFAULT 'guest',
    family_member TEXT,
    approved      BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    last_login    TIMESTAMPTZ,
    login_count   INTEGER DEFAULT 0
);

-- Sessions
CREATE TABLE IF NOT EXISTS j_sessions (
    token      TEXT PRIMARY KEY,
    username   TEXT NOT NULL,
    device_id  TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    last_seen  TIMESTAMPTZ DEFAULT NOW()
);

-- Hot memory — recent messages
CREATE TABLE IF NOT EXISTS memories (
    id          BIGSERIAL PRIMARY KEY,
    device_id   TEXT NOT NULL,
    person      TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    importance  FLOAT DEFAULT 0.5,
    archived    BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_memories_device_created ON memories(device_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_person_archived ON memories(person, archived);

-- Warm memory — compressed summaries
CREATE TABLE IF NOT EXISTS memory_archive (
    id           BIGSERIAL PRIMARY KEY,
    person       TEXT NOT NULL,
    device_id    TEXT,
    summary      TEXT NOT NULL,
    period_start TIMESTAMPTZ,
    period_end   TIMESTAMPTZ,
    message_count INTEGER DEFAULT 0,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_archive_person ON memory_archive(person, created_at DESC);

-- Cold memory — long-term facts
CREATE TABLE IF NOT EXISTS facts (
    id           BIGSERIAL PRIMARY KEY,
    key          TEXT NOT NULL,
    value        TEXT NOT NULL,
    person       TEXT DEFAULT 'family',
    importance   FLOAT DEFAULT 0.5,
    last_accessed TIMESTAMPTZ DEFAULT NOW(),
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_facts_person ON facts(person, importance DESC);

-- Devices
CREATE TABLE IF NOT EXISTS devices (
    device_id   TEXT PRIMARY KEY,
    person      TEXT,
    user_agent  TEXT,
    last_seen   TIMESTAMPTZ DEFAULT NOW(),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Persons metadata
CREATE TABLE IF NOT EXISTS persons (
    name               TEXT PRIMARY KEY,
    lang_preference    TEXT DEFAULT 'english',
    private_mode       BOOLEAN DEFAULT FALSE,
    created_at         TIMESTAMPTZ DEFAULT NOW()
);

-- Reminders
CREATE TABLE IF NOT EXISTS reminders (
    id          BIGSERIAL PRIMARY KEY,
    person      TEXT NOT NULL,
    device_id   TEXT,
    text        TEXT NOT NULL,
    remind_at   TIMESTAMPTZ NOT NULL,
    done        BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reminders_person_time ON reminders(person, remind_at);

-- Todos
CREATE TABLE IF NOT EXISTS todos (
    id          BIGSERIAL PRIMARY KEY,
    person      TEXT NOT NULL,
    device_id   TEXT,
    text        TEXT NOT NULL,
    category    TEXT DEFAULT 'general',
    done        BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Notes
CREATE TABLE IF NOT EXISTS notes (
    id          BIGSERIAL PRIMARY KEY,
    person      TEXT NOT NULL,
    device_id   TEXT,
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Birthdays
CREATE TABLE IF NOT EXISTS birthdays (
    id          BIGSERIAL PRIMARY KEY,
    person      TEXT NOT NULL,
    name        TEXT NOT NULL,
    dob         TEXT NOT NULL,
    relation    TEXT DEFAULT '',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- RL Feedback
CREATE TABLE IF NOT EXISTS rl_feedback (
    id           BIGSERIAL PRIMARY KEY,
    person       TEXT NOT NULL,
    user_msg     TEXT,
    jarvis_msg   TEXT,
    feedback     TEXT NOT NULL,
    source       TEXT DEFAULT 'user',
    auto_score   FLOAT,
    processed    BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rl_person_processed ON rl_feedback(person, processed);

-- Announcements
CREATE TABLE IF NOT EXISTS announcements (
    id           BIGSERIAL PRIMARY KEY,
    title        TEXT NOT NULL,
    content      TEXT NOT NULL,
    from_person  TEXT NOT NULL,
    active       BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Personality profiles
CREATE TABLE IF NOT EXISTS personality_profiles (
    person       TEXT PRIMARY KEY,
    profile_json JSONB DEFAULT '{}',
    prompt_additions TEXT DEFAULT '',
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Emotional history
CREATE TABLE IF NOT EXISTS emotional_history (
    id          BIGSERIAL PRIMARY KEY,
    person      TEXT NOT NULL,
    emotion     TEXT NOT NULL,
    intensity   TEXT NOT NULL,
    context     TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_emotion_person ON emotional_history(person, created_at DESC);

-- Conversation insights
CREATE TABLE IF NOT EXISTS conversation_insights (
    id          BIGSERIAL PRIMARY KEY,
    person      TEXT NOT NULL,
    insight     TEXT NOT NULL,
    week_of     DATE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Error logs (new in v3)
CREATE TABLE IF NOT EXISTS error_logs (
    id          BIGSERIAL PRIMARY KEY,
    error_type  TEXT,
    message     TEXT,
    context     TEXT,
    person      TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
