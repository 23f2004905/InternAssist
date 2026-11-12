-- Apply once to an existing PostgreSQL database before deploying this release.
-- Rollback: DROP TABLE IF EXISTS document_files;
CREATE TABLE IF NOT EXISTS document_files (
    document_id INTEGER PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    content BYTEA NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
