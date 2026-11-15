-- Persist structured source citations on assistant messages.
ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS citations_json TEXT NOT NULL DEFAULT '[]';
