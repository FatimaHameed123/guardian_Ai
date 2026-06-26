import sqlite3
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "CriminalInvestigation_Secured.db"
print("path:", p)
print("exists:", p.exists())
if p.exists():
    print("size:", p.stat().st_size)
    c = sqlite3.connect(p)
    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    print("tables:", tables)
    if "Criminal_Cases" in tables:
        print("cases:", c.execute("SELECT COUNT(*) FROM Criminal_Cases").fetchone()[0])
