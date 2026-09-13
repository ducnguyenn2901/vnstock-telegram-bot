import sqlite3
import os
import pandas as pd
from config import BASE_DIR

DB_PATH = os.path.join(BASE_DIR, "bot_database.db")

def init_db():
    """Khởi tạo cấu trúc cơ sở dữ liệu"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Bảng lưu trữ cảnh báo
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            condition_type TEXT NOT NULL,
            operator TEXT NOT NULL,
            target_value REAL NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Bảng người dùng (optional, cho tương lai)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            tier TEXT DEFAULT 'free',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Bảng danh mục đầu tư (Portfolio)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            buy_price REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_alerted INTEGER DEFAULT 0
        )
    ''')
    
    # Bảng lưu trữ dữ liệu giá lịch sử
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            symbol TEXT,
            date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            PRIMARY KEY (symbol, date)
        )
    ''')
    
    conn.commit()
    conn.close()

def save_price_history(df):
    """Lưu dataframe giá lịch sử vào DB"""
    if df is None or df.empty:
        return
    conn = sqlite3.connect(DB_PATH)
    df.to_sql('price_history', conn, if_exists='append', index=False)
    conn.close()

def get_all_price_history(symbols=None):
    """Lấy dữ liệu giá lịch sử. Nếu symbols=None, lấy toàn bộ."""
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT * FROM price_history"
    if symbols:
        placeholders = ','.join('?' for _ in symbols)
        query += f" WHERE symbol IN ({placeholders})"
        df = pd.read_sql_query(query, conn, params=symbols)
    else:
        df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def add_alert(user_id: int, symbol: str, condition_type: str, operator: str, target_value: float):
    """Thêm một cảnh báo mới"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO alerts (user_id, symbol, condition_type, operator, target_value)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, symbol.upper(), condition_type.lower(), operator, target_value))
    conn.commit()
    alert_id = cursor.lastrowid
    conn.close()
    return alert_id

def get_active_alerts(user_id: int = None):
    """Lấy danh sách cảnh báo đang hoạt động. Có thể lọc theo user_id"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if user_id:
        cursor.execute('SELECT * FROM alerts WHERE user_id = ? AND is_active = 1', (user_id,))
    else:
        cursor.execute('SELECT * FROM alerts WHERE is_active = 1')
        
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def remove_alert(alert_id: int, user_id: int):
    """Xóa (hoặc vô hiệu hóa) một cảnh báo"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE alerts SET is_active = 0 WHERE id = ? AND user_id = ?', (alert_id, user_id))
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0

def deactivate_alert(alert_id: int):
    """Vô hiệu hóa một cảnh báo sau khi đã trigger"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE alerts SET is_active = 0 WHERE id = ?', (alert_id,))
    conn.commit()
    conn.close()

def buy_stock(user_id: int, symbol: str, quantity: int, buy_price: float):
    """Thêm một giao dịch mua vào danh mục. Trả về id."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO portfolio (user_id, symbol, quantity, buy_price)
        VALUES (?, ?, ?, ?)
    ''', (user_id, symbol.upper(), quantity, buy_price))
    conn.commit()
    record_id = cursor.lastrowid
    conn.close()
    return record_id

def get_portfolio(user_id: int):
    """Lấy danh sách các mã đang giữ của user."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM portfolio WHERE user_id = ? AND quantity > 0', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def sell_stock(user_id: int, symbol: str, sell_qty: int):
    """Bán cổ phiếu (giảm khối lượng). Trả về số lượng còn lại chưa bán được."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM portfolio WHERE user_id = ? AND symbol = ? AND quantity > 0 ORDER BY created_at ASC', (user_id, symbol.upper()))
    rows = cursor.fetchall()
    
    remaining_to_sell = sell_qty
    for row in rows:
        if remaining_to_sell <= 0:
            break
            
        r_id = row['id']
        r_qty = row['quantity']
        
        if r_qty <= remaining_to_sell:
            cursor.execute('UPDATE portfolio SET quantity = 0 WHERE id = ?', (r_id,))
            remaining_to_sell -= r_qty
        else:
            new_qty = r_qty - remaining_to_sell
            cursor.execute('UPDATE portfolio SET quantity = ? WHERE id = ?', (new_qty, r_id))
            remaining_to_sell = 0
            
    conn.commit()
    conn.close()
    return remaining_to_sell

if __name__ == "__main__":
    init_db()
    print(f"Cơ sở dữ liệu đã được khởi tạo tại: {DB_PATH}")
