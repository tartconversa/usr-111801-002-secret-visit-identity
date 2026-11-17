import sqlite3


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY, owner TEXT NOT NULL, jurisdiction TEXT NOT NULL,
    classification TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
    schema_version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS fields (
    source_id TEXT NOT NULL REFERENCES sources(id), name TEXT NOT NULL,
    meaning TEXT NOT NULL, kind TEXT NOT NULL, sensitive INTEGER NOT NULL,
    PRIMARY KEY(source_id,name)
);
CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),
    schema_version INTEGER NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL,
    received_at TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS grants (
    id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),
    recipient TEXT NOT NULL, purpose TEXT NOT NULL, valid_until TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS policies (
    jurisdiction TEXT NOT NULL, classification TEXT NOT NULL, purpose TEXT NOT NULL,
    decision TEXT NOT NULL, revision INTEGER NOT NULL,
    PRIMARY KEY(jurisdiction,classification,purpose)
);
CREATE TABLE IF NOT EXISTS products (
    id TEXT NOT NULL, revision INTEGER NOT NULL, name TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL,
    PRIMARY KEY(id,revision)
);
CREATE TABLE IF NOT EXISTS product_inputs (
    product_id TEXT NOT NULL, product_revision INTEGER NOT NULL,
    asset_id TEXT NOT NULL REFERENCES assets(id),
    PRIMARY KEY(product_id,product_revision,asset_id),
    FOREIGN KEY(product_id,product_revision) REFERENCES products(id,revision)
);
CREATE TABLE IF NOT EXISTS deliveries (
    id TEXT PRIMARY KEY, product_id TEXT NOT NULL, product_revision INTEGER NOT NULL,
    recipient TEXT NOT NULL, purpose TEXT NOT NULL, created_at TEXT NOT NULL,
    input_digest TEXT NOT NULL, policy_revisions TEXT NOT NULL,
    FOREIGN KEY(product_id,product_revision) REFERENCES products(id,revision)
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, actor TEXT NOT NULL,
    action TEXT NOT NULL, subject TEXT NOT NULL, details TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS subjects (
    id TEXT PRIMARY KEY, jurisdiction TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS subject_names (
    subject_id TEXT NOT NULL REFERENCES subjects(id),
    name TEXT NOT NULL, valid_from TEXT NOT NULL, valid_to TEXT,
    PRIMARY KEY(subject_id,name,valid_from)
);
CREATE TABLE IF NOT EXISTS identity_events (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, at TEXT NOT NULL,
    actor TEXT NOT NULL, reason TEXT NOT NULL,
    from_subjects TEXT NOT NULL, to_subjects TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attributions (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES assets(id),
    subject_id TEXT NOT NULL REFERENCES subjects(id),
    claimed_name TEXT NOT NULL, basis TEXT NOT NULL, note TEXT,
    state TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL, created_by TEXT NOT NULL,
    supersedes TEXT, event_id TEXT REFERENCES identity_events(id)
);
CREATE TABLE IF NOT EXISTS response_links (
    id TEXT PRIMARY KEY,
    observation_asset_id TEXT NOT NULL REFERENCES assets(id),
    response_asset_id TEXT NOT NULL REFERENCES assets(id),
    created_at TEXT NOT NULL, created_by TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS disputes (
    id TEXT PRIMARY KEY,
    observation_asset_id TEXT NOT NULL REFERENCES assets(id),
    raised_by TEXT NOT NULL REFERENCES subjects(id),
    raised_at TEXT NOT NULL, grounds TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'open',
    decided_at TEXT, decided_by TEXT, decision_note TEXT
);
CREATE TABLE IF NOT EXISTS conclusions (
    subject_id TEXT NOT NULL REFERENCES subjects(id),
    revision INTEGER NOT NULL, summary TEXT NOT NULL,
    created_at TEXT NOT NULL, created_by TEXT NOT NULL,
    PRIMARY KEY(subject_id,revision)
);
CREATE TABLE IF NOT EXISTS conclusion_items (
    subject_id TEXT NOT NULL, revision INTEGER NOT NULL,
    observation_asset_id TEXT NOT NULL,
    attribution_id TEXT NOT NULL REFERENCES attributions(id),
    dispute_id TEXT, decision TEXT NOT NULL, reason TEXT NOT NULL,
    responses TEXT NOT NULL,
    PRIMARY KEY(subject_id,revision,observation_asset_id),
    FOREIGN KEY(subject_id,revision) REFERENCES conclusions(subject_id,revision)
);
"""


def connect(path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    return connection
