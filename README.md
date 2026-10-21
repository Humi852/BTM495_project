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
`database/schema.sql`, and `database/db.py` initializes the database file at
`database/lpvr.db`.

## Project structure

- `backend/models/` contains Python classes for the project concepts, such as
  users, events, orders, carts, items, and payments.
- `backend/services/` contains service logic for user profiles, inventory, and
  payments. Inventory management operates on the domain types in
  `backend/models/`.
- `backend/apis/local_test.py` serves the local website and its API.
- `database/schema.sql` defines the SQLite tables.
- `database/db.py` initializes the database.
- `frontend/` contains the website HTML, CSS, and JavaScript.
- `tests/` contains the website tests. `tests/unitTests/` contains the payment
  and user-profile unit tests, domain-model tests, and the manual cash-payment
  demo.
- `main.py` runs the command-line payment example.
- `testInLocalWebPage.py` starts the local website.

User profile creation is supported through `UserService`. Password handling
and authentication are outside the current application scope.

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
python testInLocalWebPage.py
```

The launcher starts a local server and attempts to open the site in your
default browser. If it does not open automatically, visit:

```text
http://localhost:8765/
```

The page shows the SQLite table names, orders, and existing payment history.
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
python testInLocalWebPage.py --port 8766
```

## Run the tests

Run the local website tests:

```powershell
python -m unittest discover -s tests -p "test_localDryrunWebsite.py"
```

Run the payment, user-profile, and domain-model unit tests, followed by the
admin cash-payment demo:

```powershell
python tests\unitTests\runAllUnitTests.py
```

The second command prints the unit-test pass count, then shows the manual cash
payment moving from **Pending** to **Paid** after admin confirmation.
