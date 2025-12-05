-- ====================================
-- Signalink Database Schema
-- PostgreSQL 15+
-- ====================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable timestamp functions
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- ====================================
-- USERS TABLE
-- ====================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    avatar_url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT username_length CHECK (LENGTH(username) >= 3),
    CONSTRAINT email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_created_at ON users(created_at);

-- ====================================
-- CHANNELS TABLE
-- ====================================
CREATE TABLE channels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    is_private BOOLEAN DEFAULT FALSE,
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT channel_name_length CHECK (LENGTH(name) >= 2)
);

CREATE INDEX idx_channels_name ON channels(name);
CREATE INDEX idx_channels_created_by ON channels(created_by);
CREATE INDEX idx_channels_is_private ON channels(is_private);

-- ====================================
-- CHANNEL MEMBERS TABLE
-- ====================================
CREATE TABLE channel_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) DEFAULT 'member', -- 'owner', 'admin', 'member'
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(channel_id, user_id),
    CONSTRAINT valid_role CHECK (role IN ('owner', 'admin', 'member'))
);

CREATE INDEX idx_channel_members_channel ON channel_members(channel_id);
CREATE INDEX idx_channel_members_user ON channel_members(user_id);
CREATE INDEX idx_channel_members_role ON channel_members(channel_id, role);

-- ====================================
-- MESSAGES TABLE
-- ====================================
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    message_type VARCHAR(20) DEFAULT 'text', -- 'text', 'image', 'file', 'system'
    metadata JSONB, -- For storing additional data like file URLs, reactions, etc.
    is_edited BOOLEAN DEFAULT FALSE,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT content_not_empty CHECK (LENGTH(TRIM(content)) > 0),
    CONSTRAINT valid_message_type CHECK (message_type IN ('text', 'image', 'file', 'system'))
);

CREATE INDEX idx_messages_channel ON messages(channel_id, created_at DESC);
CREATE INDEX idx_messages_user ON messages(user_id);
CREATE INDEX idx_messages_created_at ON messages(created_at DESC);
CREATE INDEX idx_messages_type ON messages(message_type);

-- GIN index for JSONB metadata searching
CREATE INDEX idx_messages_metadata ON messages USING GIN (metadata);

-- ====================================
-- MESSAGE REACTIONS TABLE
-- ====================================
CREATE TABLE message_reactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    emoji VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(message_id, user_id, emoji)
);

CREATE INDEX idx_reactions_message ON message_reactions(message_id);
CREATE INDEX idx_reactions_user ON message_reactions(user_id);

-- ====================================
-- READ RECEIPTS TABLE
-- ====================================
CREATE TABLE read_receipts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    last_read_message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    last_read_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(channel_id, user_id)
);

CREATE INDEX idx_read_receipts_channel_user ON read_receipts(channel_id, user_id);
CREATE INDEX idx_read_receipts_last_read ON read_receipts(last_read_at);

-- ====================================
-- USER SESSIONS TABLE (for JWT blacklist/tracking)
-- ====================================
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_jti VARCHAR(255) UNIQUE NOT NULL, -- JWT ID for token tracking
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    user_agent VARCHAR(500),
    ip_address INET
);

CREATE INDEX idx_sessions_user ON user_sessions(user_id);
CREATE INDEX idx_sessions_jti ON user_sessions(token_jti);
CREATE INDEX idx_sessions_expires ON user_sessions(expires_at);

-- ====================================
-- NOTIFICATION PREFERENCES TABLE
-- ====================================
CREATE TABLE notification_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email_notifications BOOLEAN DEFAULT TRUE,
    push_notifications BOOLEAN DEFAULT TRUE,
    mention_notifications BOOLEAN DEFAULT TRUE,
    dm_notifications BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_notification_prefs_user ON notification_preferences(user_id);

-- ====================================
-- ANALYTICS EVENTS TABLE (Phase 4)
-- ====================================
CREATE TABLE analytics_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(50) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    channel_id UUID REFERENCES channels(id) ON DELETE SET NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_analytics_events_type ON analytics_events(event_type, created_at DESC);
CREATE INDEX idx_analytics_events_user ON analytics_events(user_id);
CREATE INDEX idx_analytics_events_channel ON analytics_events(channel_id);
CREATE INDEX idx_analytics_events_created ON analytics_events(created_at DESC);

-- GIN index for JSONB searching
CREATE INDEX idx_analytics_metadata ON analytics_events USING GIN (metadata);

-- ====================================
-- FUNCTIONS AND TRIGGERS
-- ====================================

-- Function to update 'updated_at' timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to relevant tables
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_channels_updated_at BEFORE UPDATE ON channels
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_messages_updated_at BEFORE UPDATE ON messages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_notification_prefs_updated_at BEFORE UPDATE ON notification_preferences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to automatically add channel creator as owner
CREATE OR REPLACE FUNCTION add_channel_creator_as_owner()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO channel_members (channel_id, user_id, role)
    VALUES (NEW.id, NEW.created_by, 'owner');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER add_creator_to_channel AFTER INSERT ON channels
    FOR EACH ROW EXECUTE FUNCTION add_channel_creator_as_owner();

-- Function to create default notification preferences for new users
CREATE OR REPLACE FUNCTION create_default_notification_preferences()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO notification_preferences (user_id)
    VALUES (NEW.id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER create_user_notification_prefs AFTER INSERT ON users
    FOR EACH ROW EXECUTE FUNCTION create_default_notification_preferences();

-- ====================================
-- VIEWS
-- ====================================

-- View for channel statistics
CREATE OR REPLACE VIEW channel_stats AS
SELECT
    c.id AS channel_id,
    c.name AS channel_name,
    COUNT(DISTINCT cm.user_id) AS member_count,
    COUNT(DISTINCT m.id) AS message_count,
    MAX(m.created_at) AS last_message_at
FROM channels c
LEFT JOIN channel_members cm ON c.id = cm.channel_id
LEFT JOIN messages m ON c.id = m.channel_id AND m.is_deleted = FALSE
GROUP BY c.id, c.name;

-- View for user activity
CREATE OR REPLACE VIEW user_activity AS
SELECT
    u.id AS user_id,
    u.username,
    COUNT(DISTINCT m.id) AS message_count,
    COUNT(DISTINCT cm.channel_id) AS channel_count,
    MAX(m.created_at) AS last_message_at
FROM users u
LEFT JOIN messages m ON u.id = m.user_id AND m.is_deleted = FALSE
LEFT JOIN channel_members cm ON u.id = cm.user_id
GROUP BY u.id, u.username;

-- ====================================
-- SEED DATA (Optional - for development)
-- ====================================

-- Commented out for initial deployment - can be added later
-- Insert a system user for system messages
-- INSERT INTO users (id, username, email, hashed_password, full_name, is_active, is_verified)
-- VALUES (
--     '00000000-0000-0000-0000-000000000000',
--     'system',
--     'system@signalink.local',
--     '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5ojg.dQE2fDDO', -- dummy hash
--     'System',
--     TRUE,
--     TRUE
-- );

-- Create a general channel
-- INSERT INTO channels (name, description, is_private, created_by)
-- VALUES (
--     'general',
--     'General discussion channel',
--     FALSE,
--     '00000000-0000-0000-0000-000000000000'
-- );

-- ====================================
-- COMMENTS AND DOCUMENTATION
-- ====================================

COMMENT ON TABLE users IS 'Stores user account information';
COMMENT ON TABLE channels IS 'Stores channel/room information';
COMMENT ON TABLE channel_members IS 'Maps users to channels with roles';
COMMENT ON TABLE messages IS 'Stores all messages with soft delete support';
COMMENT ON TABLE message_reactions IS 'Stores emoji reactions to messages';
COMMENT ON TABLE read_receipts IS 'Tracks last read message per user per channel';
COMMENT ON TABLE user_sessions IS 'Tracks JWT sessions for revocation and auditing';
COMMENT ON TABLE notification_preferences IS 'User notification settings';
COMMENT ON TABLE analytics_events IS 'Stores events for analytics processing';

-- ====================================
-- MAINTENANCE QUERIES (for reference)
-- ====================================

-- Clean up expired sessions (run periodically)
-- DELETE FROM user_sessions WHERE expires_at < NOW();

-- Get unread message count for a user in a channel
-- SELECT COUNT(*) FROM messages m
-- LEFT JOIN read_receipts rr ON rr.channel_id = m.channel_id AND rr.user_id = $user_id
-- WHERE m.channel_id = $channel_id
-- AND (rr.last_read_at IS NULL OR m.created_at > rr.last_read_at);
