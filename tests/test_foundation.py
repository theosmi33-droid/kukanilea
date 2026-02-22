from app.database import DB_PATH, get_db_connection, init_db


def test_database_initialization():
    """Verifiziert, dass die DB erstellt wird und FTS5 verfügbar ist."""
    if DB_PATH.exists():
        DB_PATH.unlink()
    
    init_db()
    assert DB_PATH.exists()
    
    conn = get_db_connection()
    # Prüfe ob FTS5 Tabelle existiert
    res = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='knowledge_search';").fetchone()
    assert res is not None
    
    # Teste FTS5 Insert/Search
    conn.execute("INSERT INTO knowledge_search (title, content) VALUES ('Test Doc', 'Handwerk ist toll');")
    conn.commit()
    
    search = conn.execute("SELECT title FROM knowledge_search WHERE knowledge_search MATCH 'Handwerk';").fetchone()
    assert search['title'] == 'Test Doc'
    conn.close()
