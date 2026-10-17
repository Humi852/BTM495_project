--1.User table 
CREATE TABLE IF NOT EXISTS user (
    user_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    phone TEXT,
    address TEXT,
    password_hash TEXT,
    is_admin INTEGER DEFAULT 0
);
-- 2. Event Table
CREATE TABLE event (
    event_id INTEGER PRIMARY KEY,
    admin_id INTEGER,
    name TEXT NOT NULL,
    description TEXT,
    eventDateTime DATETIME,
    participantLimit INTEGER,
    FOREIGN KEY (admin_id) REFERENCES user(user_id)    
);

--3. Appointment Table
CREATE TABLE appointment (
    appointment_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    appointmentTime DATETIME,
    FOREIGN KEY (user_id) REFERENCES user(user_id)
 );   

--4. Item Table
CREATE TABLE item (
    item_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    sellingprice REAL,
    costprice REAL,
    stock_quantity INTEGER
 );   

 --5. Order Table
CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    orderDateTime DATETIME,
    totalAmount REAL,
    FOREIGN KEY (user_id) REFERENCES user(user_id)
 ); 

   --6. Payment Table
CREATE TABLE payment (
    payment_id INTEGER PRIMARY KEY,
    order_id INTEGER,
    paymentDateTime DATETIME,
    amount REAL,
    paymentMethod TEXT,
    paidstatus BOOLEAN,
    details TEXT,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
 ); 
    FOREIGN KEY (user_id) REFERENCES user(user_id)
 ); 