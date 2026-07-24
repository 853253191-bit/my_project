-- 站点意见反馈表（与推荐菜品 feedback 分离）
CREATE TABLE IF NOT EXISTS site_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    contact TEXT,
    category TEXT DEFAULT '建议',
    user_id TEXT,
    username TEXT,
    client_ip TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_site_feedback_status ON site_feedback(status);
CREATE INDEX IF NOT EXISTS idx_site_feedback_created_at ON site_feedback(created_at);
