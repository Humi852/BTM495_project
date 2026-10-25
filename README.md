# BTM 495 Project

## Quick start

**Step 1. Clone the project**

```
git clone https://github.com/Humi852/BTM495_project.git
cd BTM495_project
```

**Step 2. Run the setup script (one line)**

It creates the Python environment (skipped if it already exists), starts the
local website, and opens it in your browser. Requires Python 3.10 or newer.

Windows:

```
setup.bat
```

macOS / Linux:

```
bash setup.sh
```

Press `Ctrl+C` in the terminal to stop the server. If the browser does not
open, go to `http://localhost:8765/`.

**Step 3. Try the features in the browser**

| Section on the page | What to try |
| --- | --- |
| Test profile login | Log in with `login@example.com` / `1234`. |
| Database structure | See all tables and row counts. `status` has 3 rows: Pending, Completed, Cancelled. Click **Refresh data** to reload. |
| Orders | Click **Make a payment** to create a $50 sample order. Use the edit and delete icons on a row, or **Remove all orders**. |
| Mock credit card | The form is prefilled with a valid test card. Click **Review payment** and confirm. Any other card number is declined. |
| Payment history | See paid payments. Use the edit and delete icons, or **Remove all payments**. |
| Inventory | Click **Save item** to add or update an item. Click the history icon to see stock changes (who, when, why). Use the delete icon to remove it. |
| Event registration | Click **Add sample event (limit 2)**, then register customer IDs until it is full. Duplicate and over-limit registrations are rejected. Unregister with the `🗑 #id` button. |

No real payment is made and card details are never stored.

## Run the tests

```
python -m unittest discover -s tests -p "test_*.py"
```

The last line should say `OK`. Warning and error log lines in the middle of
the run are expected. The tests use temporary databases, so they do not change
your data.

## Other

- Delete `database/lpvr.db` (after stopping the server) to start with a fresh
  database.
- Use another port with `bash setup.sh --port 8766` or
  `setup.bat --port 8766`.
- A single shared `status` table (`1 = Pending`, `2 = Completed`,
  `3 = Cancelled`) is used by events, appointments, orders, and payments. See
  `StatusID` in `backend/utils/constants.py`.
- `python main.py` runs the command-line mock payment example.

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
