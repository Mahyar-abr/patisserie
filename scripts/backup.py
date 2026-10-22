"""Copie SQLite cohérente sans arrêter le site : python scripts/backup.py DESTINATION"""
import os, sqlite3, sys
from pathlib import Path
if len(sys.argv)!=2: raise SystemExit('Usage: python scripts/backup.py /app/data/backup.sqlite3')
source=Path(os.getenv('DB_PATH','db.sqlite3'))
dest=Path(sys.argv[1])
if not source.exists(): raise SystemExit('Base introuvable')
if dest.resolve()==source.resolve(): raise SystemExit('La destination doit être différente')
with sqlite3.connect(source) as db, sqlite3.connect(dest) as backup: db.backup(backup)
print(dest)
