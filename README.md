# LPVR first Python prototype

Generated from the uploaded Visual Paradigm XML. Contains 17 Python class scaffolds, their attributes, UML method placeholders, and inheritance links.

## Run
```bash
python main.py
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
