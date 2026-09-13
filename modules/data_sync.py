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
        from sqlalchemy import text
        from database import engine
        
        try:
            with engine.connect() as conn:
                res = conn.execute(text("SELECT DISTINCT symbol FROM price_history WHERE date >= :edate"), {"edate": end_date})
                updated_syms = [row[0] for row in res.fetchall()]
        except Exception as e:
            logger.warning(f"Chưa có bảng price_history hoặc lỗi đọc DB: {e}")
            updated_syms = []
        
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
            
            # Ghi vào SQLite/Postgres an toàn (Upsert)
            from sqlalchemy import text
            from database import engine
            
            # Ghi dữ liệu trực tiếp bằng index và ON CONFLICT DO UPDATE (nếu Postgres) hoặc REPLACE (nếu SQLite)
            # Tuy nhiên, cách an toàn nhất hỗ trợ cả hai: ghi vào bảng tạm, sau đó dùng SQL MERGE/REPLACE.
            
            with engine.begin() as conn:
                # Ghi vào bảng tạm
                temp_table_name = 'price_history_temp'
                final_df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume']].to_sql(
                    temp_table_name, engine, if_exists='replace', index=False
                )
                
                # Thực hiện truy vấn Upsert tùy vào loại database
                if engine.dialect.name == 'postgresql':
                    conn.execute(text(f"""
                        INSERT INTO price_history (symbol, date, open, high, low, close, volume)
                        SELECT symbol, date, open, high, low, close, volume FROM {temp_table_name}
                        ON CONFLICT (symbol, date) DO UPDATE SET
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume;
                    """))
                else:
                    # SQLite
                    conn.execute(text(f"""
                        INSERT OR REPLACE INTO price_history (symbol, date, open, high, low, close, volume)
                        SELECT symbol, date, open, high, low, close, volume FROM {temp_table_name}
                    """))
                    
                # Xóa bảng tạm
                conn.execute(text(f"DROP TABLE {temp_table_name}"))
            
            logger.info(f"Đã đồng bộ thành công dữ liệu lịch sử cho {len(all_data)} mã cổ phiếu (VN100).")
            
            import config
            if config.ADMIN_CHAT_ID:
                try:
                    await context.bot.send_message(
                        chat_id=config.ADMIN_CHAT_ID,
                        text=f"🔄 <b>TỰ ĐỘNG ĐỒNG BỘ HOÀN TẤT</b>\nĐã tải xong dữ liệu EOD cho {len(all_data)} mã VN100 vào Kho dữ liệu nội bộ.",
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"Không thể gửi tin báo cáo cho admin: {e}")
        
    except Exception as e:
        logger.error(f"Lỗi trong quá trình đồng bộ: {e}")
