"""SQLite database for template metadata."""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "templates.db"

POS_GRADUACOES = [
    "Medicina Funcional Integrativa",
    "Suplementação Pediátrica",
    "Endocrinologia",
    "Metabolômica",
    "Suplementação",
    "Medicina Esportiva e do Exercício",
    "Saúde Gastrointestinal",
    "Autismo e TDAH",
    "Saúde Mental",
    "Nutrição Funcional Integrativa",
    "Emagrecimento e Obesidade",
]

VARIANTS = ["azul", "verde"]


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                filename  TEXT NOT NULL UNIQUE,
                name      TEXT NOT NULL,
                config    TEXT NOT NULL DEFAULT '{}',
                category  TEXT NOT NULL DEFAULT '',
                variant   TEXT NOT NULL DEFAULT '',
                is_verso  INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Migrate existing DBs that lack the new columns
        existing = {r[1] for r in con.execute("PRAGMA table_info(templates)")}
        for col, definition in [
            ("category", "TEXT NOT NULL DEFAULT ''"),
            ("variant",  "TEXT NOT NULL DEFAULT ''"),
            ("is_verso", "INTEGER NOT NULL DEFAULT 0"),
        ]:
            if col not in existing:
                con.execute(f"ALTER TABLE templates ADD COLUMN {col} {definition}")


# ── CRUD ──────────────────────────────────────────────────────────────────

def add_template(filename: str, name: str, category: str = "", variant: str = "", is_verso: bool = False) -> dict:
    with _conn() as con:
        cur = con.execute(
            "INSERT OR REPLACE INTO templates (filename, name, config, category, variant, is_verso) VALUES (?,?,?,?,?,?)",
            (filename, name, "{}", category, variant, int(is_verso)),
        )
        return get_template(cur.lastrowid)


def list_templates() -> list[dict]:
    with _conn() as con:
        rows = con.execute("SELECT * FROM templates ORDER BY category, variant, id").fetchall()
    return [_row_to_dict(r) for r in rows]


def get_template(template_id: int) -> dict | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM templates WHERE id = ?", (template_id,)).fetchone()
    return _row_to_dict(row) if row else None


def get_verso_for(category: str, variant: str) -> dict | None:
    """Return the verso template for a specific category+variant pair."""
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM templates WHERE category = ? AND variant = ? AND is_verso = 1 LIMIT 1",
            (category, variant),
        ).fetchone()
    return _row_to_dict(row) if row else None


def update_config(template_id: int, config: dict) -> dict | None:
    with _conn() as con:
        con.execute("UPDATE templates SET config = ? WHERE id = ?", (json.dumps(config), template_id))
    return get_template(template_id)


def delete_template(template_id: int) -> bool:
    with _conn() as con:
        cur = con.execute("DELETE FROM templates WHERE id = ?", (template_id,))
    return cur.rowcount > 0


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["config"] = json.loads(d["config"])
    d["is_verso"] = bool(d["is_verso"])
    return d
