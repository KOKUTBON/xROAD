# Data Layout

This project keeps heavy, licensed, and sensitive data out of Git. The public repository tracks only this layout and empty placeholders.

Use the folders as follows:

- `data/external/`: locally downloaded public sources, never committed
- `data/raw/`: immutable local source extracts, never committed
- `data/staging/`: local intermediate tables, never committed
- `data/processed/`: local features and aggregate outputs, never committed

Recommended rule:

- never overwrite a source file in `data/raw/`
- record source version and extraction date in metadata files
- keep all row-level crash data, precise locations, private exports, production stores, and restricted datasets outside public Git hosting
- verify each source's terms and record attribution before using it

See [`../DATA_LICENSES.md`](../DATA_LICENSES.md) for publication rules.
