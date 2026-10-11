-- Starter table only, NOT a complete mapping of all UML classes.
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    email TEXT UNIQUE,
    phone INTEGER,
    address TEXT,
    password_hash TEXT,
    is_admin BOOLEAN
);
