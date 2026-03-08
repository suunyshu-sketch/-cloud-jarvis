-- ═══════════════════════════════════════════════════════════
--  JARVIS — Database Migrations v1
--  Run once against Supabase. Safe to re-run (IF NOT EXISTS).
-- ═══════════════════════════════════════════════════════════

-- Core chat memory
CREATE TABLE IF NOT EXISTS memories (
    id          BIGSERIAL PRIMARY KEY,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    timestamp   TIMESTAMPTZ DEFAULT NOW(),
    device_id   TEXT,
    private     BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_memories_device ON memories(device_id);
CREATE INDEX IF NOT EXISTS idx_memories_ts     ON memories(timestamp DESC);

-- Compressed/archived memory tiers
CREATE TABLE IF NOT EXISTS memory_archive (
    id           BIGSERIAL PRIMARY KEY,
    tier         INTEGER NOT NULL,         -- 2=warm, 3=cold, 4=archive
    period_start TIMESTAMPTZ,
    period_end   TIMESTAMPTZ,
    summary      TEXT NOT NULL,
    device_id    TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Learned facts per person / device
CREATE TABLE IF NOT EXISTS facts (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated    TIMESTAMPTZ DEFAULT NOW(),
    person     TEXT
);

-- Registered devices
CREATE TABLE IF NOT EXISTS devices (
    device_id   TEXT PRIMARY KEY,
    device_name TEXT,
    owner       TEXT,
    last_seen   TIMESTAMPTZ DEFAULT NOW(),
    first_seen  TIMESTAMPTZ DEFAULT NOW(),
    user_agent  TEXT,
    message_count INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_devices_owner ON devices(owner);

-- Persons (aggregate view across devices)
CREATE TABLE IF NOT EXISTS persons (
    name          TEXT PRIMARY KEY,
    device_ids    TEXT,
    first_seen    TIMESTAMPTZ,
    last_seen     TIMESTAMPTZ,
    message_count INTEGER DEFAULT 0
);

-- Reminders
CREATE TABLE IF NOT EXISTS reminders (
    id         BIGSERIAL PRIMARY KEY,
    person     TEXT,
    device_id  TEXT,
    text       TEXT NOT NULL,
    remind_at  TIMESTAMPTZ NOT NULL,
    done       BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reminders_device ON reminders(device_id, done, remind_at);

-- Todos
CREATE TABLE IF NOT EXISTS todos (
    id         BIGSERIAL PRIMARY KEY,
    person     TEXT,
    device_id  TEXT,
    text       TEXT NOT NULL,
    done       BOOLEAN DEFAULT FALSE,
    category   TEXT DEFAULT 'general',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_todos_device ON todos(device_id);

-- Notes
CREATE TABLE IF NOT EXISTS notes (
    id         BIGSERIAL PRIMARY KEY,
    person     TEXT,
    device_id  TEXT,
    title      TEXT,
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_notes_device ON notes(device_id);

-- Birthdays
CREATE TABLE IF NOT EXISTS birthdays (
    id       BIGSERIAL PRIMARY KEY,
    person   TEXT,
    name     TEXT NOT NULL,
    dob      DATE NOT NULL,
    relation TEXT
);

-- RL Feedback
CREATE TABLE IF NOT EXISTS rl_feedback (
    id             BIGSERIAL PRIMARY KEY,
    person         TEXT,
    device_id      TEXT,
    user_msg       TEXT,
    jarvis_response TEXT,
    feedback       TEXT,
    topic          TEXT DEFAULT 'general',
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Announcements
CREATE TABLE IF NOT EXISTS announcements (
    id          BIGSERIAL PRIMARY KEY,
    title       TEXT,
    content     TEXT NOT NULL,
    from_person TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    active      BOOLEAN DEFAULT TRUE
);

-- Deep Personality Profiles
CREATE TABLE IF NOT EXISTS personality_profiles (
    person               TEXT PRIMARY KEY,
    raw_profile          TEXT,
    behavioral_patterns  TEXT,
    communication_style  TEXT,
    emotional_triggers   TEXT,
    topics_they_love     TEXT,
    topics_to_avoid      TEXT,
    how_they_deflect     TEXT,
    inside_knowledge     TEXT,
    last_updated         TIMESTAMPTZ DEFAULT NOW()
);

-- Emotional History
CREATE TABLE IF NOT EXISTS emotional_history (
    id          BIGSERIAL PRIMARY KEY,
    person      TEXT,
    device_id   TEXT,
    emotion     TEXT,
    intensity   TEXT,
    context     TEXT,
    time_of_day TEXT,
    day_of_week TEXT,
    timestamp   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_emotion_person ON emotional_history(person, timestamp DESC);

-- Auth: Users
CREATE TABLE IF NOT EXISTS j_users (
    username      TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    display_name  TEXT,
    role          TEXT DEFAULT 'guest',
    family_member TEXT,
    approved      BOOLEAN DEFAULT FALSE,
    relation      TEXT,
    knows_member  TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    last_login    TIMESTAMPTZ,
    login_count   INTEGER DEFAULT 0
);

-- Auth: Sessions (JWT metadata)
CREATE TABLE IF NOT EXISTS j_sessions (
    token      TEXT PRIMARY KEY,
    username   TEXT NOT NULL,
    device_id  TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    last_seen  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(username);
CREATE INDEX IF NOT EXISTS idx_sessions_exp  ON sessions(expires_at);

-- Conversation Insights
CREATE TABLE IF NOT EXISTS conversation_insights (
    id           BIGSERIAL PRIMARY KEY,
    person       TEXT,
    insight      TEXT NOT NULL,
    insight_type TEXT DEFAULT 'general',
    confidence   TEXT DEFAULT 'medium',
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_insights_person ON conversation_insights(person, created_at DESC);
