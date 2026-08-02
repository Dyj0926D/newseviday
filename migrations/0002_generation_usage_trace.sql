ALTER TABLE generation_requests ADD COLUMN trace_id TEXT;
ALTER TABLE generation_requests ADD COLUMN provider TEXT;
ALTER TABLE generation_requests ADD COLUMN model TEXT;
ALTER TABLE generation_requests ADD COLUMN prompt_tokens INTEGER CHECK (prompt_tokens IS NULL OR prompt_tokens >= 0);
ALTER TABLE generation_requests ADD COLUMN completion_tokens INTEGER CHECK (completion_tokens IS NULL OR completion_tokens >= 0);
ALTER TABLE generation_requests ADD COLUMN total_tokens INTEGER CHECK (total_tokens IS NULL OR total_tokens >= 0);

CREATE INDEX IF NOT EXISTS generation_requests_trace
ON generation_requests (trace_id);
