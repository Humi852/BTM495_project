# LPVR Python prototype

Generated from the Visual Paradigm model. Contains Python class scaffolds, their attributes, UML method placeholders, and inheritance links.

## Run the Python prototype
```bash
python main.py
```

## Run the local web integration test

The local test page checks that the page, its API, and the SQLite database can
communicate. It uses Python's standard library; no package installation is
needed.

1. From the project root, run:

   ```bash
   python localteststart.py
   ```

2. The launcher starts a server bound to this computer and opens the page in
   Google Chrome when Chrome is detected. If it does not open automatically,
   enter this URL in Chrome:

   ```text
   http://localhost:8765/
   ```

3. The page reports database connectivity and the number of rows in each
   application table. Select **Run test again** to repeat the check.
4. Press `Ctrl+C` in the terminal to stop the local server.

The page calls `GET /api/status`. This is a read-only smoke test: it does not
initialize the database or create, update, or delete records. To use another
port, run `python localteststart.py --port 8766`; the URL will use that port.

Run the API tests separately with:

```bash
python -m unittest discover -s tests
```

## Important
- Method bodies intentionally raise `NotImplementedError`.
- The SQLite schema is a starter example, **not** a complete model-to-table conversion.
- UML association/composition multiplicities are not implemented as ORM relations.
- Attribute types and names may require refinement; passwords should be stored as secure hashes, not plain text.
- Classes such as Database and service classes were kept because they occur in the source UML, but may not represent persistent database tables.

## Inheritance extracted
- Administrator inherits User
- Customer inherits User
- Part inherits Item
- Bicycle inherits Item
