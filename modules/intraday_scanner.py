import logging
import asyncio
import datetime
import pandas as pd
from telegram import Update
from telegram.ext import ContextTypes
import vnstock
import config

logger = logging.getLogger("IntradayScanner")

# Bộ nhớ đệm lưu kết quả quét gần nhất để phản hồi nhanh lệnh /scanner
SCANNER_CACHE = {
    "time": None,
    "results": []
}

async def run_scanner_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Hàm quét toàn bộ VN100 để tìm tín hiệu: Vol Breakout, Golden Cross, RSI.
    Được gọi tự động mỗi 30 phút trong giờ giao dịch.
    """
    logger.info("Bắt đầu quét tín hiệu thị trường VN100...")
    
    try:
        # Lấy danh sách VN100
        ref = vnstock.Reference()
        df_vn100 = ref.index.members('VN100')
        symbols = df_vn100.tolist()
    except Exception as e:
        logger.error(f"Không thể lấy danh sách VN100: {e}")
        return

    mkt = vnstock.Market()
    today = datetime.date.today()
    start_date = (today - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")
    
    signals_found = []
    
    for sym in symbols:
        try:
            # Lấy lịch sử giá (chạy qua thread để không block bot)
            df = await asyncio.to_thread(mkt.equity(sym).ohlcv, start=start_date, end=end_date)
            
            if df is None or df.empty or len(df) < 25:
                continue
                
            # Đảm bảo index/dữ liệu chuẩn
            df.sort_index(ascending=True, inplace=True)
            
            # Tính toán các chỉ báo
            df['SMA20'] = df['close'].rolling(window=20).mean()
            df['SMA50'] = df['close'].rolling(window=50).mean()
            df['Vol20'] = df['volume'].rolling(window=20).mean()
            
            # Tính RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI14'] = 100 - (100 / (1 + rs))
            
            # Lấy dòng dữ liệu hôm nay và hôm qua
            today_row = df.iloc[-1]
            yest_row = df.iloc[-2]
            
            close_price = float(today_row['close'])
            vol_today = float(today_row['volume'])
            avg_vol = float(today_row['Vol20'])
            
            sym_signals = []
            
            # 1. Volume Breakout (Khối lượng đột biến > 150% TB 20 phiên & Giá tăng)
            if vol_today > 1.5 * avg_vol and close_price > today_row['open']:
                ratio = (vol_today / avg_vol) * 100 if avg_vol > 0 else 0
                sym_signals.append(f"🔥 <b>Nổ Vol:</b> Gấp {ratio/100:.1f} lần TB20 phiên")
                
            # 2. Golden Cross (SMA20 cắt lên SMA50)
            if today_row['SMA20'] > today_row['SMA50'] and yest_row['SMA20'] <= yest_row['SMA50']:
                sym_signals.append("⚡ <b>Golden Cross:</b> MA20 cắt lên MA50")
                
            # 3. RSI
            rsi = today_row['RSI14']
            if pd.notna(rsi):
                if rsi < 30:
                    sym_signals.append(f"📉 <b>RSI Quá bán:</b> {rsi:.1f} (Vùng bắt đáy)")
                elif rsi > 70:
                    sym_signals.append(f"📈 <b>RSI Quá mua:</b> {rsi:.1f} (Vùng chốt lời)")
                    
            if sym_signals:
                signals_found.append({
                    "symbol": sym,
                    "price": close_price,
                    "signals": sym_signals
                })
                
        except Exception as e:
            logger.debug(f"Lỗi quét mã {sym}: {e}")
            
        # Nghỉ 1 giây để an toàn cho rate limit
        await asyncio.sleep(1)
        
    # Cập nhật Cache
    SCANNER_CACHE["time"] = datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    SCANNER_CACHE["results"] = signals_found
    
    logger.info(f"Hoàn tất quét. Tìm thấy {len(signals_found)} mã có tín hiệu.")
    
    # Tự động gửi tin nhắn cho Admin nếu có tín hiệu mới
    if signals_found and config.ADMIN_CHAT_ID:
        # Lọc ra top 10 mã nổi bật nhất để tránh spam
        top_signals = signals_found[:15]
        
        msg = f"🔍 <b>RADAR THỊ TRƯỜNG TỰ ĐỘNG</b> 🔍\n"
        msg += f"<i>Quét lúc: {SCANNER_CACHE['time']}</i>\n\n"
        
        for item in top_signals:
            msg += f"📌 <b>{item['symbol']}</b> (Giá: <code>{config.format_number(item['price'], 0)}</code>)\n"
            for sig in item['signals']:
                msg += f" ├ {sig}\n"
            msg += "\n"
            
        if len(signals_found) > 15:
            msg += f"<i>... và {len(signals_found) - 15} mã khác. Gõ /scanner để xem thêm.</i>"
            
        try:
            await context.bot.send_message(
                chat_id=config.ADMIN_CHAT_ID,
                text=msg,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Lỗi gửi tin báo scanner cho admin: {e}")

async def scanner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Trả về kết quả quét thị trường gần nhất cho người dùng.
    """
    if not SCANNER_CACHE["time"]:
        await update.message.reply_text(
            "⏳ Hệ thống Radar đang quét thị trường (mỗi 30 phút một lần). Vui lòng thử lại sau ít phút nhé!",
            parse_mode='HTML'
        )
        return
        
    results = SCANNER_CACHE["results"]
    if not results:
        await update.message.reply_text(
            f"🔍 <b>RADAR THỊ TRƯỜNG</b> ({SCANNER_CACHE['time']})\n\n"
            "Hiện tại chưa phát hiện cổ phiếu VN100 nào có tín hiệu đột biến (Nổ Vol, Golden Cross, RSI Quá mua/bán).",
            parse_mode='HTML'
        )
        return
        
    # Phân trang nếu quá dài
    msg = f"🔍 <b>RADAR THỊ TRƯỜNG (VN100)</b>\n"
    msg += f"<i>Cập nhật lúc: {SCANNER_CACHE['time']}</i>\n\n"
    
    # Chỉ hiển thị tối đa 20 mã để không bị rối
    display_results = results[:20]
    
    for item in display_results:
        msg += f"📌 <b>{item['symbol']}</b> (<code>{config.format_number(item['price'], 0)} đ</code>)\n"
        for sig in item['signals']:
            msg += f" ├ {sig}\n"
        msg += "\n"
        
    if len(results) > 20:
        msg += f"<i>... (Còn {len(results) - 20} mã khác đang có tín hiệu)</i>"
        
    await update.message.reply_text(msg, parse_mode='HTML')
