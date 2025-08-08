-- Hebrew AI Call Center CRM - Tasks, Notifications & Timeline Migration
-- מיגרציית משימות, התראות וטיימליין למערכת CRM

-- Tasks table for task management
CREATE TABLE IF NOT EXISTS tasks (
    id BIGSERIAL PRIMARY KEY,
    business_id BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    title TEXT NOT NULL,
    notes TEXT,
    channel VARCHAR(16) NOT NULL CHECK (channel IN ('call','whatsapp','meeting','email','sms')),
    due_at TIMESTAMPTZ NOT NULL,
    assignee_user_id BIGINT,
    status VARCHAR(16) NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_progress','completed','cancelled','overdue')),
    priority VARCHAR(16) NOT NULL DEFAULT 'medium' CHECK (priority IN ('low','medium','high','urgent')),
    snooze_until TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    
    -- Foreign key constraints
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    FOREIGN KEY (assignee_user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS ix_tasks_due ON tasks(due_at);
CREATE INDEX IF NOT EXISTS ix_tasks_business ON tasks(business_id);
CREATE INDEX IF NOT EXISTS ix_tasks_customer ON tasks(business_id, customer_id);
CREATE INDEX IF NOT EXISTS ix_tasks_assignee ON tasks(assignee_user_id);
CREATE INDEX IF NOT EXISTS ix_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS ix_tasks_channel ON tasks(channel);

-- Notifications table for system notifications
CREATE TABLE IF NOT EXISTS notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    task_id BIGINT,
    type VARCHAR(32) NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    data JSONB,
    delivered_at TIMESTAMPTZ,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    
    -- Foreign key constraints
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

-- Indexes for notifications
CREATE INDEX IF NOT EXISTS ix_notifications_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS ix_notifications_task ON notifications(task_id);
CREATE INDEX IF NOT EXISTS ix_notifications_type ON notifications(type);
CREATE INDEX IF NOT EXISTS ix_notifications_unread ON notifications(user_id, read_at) WHERE read_at IS NULL;

-- Web Push subscriptions for browser notifications
CREATE TABLE IF NOT EXISTS webpush_subscriptions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    endpoint TEXT NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_used_at TIMESTAMPTZ DEFAULT now(),
    
    -- Foreign key constraints
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Index for webpush subscriptions
CREATE INDEX IF NOT EXISTS ix_webpush_user ON webpush_subscriptions(user_id);

-- Customer timeline materialized view (unified activity view)
-- This combines all customer interactions into a single timeline
DROP MATERIALIZED VIEW IF EXISTS customer_timeline;

CREATE MATERIALIZED VIEW customer_timeline AS
    -- Call logs
    SELECT 
        'call'::text AS activity_type,
        business_id,
        customer_id,
        created_at AS activity_timestamp,
        call_sid::text AS reference_id,
        COALESCE(summary, 'שיחה טלפונית') AS title,
        COALESCE(transcription, '') AS description,
        to_jsonb(row(call_sid, duration, status, twilio_status)) AS metadata
    FROM call_logs
    WHERE customer_id IS NOT NULL

    UNION ALL
    
    -- WhatsApp conversations  
    SELECT 
        'whatsapp'::text AS activity_type,
        business_id,
        customer_id,
        created_at AS activity_timestamp,
        conversation_id::text AS reference_id,
        COALESCE(last_message, 'שיחת WhatsApp') AS title,
        COALESCE(last_message, '') AS description,
        to_jsonb(row(conversation_id, message_count, status)) AS metadata
    FROM whatsapp_conversations
    WHERE customer_id IS NOT NULL
    
    UNION ALL
    
    -- Tasks
    SELECT 
        'task'::text AS activity_type,
        business_id,
        customer_id,
        created_at AS activity_timestamp,
        id::text AS reference_id,
        title,
        COALESCE(notes, '') AS description,
        to_jsonb(row(id, status, priority, channel, due_at)) AS metadata
    FROM tasks
    
    UNION ALL
    
    -- Contracts (if table exists)
    SELECT 
        'contract'::text AS activity_type,
        business_id,
        customer_id,
        created_at AS activity_timestamp,
        id::text AS reference_id,
        COALESCE(title, 'חוזה דיגיטלי') AS title,
        COALESCE(description, '') AS description,
        to_jsonb(row(id, status, contract_value)) AS metadata
    FROM contracts
    WHERE customer_id IS NOT NULL
    
    UNION ALL
    
    -- Invoices (if table exists)
    SELECT 
        'invoice'::text AS activity_type,
        business_id,
        customer_id,
        created_at AS activity_timestamp,
        id::text AS reference_id,
        CONCAT('חשבונית מס׳ ', invoice_number) AS title,
        COALESCE(description, '') AS description,
        to_jsonb(row(id, status, total_amount, invoice_number)) AS metadata
    FROM invoices
    WHERE customer_id IS NOT NULL;

-- Index for the materialized view
CREATE UNIQUE INDEX IF NOT EXISTS ix_timeline_unique ON customer_timeline 
    (business_id, customer_id, activity_timestamp, activity_type, reference_id);

CREATE INDEX IF NOT EXISTS ix_timeline_business_customer ON customer_timeline 
    (business_id, customer_id, activity_timestamp DESC);

CREATE INDEX IF NOT EXISTS ix_timeline_type ON customer_timeline 
    (activity_type, business_id, customer_id);

-- Function to refresh the materialized view
CREATE OR REPLACE FUNCTION refresh_customer_timeline()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY customer_timeline;
END;
$$ LANGUAGE plpgsql;

-- Trigger function to update tasks updated_at timestamp
CREATE OR REPLACE FUNCTION update_task_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically update updated_at
DROP TRIGGER IF EXISTS tasks_updated_at_trigger ON tasks;
CREATE TRIGGER tasks_updated_at_trigger
    BEFORE UPDATE ON tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_task_updated_at();

-- Function to create task notification
CREATE OR REPLACE FUNCTION create_task_notification()
RETURNS TRIGGER AS $$
BEGIN
    -- Create notification for new tasks
    IF TG_OP = 'INSERT' THEN
        INSERT INTO notifications (user_id, task_id, type, title, message, data)
        VALUES (
            COALESCE(NEW.assignee_user_id, 1), -- Default to admin if no assignee
            NEW.id,
            'task_created',
            'משימה חדשה נוצרה',
            NEW.title,
            to_jsonb(row(NEW.id, NEW.channel, NEW.due_at))
        );
    -- Create notification for task status changes
    ELSIF TG_OP = 'UPDATE' AND OLD.status != NEW.status THEN
        INSERT INTO notifications (user_id, task_id, type, title, message, data)
        VALUES (
            COALESCE(NEW.assignee_user_id, OLD.assignee_user_id, 1),
            NEW.id,
            'task_status_changed',
            'סטטוס משימה השתנה',
            CONCAT(NEW.title, ' - ', NEW.status),
            to_jsonb(row(NEW.id, OLD.status, NEW.status))
        );
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Trigger for task notifications
DROP TRIGGER IF EXISTS task_notification_trigger ON tasks;
CREATE TRIGGER task_notification_trigger
    AFTER INSERT OR UPDATE ON tasks
    FOR EACH ROW
    EXECUTE FUNCTION create_task_notification();

-- Add some helpful views for common queries
CREATE OR REPLACE VIEW active_tasks AS
SELECT 
    t.*,
    c.name as customer_name,
    c.phone as customer_phone,
    u.username as assignee_name
FROM tasks t
LEFT JOIN customers c ON t.customer_id = c.id
LEFT JOIN users u ON t.assignee_user_id = u.id
WHERE t.status IN ('open', 'in_progress')
ORDER BY t.due_at ASC;

CREATE OR REPLACE VIEW overdue_tasks AS
SELECT 
    t.*,
    c.name as customer_name,
    c.phone as customer_phone,
    u.username as assignee_name,
    (now() - t.due_at) as overdue_duration
FROM tasks t
LEFT JOIN customers c ON t.customer_id = c.id
LEFT JOIN users u ON t.assignee_user_id = u.id
WHERE t.due_at < now() AND t.status IN ('open', 'in_progress')
ORDER BY t.due_at ASC;

CREATE OR REPLACE VIEW task_summary_by_user AS
SELECT 
    u.username,
    COUNT(*) FILTER (WHERE t.status = 'open') as open_tasks,
    COUNT(*) FILTER (WHERE t.status = 'in_progress') as in_progress_tasks,
    COUNT(*) FILTER (WHERE t.status = 'completed') as completed_tasks,
    COUNT(*) FILTER (WHERE t.due_at < now() AND t.status IN ('open', 'in_progress')) as overdue_tasks
FROM users u
LEFT JOIN tasks t ON u.id = t.assignee_user_id
GROUP BY u.id, u.username;