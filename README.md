# BTM 495 Project

## Project overview

This project is a website for a bike shop. It is designed to help customers
and administrators manage user profiles, events, appointments, orders,
payments, and inventory. Administrators manage the shop's information and
operations, while customers use the website to access shop services.

The team developed the code in Python, using its UML class design as a guide
for classes, attributes, and methods. The project was not generated from a
Visual Paradigm model.

SQLite provides the database. Its tables are defined in
`database/schema.sql`, and `database/sqlite_database.py` initializes the
database file at `database/lpvr.db`.

## Project structure

- `backend/models/` contains Python classes for the project concepts, such as
  users, events, appointments, orders, carts, inventory, items, and payments.
- `backend/apis/` contains the local website API and focused application
  operations for profiles, shopping-cart persistence, ordering, and payments.
- `backend/utils/` contains shared SQLite query/transaction, validation,
  logging, HTTP request/response helpers, operation responses, and schema
  identifier constants.
- `database/schema.sql` defines the SQLite tables.
- `database/sqlite_database.py` initializes the database from its schema.
- `shopping_cart` stores one active cart per customer as JSON item IDs,
  quantities, and unit-price snapshots; successful database checkout clears it
  in the same transaction as the order and inventory updates.
- `ShoppingCart` in `backend/models/shopping_cart.py` contains in-memory cart
  behavior; `ShoppingCartAPI` in `backend/apis/shopping_cart_api.py` handles
  loading and persisting that cart.
- Domain operations return `Response` values with a message, severity,
  success flag, and optional data instead of bare status strings.
- `admin` and `customer` store their own profile records. `User` is the shared
  in-memory base type; `Admin` and `Customer` are its role-specific types.
- Checked-out cart contents are stored in `order_item`, including each
  item's quantity and checkout-time unit-price snapshot. The order operations
  in `backend/apis/order_api.py` persist the order and lines, decrement
  available database stock, and clear the cart only after the transaction
  succeeds.
- `frontend/` contains the website HTML, CSS, and JavaScript.
- `tests/` contains the website tests. `tests/unitTests/` contains SQLite
  schema, payment API, profile API, order API, and domain-model tests, along
  with the manual cash-payment demo.
- `main.py` runs the command-line payment example.
- `run_local_website.py` starts the local website.

User profile creation and updates are supported through `ManageProfile`.
`createAccount` hashes the supplied password with PBKDF2 before storing it in
the `password_hash` column. `login` checks both Admin and Customer accounts
using only email and password; it returns the account only when exactly one
role matches. Passwords must be at least eight characters.

## Run the Python payment example

From the project root, run:

```powershell
python main.py
```

Follow the prompts to choose credit-card payment or cash payment. This is a
mock payment flow; it does not contact a bank.

## Run the local website

From the project root, run:

```powershell
python run_local_website.py
```

The launcher starts a local server and attempts to open the site in your
default browser. If it does not open automatically, visit:

```text
http://localhost:8765/
```

The page shows the SQLite table names, orders, and existing payment history.
Use **Test profile login** with the local demo credentials
`login@example.com` / `1234`, or with another existing Admin or Customer
account. The launcher creates the demo Customer account if it is missing and
does not replace an existing account with that email. This deliberately weak
password is for the local dry-run only; keep the server bound to loopback and
do not reuse it elsewhere. The form reports whether the credentials match;
it does not create a persistent signed-in session.

The server console reports startup steps (database initialization and server
readiness), concise request durations, and human-readable summaries of backend
inputs, outputs, and SQL query results. It does not print raw JSON payloads or
bound SQL values. HTTP status codes are shown as readable descriptions, and
warning/error messages are colored in terminals that support ANSI colors.
Verbose default HTTP access lines are suppressed.

Select **Make a payment** to open the payment form. If there is no unpaid
order, the website creates a $50 sample order in SQLite so that you can try
the form. The sample order remains in the database.

Only the card number `4242424242424242` is approved by the mock gateway. Use a
valid expiration date in `MM/YY` format and a three-digit security code. Other
card numbers are declined. When a payment is declined, the form explains the
result and the order remains unpaid.

Payment attempts and card details are not stored in the database. No external
bank or payment service is contacted. Press `Ctrl+C` in the server terminal to
stop the website. To use a different port, for example, run:

```powershell
python run_local_website.py --port 8766
```

## Run the tests

Run the local website tests:

```powershell
python -m unittest discover -s tests -p "test_local_website_api.py"
```

Run the payment, user-profile, and domain-model unit tests, followed by the
admin cash-payment demo:

```powershell
python tests\unitTests\run_unit_tests.py
```

The second command prints the unit-test pass count, then shows the manual cash
payment moving from **Pending** to **Paid** after admin confirmation.
