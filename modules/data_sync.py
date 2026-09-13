import logging
import asyncio
import pandas as pd
import vnstock
import datetime
import database as db

logger = logging.getLogger("DataSync")

async def sync_all_stocks_data(context):
    """
    Task ngầm đồng bộ dữ liệu EOD (End-Of-Day) của HOSE.
    Vì giới hạn 60 requests/phút, chúng ta chỉ lấy rổ VN100 hoặc top thanh khoản để tránh quá tải,
    hoặc quét từ từ (sleep giữa các request).
    """
    logger.info("Bắt đầu tiến trình đồng bộ dữ liệu EOD...")
    try:
        # Tạm thời chỉ lấy danh sách VN100 để giới hạn 100 request (vượt qua 60 req/phút bằng cách nghỉ ngơi)
        ref = vnstock.Reference()
        df_vn100 = ref.index.members('VN100')
        symbols = df_vn100.tolist()
        
        mkt = vnstock.Market()
        today = datetime.date.today()
        start_date = (today - datetime.timedelta(days=100)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        
        # Kiểm tra xem mã nào đã được cập nhật hôm nay rồi thì bỏ qua
        import sqlite3
        conn = sqlite3.connect(db.DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT DISTINCT symbol FROM price_history WHERE date >= ?", (end_date,))
            updated_syms = [r[0] for r in cursor.fetchall()]
        except:
            updated_syms = []
        conn.close()
        
        symbols = [s for s in symbols if s not in updated_syms]
        
        if not symbols:
            logger.info("Tất cả các mã VN100 đã được đồng bộ đầy đủ cho ngày hôm nay.")
            return
            
        logger.info(f"Cần đồng bộ {len(symbols)} mã còn lại...")
        
        all_data = []
        count = 0
        
        for sym in symbols:
            try:
                df = mkt.equity(sym).ohlcv(start=start_date, end=end_date)
                if df is not None and not df.empty:
                    df['symbol'] = sym
                    all_data.append(df)
                    
                count += 1
                # Nghỉ 1.5 giây sau mỗi request để không vượt quá 60 req/phút (40 req/phút an toàn)
                await asyncio.sleep(1.5)
                
            except SystemExit:
                logger.warning(f"Bị ngắt do quá giới hạn API khi đang tải mã {sym}")
                break
            except Exception as e:
                logger.error(f"Lỗi tải dữ liệu cho {sym}: {e}")
                
        if all_data:
            # Gộp tất cả dataframe lại
            final_df = pd.concat(all_data, ignore_index=True)
            # Chuẩn hóa cột
            final_df.rename(columns={'time': 'date'}, inplace=True)
            
            # Ghi vào SQLite an toàn (không ghi đè mất dữ liệu cũ nếu tiến trình bị ngắt nửa chừng)
            import sqlite3
            conn = sqlite3.connect(db.DB_PATH)
            
            # Ghi vào bảng tạm
            final_df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume']].to_sql('price_history_temp', conn, if_exists='replace', index=False)
            
            # Insert or replace vào bảng chính
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO price_history (symbol, date, open, high, low, close, volume)
                SELECT symbol, date, open, high, low, close, volume FROM price_history_temp
            ''')
            
            # Dọn dẹp bảng tạm
            cursor.execute("DROP TABLE price_history_temp")
            
            # Tạo index cho bảng mới (để truy vấn nhanh)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbol_date ON price_history(symbol, date);")
            conn.commit()
            conn.close()
            
            logger.info(f"Đã đồng bộ thành công dữ liệu lịch sử cho {len(all_data)} mã cổ phiếu (VN100).")
        
    except Exception as e:
        logger.error(f"Lỗi trong quá trình đồng bộ: {e}")
