-- Enterprise Database Performance Indexes
-- אינדקסים לביצועים ברמה אנטרפרייז

-- Business table indexes for multi-tenancy
CREATE INDEX IF NOT EXISTS idx_business_active ON business(is_active);
CREATE INDEX IF NOT EXISTS idx_business_created ON business(created_at);

-- User table indexes for authentication & multi-tenant queries
CREATE INDEX IF NOT EXISTS idx_user_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_user_business_role ON users(business_id, role);
CREATE INDEX IF NOT EXISTS idx_user_enabled ON users(enabled);
CREATE INDEX IF NOT EXISTS idx_user_business_created ON users(business_id, created_at);

-- Contact table indexes for CRM performance
CREATE INDEX IF NOT EXISTS idx_contact_business_name ON contact(business_id, name);
CREATE INDEX IF NOT EXISTS idx_contact_business_created ON contact(business_id, created_at);
CREATE INDEX IF NOT EXISTS idx_contact_business_status ON contact(business_id, status);
CREATE INDEX IF NOT EXISTS idx_contact_phone ON contact(phone);

-- Call logs for real-time queries
CREATE INDEX IF NOT EXISTS idx_call_log_business_created ON call_log(business_id, created_at);
CREATE INDEX IF NOT EXISTS idx_call_log_status ON call_log(status);
CREATE INDEX IF NOT EXISTS idx_call_log_from_number ON call_log(from_number);

-- WhatsApp messages for thread performance  
CREATE INDEX IF NOT EXISTS idx_wa_message_thread_created ON whatsapp_message(thread_id, created_at);
CREATE INDEX IF NOT EXISTS idx_wa_message_business_created ON whatsapp_message(business_id, created_at);

-- Conversation turns for AI analysis
CREATE INDEX IF NOT EXISTS idx_conversation_call_created ON conversation_turn(call_log_id, created_at);

-- Invoice and contract indexes for financial operations
CREATE INDEX IF NOT EXISTS idx_invoice_business_status ON invoice(business_id, status);
CREATE INDEX IF NOT EXISTS idx_invoice_business_created ON invoice(business_id, created_at);
CREATE INDEX IF NOT EXISTS idx_contract_business_status ON contract(business_id, status);
CREATE INDEX IF NOT EXISTS idx_contract_business_created ON contract(business_id, created_at);

-- Composite indexes for complex queries
CREATE INDEX IF NOT EXISTS idx_users_business_role_enabled ON users(business_id, role, enabled);
CREATE INDEX IF NOT EXISTS idx_call_log_business_status_created ON call_log(business_id, status, created_at);

-- Audit log table and indexes (if implementing audit in DB)
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    action_type VARCHAR(50) NOT NULL,
    resource VARCHAR(50) NOT NULL,
    resource_id VARCHAR(100),
    user_id INTEGER,
    user_email VARCHAR(255),
    user_role VARCHAR(50),
    business_id INTEGER,
    ip_address VARCHAR(45),
    user_agent TEXT,
    endpoint VARCHAR(255),
    method VARCHAR(10),
    details JSONB,
    payload_hash VARCHAR(32)
);

CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_business ON audit_log(business_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_resource ON audit_log(resource, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action_type);