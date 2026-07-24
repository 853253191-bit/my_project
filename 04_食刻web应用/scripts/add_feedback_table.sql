-- 用户推荐反馈表（可在生产库直接执行）
-- 用法：sqlite3 /opt/shike/backend/data/sqlite/recipes.db < scripts/add_feedback_table.sql

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    user_id TEXT,
    recipe_id TEXT,
    query_text TEXT,
    filters TEXT,
    rating TEXT,
    comment TEXT,
    client_ip TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feedback_recipe_id ON feedback(recipe_id);
CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback(rating);
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at);
