"""
SQLite database module for GST HSN product lookup.
Stores product names, categories, 4-digit HSN, 8-digit HSN, and source URLs.
"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

DB_DIR = Path(__file__).parent.parent.parent / "data" / "db"
DB_PATH = DB_DIR / "gst_hsn.db"


def init_db():
    """Initialize SQLite database with products table."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT,
            hsn_4digit TEXT,
            hsn_8digit TEXT,
            source_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)
    """)
    
    conn.commit()
    conn.close()


def insert_product(
    name: str,
    category: Optional[str] = None,
    hsn_4digit: Optional[str] = None,
    hsn_8digit: Optional[str] = None,
    source_url: Optional[str] = None
) -> bool:
    """
    Insert a product into the database.
    Returns True if successful, False if product already exists.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO products (name, category, hsn_4digit, hsn_8digit, source_url)
            VALUES (?, ?, ?, ?, ?)
        """, (name.strip(), category, hsn_4digit, hsn_8digit, source_url))
        
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Product name already exists
        return False
    finally:
        conn.close()


def update_product(
    name: str,
    category: Optional[str] = None,
    hsn_4digit: Optional[str] = None,
    hsn_8digit: Optional[str] = None,
    source_url: Optional[str] = None
) -> bool:
    """
    Update an existing product. Returns True if successful.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE products
        SET category = COALESCE(?, category),
            hsn_4digit = COALESCE(?, hsn_4digit),
            hsn_8digit = COALESCE(?, hsn_8digit),
            source_url = COALESCE(?, source_url),
            updated_at = CURRENT_TIMESTAMP
        WHERE name = ?
    """, (category, hsn_4digit, hsn_8digit, source_url, name.strip()))
    
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    
    return affected > 0


def get_product(name: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a product by exact name match.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, category, hsn_4digit, hsn_8digit, source_url, created_at
        FROM products WHERE name = ?
    """, (name.strip(),))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'id': row[0],
            'name': row[1],
            'category': row[2],
            'hsn_4digit': row[3],
            'hsn_8digit': row[4],
            'source_url': row[5],
            'created_at': row[6]
        }
    return None


def search_products(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search products by name (LIKE query).
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, category, hsn_4digit, hsn_8digit, source_url, created_at
        FROM products WHERE name LIKE ? LIMIT ?
    """, (f"%{query.strip()}%", limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        results.append({
            'id': row[0],
            'name': row[1],
            'category': row[2],
            'hsn_4digit': row[3],
            'hsn_8digit': row[4],
            'source_url': row[5],
            'created_at': row[6]
        })
    
    return results


def get_all_products(limit: int = 1000) -> List[Dict[str, Any]]:
    """
    Retrieve all products from database.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, category, hsn_4digit, hsn_8digit, source_url, created_at
        FROM products ORDER BY created_at DESC LIMIT ?
    """, (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        results.append({
            'id': row[0],
            'name': row[1],
            'category': row[2],
            'hsn_4digit': row[3],
            'hsn_8digit': row[4],
            'source_url': row[5],
            'created_at': row[6]
        })
    
    return results


def delete_product(name: str) -> bool:
    """
    Delete a product by name. Returns True if successful.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM products WHERE name = ?", (name.strip(),))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    
    return affected > 0


def product_exists(name: str) -> bool:
    """
    Check if product exists in database.
    """
    return get_product(name.strip()) is not None


def get_total_count() -> int:
    """
    Get total number of products in database.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM products")
    count = cursor.fetchone()[0]
    conn.close()
    
    return count


# Initialize DB on module load
init_db()
