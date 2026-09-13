import os
import pandas as pd
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, BigInteger, String, Float, DateTime
from sqlalchemy.sql import func
from config import BASE_DIR, DATABASE_URL
import logging

logger = logging.getLogger("Database")

DB_PATH = os.path.join(BASE_DIR, "bot_database.db")

# 1. Thiết lập Động cơ kết nối (Engine) hỗ trợ tự động Supabase hoặc SQLite
if DATABASE_URL:
    db_url = DATABASE_URL.replace("postgres://", "postgresql://")
    engine = create_engine(db_url, pool_size=10, max_overflow=20)
    logger.info("🟢 Đã kết nối với Supabase PostgreSQL (Cloud).")
else:
    engine = create_engine(f"sqlite:///{DB_PATH}")
    logger.info("🟡 Đang sử dụng SQLite cục bộ (Local).")

# 2. Định nghĩa cấu trúc các bảng (Metadata) chuẩn hóa đa nền tảng
metadata = MetaData()

alerts_table = Table(
    'alerts', metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', BigInteger, nullable=False),
    Column('symbol', String, nullable=False),
    Column('condition_type', String, nullable=False),
    Column('operator', String, nullable=False),
    Column('target_value', Float, nullable=False),
    Column('is_active', Integer, default=1),
    Column('created_at', DateTime, server_default=func.now())
)

users_table = Table(
    'users', metadata,
    Column('user_id', BigInteger, primary_key=True),
    Column('username', String),
    Column('tier', String, default='free'),
    Column('created_at', DateTime, server_default=func.now())
)

portfolio_table = Table(
    'portfolio', metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', BigInteger, nullable=False),
    Column('symbol', String, nullable=False),
    Column('quantity', Integer, nullable=False),
    Column('buy_price', Float, nullable=False),
    Column('created_at', DateTime, server_default=func.now()),
    Column('is_alerted', Integer, default=0)
)

price_history_table = Table(
    'price_history', metadata,
    Column('symbol', String, primary_key=True),
    Column('date', String, primary_key=True),
    Column('open', Float),
    Column('high', Float),
    Column('low', Float),
    Column('close', Float),
    Column('volume', Integer)
)

def init_db():
    """Khởi tạo cấu trúc cơ sở dữ liệu"""
    metadata.create_all(engine)
    # Tự động fix lỗi kiểu dữ liệu Integer -> BigInteger cho các DB Postgres đã trót tạo trước đó
    if engine.dialect.name == 'postgresql':
        try:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE alerts ALTER COLUMN user_id TYPE BIGINT;"))
                conn.execute(text("ALTER TABLE users ALTER COLUMN user_id TYPE BIGINT;"))
                conn.execute(text("ALTER TABLE portfolio ALTER COLUMN user_id TYPE BIGINT;"))
        except Exception as e:
            logger.warning(f"Lỗi khi tự động nâng cấp kiểu dữ liệu BIGINT (có thể do bảng chưa có): {e}")

def get_all_price_history(symbols=None):
    """Lấy dữ liệu giá lịch sử. Nếu symbols=None, lấy toàn bộ."""
    query = "SELECT * FROM price_history"
    if symbols:
        # Chuẩn bị tham số an toàn (:p0, :p1)
        placeholders = ', '.join([f":p{i}" for i in range(len(symbols))])
        query += f" WHERE symbol IN ({placeholders})"
        params = {f"p{i}": sym for i, sym in enumerate(symbols)}
        df = pd.read_sql_query(text(query), engine, params=params)
    else:
        df = pd.read_sql_query(text(query), engine)
    return df

def add_alert(user_id: int, symbol: str, condition_type: str, operator: str, target_value: float):
    """Thêm một cảnh báo mới"""
    with engine.begin() as conn:
        stmt = alerts_table.insert().values(
            user_id=user_id, 
            symbol=symbol.upper(), 
            condition_type=condition_type.lower(), 
            operator=operator, 
            target_value=target_value
        )
        result = conn.execute(stmt)
        # Lấy ID vừa chèn an toàn trên cả Postgres và SQLite
        return result.inserted_primary_key[0]

def get_active_alerts(user_id: int = None):
    """Lấy danh sách cảnh báo đang hoạt động. Có thể lọc theo user_id"""
    with engine.connect() as conn:
        if user_id:
            res = conn.execute(text('SELECT * FROM alerts WHERE user_id = :uid AND is_active = 1'), {"uid": user_id})
        else:
            res = conn.execute(text('SELECT * FROM alerts WHERE is_active = 1'))
        # .mappings().all() chuyển đổi các dòng thành dạng dict (như sqlite3.Row cũ)
        return [dict(row) for row in res.mappings().all()]

def remove_alert(alert_id: int, user_id: int):
    """Xóa (hoặc vô hiệu hóa) một cảnh báo"""
    with engine.begin() as conn:
        res = conn.execute(text('UPDATE alerts SET is_active = 0 WHERE id = :aid AND user_id = :uid'), {"aid": alert_id, "uid": user_id})
        return res.rowcount > 0

def deactivate_alert(alert_id: int):
    """Vô hiệu hóa một cảnh báo sau khi đã trigger"""
    with engine.begin() as conn:
        conn.execute(text('UPDATE alerts SET is_active = 0 WHERE id = :aid'), {"aid": alert_id})

def buy_stock(user_id: int, symbol: str, quantity: int, buy_price: float):
    """Thêm một giao dịch mua vào danh mục. Trả về id."""
    with engine.begin() as conn:
        stmt = portfolio_table.insert().values(
            user_id=user_id, symbol=symbol.upper(), quantity=quantity, buy_price=buy_price
        )
        result = conn.execute(stmt)
        return result.inserted_primary_key[0]

def get_portfolio(user_id: int):
    """Lấy danh sách các mã đang giữ của user."""
    with engine.connect() as conn:
        res = conn.execute(text('SELECT * FROM portfolio WHERE user_id = :uid AND quantity > 0'), {"uid": user_id})
        return [dict(row) for row in res.mappings().all()]

def sell_stock(user_id: int, symbol: str, sell_qty: int):
    """Bán cổ phiếu (giảm khối lượng). Trả về số lượng còn lại chưa bán được."""
    with engine.begin() as conn:
        res = conn.execute(
            text('SELECT * FROM portfolio WHERE user_id = :uid AND symbol = :sym AND quantity > 0 ORDER BY created_at ASC'), 
            {"uid": user_id, "sym": symbol.upper()}
        )
        rows = list(res.mappings().all())
        
        remaining_to_sell = sell_qty
        for row in rows:
            if remaining_to_sell <= 0:
                break
                
            r_id = row['id']
            r_qty = row['quantity']
            
            if r_qty <= remaining_to_sell:
                conn.execute(text('UPDATE portfolio SET quantity = 0 WHERE id = :rid'), {"rid": r_id})
                remaining_to_sell -= r_qty
            else:
                new_qty = r_qty - remaining_to_sell
                conn.execute(text('UPDATE portfolio SET quantity = :qty WHERE id = :rid'), {"qty": new_qty, "rid": r_id})
                remaining_to_sell = 0
                
        return remaining_to_sell

if __name__ == "__main__":
    init_db()
    print("Cơ sở dữ liệu đã được khởi tạo/cập nhật thành công bằng SQLAlchemy!")
