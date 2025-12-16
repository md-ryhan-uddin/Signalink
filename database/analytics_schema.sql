-- Analytics Service Database Schema
-- Phase 4: Real-time Metrics and Analytics

-- Message Metrics Table
CREATE TABLE IF NOT EXISTS message_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    time_window TIMESTAMP NOT NULL,
    window_duration_seconds INTEGER NOT NULL DEFAULT 60,

    -- Message stats
    message_count INTEGER NOT NULL DEFAULT 0,
    messages_per_second FLOAT NOT NULL DEFAULT 0.0,

    -- User stats
    active_users_count INTEGER NOT NULL DEFAULT 0,
    unique_senders_count INTEGER NOT NULL DEFAULT 0,

    -- Channel stats
    active_channels_count INTEGER NOT NULL DEFAULT 0,

    -- Message type breakdown
    text_messages_count INTEGER NOT NULL DEFAULT 0,
    image_messages_count INTEGER NOT NULL DEFAULT 0,
    file_messages_count INTEGER NOT NULL DEFAULT 0,
    system_messages_count INTEGER NOT NULL DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create index on time_window for fast queries
CREATE INDEX IF NOT EXISTS idx_message_metrics_time_window
    ON message_metrics(time_window, window_duration_seconds);

-- Channel Metrics Table
CREATE TABLE IF NOT EXISTS channel_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL,
    time_window TIMESTAMP NOT NULL,
    window_duration_seconds INTEGER NOT NULL DEFAULT 60,

    -- Channel activity
    message_count INTEGER NOT NULL DEFAULT 0,
    unique_senders_count INTEGER NOT NULL DEFAULT 0,
    messages_per_second FLOAT NOT NULL DEFAULT 0.0,

    -- Message operations
    created_count INTEGER NOT NULL DEFAULT 0,
    edited_count INTEGER NOT NULL DEFAULT 0,
    deleted_count INTEGER NOT NULL DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key to channels table
    FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE
);

-- Create composite index for fast channel+time queries
CREATE INDEX IF NOT EXISTS idx_channel_metrics_channel_time
    ON channel_metrics(channel_id, time_window);

-- User Metrics Table
CREATE TABLE IF NOT EXISTS user_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    time_window TIMESTAMP NOT NULL,
    window_duration_seconds INTEGER NOT NULL DEFAULT 60,

    -- User activity
    messages_sent INTEGER NOT NULL DEFAULT 0,
    messages_edited INTEGER NOT NULL DEFAULT 0,
    messages_deleted INTEGER NOT NULL DEFAULT 0,
    channels_active INTEGER NOT NULL DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key to users table
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create composite index for fast user+time queries
CREATE INDEX IF NOT EXISTS idx_user_metrics_user_time
    ON user_metrics(user_id, time_window);

-- Comments for documentation
COMMENT ON TABLE message_metrics IS 'Aggregated message metrics per time window for overall system statistics';
COMMENT ON TABLE channel_metrics IS 'Per-channel analytics metrics tracking activity over time';
COMMENT ON TABLE user_metrics IS 'Per-user analytics metrics tracking engagement and activity';

COMMENT ON COLUMN message_metrics.time_window IS 'Start timestamp of the aggregation window';
COMMENT ON COLUMN message_metrics.window_duration_seconds IS 'Duration of the time window in seconds (e.g., 60 for 1 minute)';
COMMENT ON COLUMN message_metrics.messages_per_second IS 'Average messages per second during this window';

COMMENT ON COLUMN channel_metrics.channel_id IS 'Reference to the channel being measured';
COMMENT ON COLUMN channel_metrics.unique_senders_count IS 'Number of unique users who sent messages in this channel during the window';

COMMENT ON COLUMN user_metrics.user_id IS 'Reference to the user being measured';
COMMENT ON COLUMN user_metrics.channels_active IS 'Number of unique channels the user was active in during the window';
