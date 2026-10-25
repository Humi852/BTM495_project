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

-- 3. Event Table
CREATE TABLE IF NOT EXISTS event (
    event_id INTEGER PRIMARY KEY,
    admin_id INTEGER,
    name TEXT NOT NULL,
    description TEXT,
    eventDateTime DATETIME,
    participantLimit INTEGER,
    participantCount INTEGER,
    statusID INTEGER,
    FOREIGN KEY (admin_id) REFERENCES admin(admin_id)
);

-- 4. Appointment Table
CREATE TABLE IF NOT EXISTS appointment (
    appointment_id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    appointmentTime DATETIME,
    description TEXT,
    statusID INTEGER,
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
);

-- 5. Order Table
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    orderDateTime DATETIME,
    totalAmount REAL,
    statusID INTEGER,
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
);

-- 6. Item Table
CREATE TABLE IF NOT EXISTS item (
    item_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    price REAL,
    category TEXT,
    brand TEXT,
    stock_quantity INTEGER
);

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
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);
