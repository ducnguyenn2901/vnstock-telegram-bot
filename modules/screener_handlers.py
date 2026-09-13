import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import vnstock
import datetime
import pandas as pd
import numpy as np

logger = logging.getLogger("ScreenerHandlers")

async def screen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Xử lý lệnh /screen
    Cú pháp: /screen <tiêu_chí>
    Tiêu chí: breakout, squeeze, uptrend
    """
    args = context.args
    valid_filters = ['breakout', 'squeeze', 'uptrend']
    
    if not args or args[0].lower() not in valid_filters:
        msg = (
            "🔍 <b>MÁY QUÉT CỔ PHIẾU (VN30)</b> 🔍\n\n"
            "Hãy chọn một trong các bộ lọc sau:\n"
            "🔹 <code>/screen breakout</code> : Cổ phiếu phá vỡ đỉnh 20 phiên kèm Volume lớn.\n"
            "🔹 <code>/screen squeeze</code> : Cổ phiếu đang tích lũy chặt (Bollinger Squeeze) chờ bùng nổ.\n"
            "🔹 <code>/screen uptrend</code> : Cổ phiếu đang trong xu hướng tăng mạnh (Giá > MA20 > MA50).\n\n"
            "<i>(Lưu ý: Để đảm bảo tốc độ và không bị vượt giới hạn API, tính năng này hiện chỉ quét rổ VN30)</i>"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        return
        
    filter_type = args[0].lower()
    await update.message.reply_text(f"🚀 Đang khởi động siêu máy quét <b>{filter_type.upper()}</b> trên Kho dữ liệu nội bộ...", parse_mode=ParseMode.HTML)
    
    try:
        # Lấy toàn bộ dữ liệu lịch sử từ DB nội bộ
        import database as db
        df_all = db.get_all_price_history()
        
        if df_all.empty:
            await update.message.reply_text("❌ Kho dữ liệu trống! Vui lòng gõ `/sync` để đồng bộ dữ liệu trước khi quét.", parse_mode=ParseMode.HTML)
            return
            
        matched_symbols = []
        
        # Nhóm dữ liệu theo từng mã
        grouped = df_all.groupby('symbol')
        
        for sym, df in grouped:
            try:
                # Phải sort theo date để đảm bảo đúng trình tự thời gian
                df = df.sort_values(by='date').reset_index(drop=True)
                
                if len(df) < 50:
                    continue
                    
                df['close'] = pd.to_numeric(df['close'])
                df['volume'] = pd.to_numeric(df['volume'])
                df['high'] = pd.to_numeric(df['high'])
                df['low'] = pd.to_numeric(df['low'])
                
                close = df['close'].values
                vol = df['volume'].values
                high = df['high'].values
                low = df['low'].values
                
                current_price = close[-1]
                current_vol = vol[-1]
                
                # Tính toán các chỉ báo
                ma20 = pd.Series(close).rolling(window=20).mean().values[-1]
                ma50 = pd.Series(close).rolling(window=50).mean().values[-1]
                vol_ma20 = pd.Series(vol).rolling(window=20).mean().values[-1]
                
                std20 = pd.Series(close).rolling(window=20).std().values[-1]
                upper_bb = ma20 + (2 * std20)
                lower_bb = ma20 - (2 * std20)
                bb_width = (upper_bb - lower_bb) / ma20
                
                highest_20 = np.max(high[-21:-1]) # Đỉnh 20 phiên trước đó
                
                # Kiểm tra điều kiện
                if filter_type == 'breakout':
                    if current_price > highest_20 and current_vol > (1.5 * vol_ma20) and current_price > ma20:
                        matched_symbols.append((sym, current_price))
                        
                elif filter_type == 'squeeze':
                    if bb_width < 0.05 and current_price > ma50:
                        matched_symbols.append((sym, current_price))
                        
                elif filter_type == 'uptrend':
                    if current_price > ma20 and ma20 > ma50 and current_price > df['close'].values[-20]:
                        matched_symbols.append((sym, current_price))
                        
            except Exception as e:
                logger.error(f"Lỗi khi quét {sym} trong DB: {e}")
                continue
                
        if not matched_symbols:
            await update.message.reply_text(f"📉 Không tìm thấy cổ phiếu nào thỏa mãn tiêu chí <b>{filter_type.upper()}</b> trong phiên hôm nay.", parse_mode=ParseMode.HTML)
        else:
            msg = f"🎯 <b>KẾT QUẢ LỌC: {filter_type.upper()}</b>\n"
            msg += f"Tìm thấy {len(matched_symbols)} cổ phiếu thỏa mãn:\n\n"
            for s, p in matched_symbols:
                msg += f"✅ <b>{s}</b> (Giá: {p})\n"
            msg += f"\n<i>Gõ <code>/analyze &lt;MÃ&gt;</code> để xem chi tiết.</i>"
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            
    except Exception as e:
        logger.error(f"Lỗi Screener: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra trong quá trình quét dữ liệu.")
