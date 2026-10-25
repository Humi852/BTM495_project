PRAGMA foreign_keys = ON;

-- 1. Admin Table
CREATE TABLE IF NOT EXISTS admin (
    admin_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    phone TEXT,
    address TEXT,
    password_hash TEXT
);

--2. Customer Table
CREATE TABLE IF NOT EXISTS customer (
    customer_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    phone TEXT,
    address TEXT,
    password_hash TEXT
);
-- Prevent duplicate email entries for admin and customer tables
DROP TRIGGER IF EXISTS admin_email_insert_unique;
DROP TRIGGER IF EXISTS admin_email_update_unique;
DROP TRIGGER IF EXISTS customer_email_insert_unique;
DROP TRIGGER IF EXISTS customer_email_update_unique;

-- Status Table: statusID values are scoped by category so each table can only use its own statuses.
CREATE TABLE IF NOT EXISTS status (
    statusID INTEGER PRIMARY KEY,
    category TEXT NOT NULL CHECK (category IN ('event','appointment','order','payment')),
    name TEXT NOT NULL,
    UNIQUE (category, name),
    UNIQUE (statusID, category)  -- Ensure statusID is unique within each category
);


INSERT OR IGNORE INTO status (statusID, category, name) VALUES
-- Event Statuses
    (1, 'event', 'Scheduled'),
    (2, 'event', 'Completed'),
    (3, 'event', 'Cancelled'),
-- Appointment Statuses
    (4, 'appointment', 'Booked'),
    (5, 'appointment', 'Cancelled'),
    (6, 'appointment', 'Completed'),
-- Order Statuses
    (7, 'order', 'Pending'),
    (8, 'order', 'Cancelled'),
    (9, 'order', 'Completed'),
-- Payment Statuses
    (10, 'payment', 'Pending'),
    (11, 'payment', 'Paid'),
    (12, 'payment', 'Failed');

-- 3. Event Table
CREATE TABLE IF NOT EXISTS event (
    event_id INTEGER PRIMARY KEY,
    admin_id INTEGER,
    location TEXT,
    name TEXT NOT NULL,
    description TEXT,
    eventDateTime DATETIME,
    participantLimit INTEGER NOT NULL DEFAULT 0 CHECK (participantLimit >= 0),
    statusID INTEGER,
    category TEXT NOT NULL DEFAULT 'event' CHECK (category = 'event'),
    FOREIGN KEY (admin_id) REFERENCES admin(admin_id),
    FOREIGN KEY (statusID, category) REFERENCES status(statusID, category)
);

-- Event Registration Table: tracks which customers joined which events.
CREATE TABLE IF NOT EXISTS event_registration (
    event_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    PRIMARY KEY (event_id, customer_id),
    FOREIGN KEY (event_id) REFERENCES event(event_id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id) ON DELETE CASCADE
);

-- 4. Appointment Table
CREATE TABLE IF NOT EXISTS appointment (
    appointment_id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    appointmentTime DATETIME,
    description TEXT,
    statusID INTEGER,
    category TEXT NOT NULL DEFAULT 'appointment' CHECK (category = 'appointment'),
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    FOREIGN KEY (statusID, category) REFERENCES status(statusID, category)
);

-- 5. Order Table
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    orderDateTime DATETIME,
    totalAmount REAL,
    statusID INTEGER,
    category TEXT NOT NULL DEFAULT 'order' CHECK (category = 'order'),
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    FOREIGN KEY (statusID, category) REFERENCES status(statusID, category)
);

-- 6. Item Table
CREATE TABLE IF NOT EXISTS item (
    item_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    price REAL,
    category TEXT,
    brand TEXT
);

-- Current stock per item. An item without a row here is not stock-tracked (e.g. a service).
CREATE TABLE IF NOT EXISTS inventory (
    item_id INTEGER PRIMARY KEY,
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now')),
    admin_id INTEGER,  -- last admin to change it; NULL for system changes such as checkout
    FOREIGN KEY (item_id) REFERENCES item(item_id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES admin(admin_id) ON DELETE SET NULL
);

-- Append-only audit trail: one row per quantity change.
CREATE TABLE IF NOT EXISTS inventory_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    old_quantity INTEGER,  -- NULL when tracking starts
    new_quantity INTEGER,  -- NULL when tracking stops
    admin_id INTEGER,      -- NULL for system changes such as checkout
    reason TEXT,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (item_id) REFERENCES item(item_id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES admin(admin_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_inventory_history_item ON inventory_history(item_id, created_at);

-- Persist each customer's active cart as a JSON array of item IDs and quantities.
CREATE TABLE IF NOT EXISTS shopping_cart (
    customer_id INTEGER PRIMARY KEY,
    items_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(items_json)),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id) ON DELETE CASCADE
);

-- 7. Order_Item Table
CREATE TABLE IF NOT EXISTS order_item (
    order_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price REAL NOT NULL CHECK (unit_price >= 0),
    PRIMARY KEY (order_id, item_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES item(item_id)
);

-- 8. Payment Table
CREATE TABLE IF NOT EXISTS payment (
    payment_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    paymentDateTime DATETIME NOT NULL,
    amount REAL NOT NULL CHECK (amount > 0),
    paymentMethod TEXT NOT NULL,
    statusID INTEGER NOT NULL,
    category TEXT NOT NULL DEFAULT 'payment' CHECK (category = 'payment'),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (statusID, category) REFERENCES status(statusID, category)
);
