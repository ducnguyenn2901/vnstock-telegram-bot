import logging
import vnstock
import pandas as pd
import config

logger = logging.getLogger("SmartMoney")

def get_shark_trades(symbol: str, min_value_vnd=5_000_000_000):
    """
    Phân tích dòng tiền cá mập trong ngày dựa trên dữ liệu khớp lệnh tick-by-tick.
    Lọc ra các lệnh MUA CHỦ ĐỘNG có giá trị >= min_value_vnd (Mặc định 5 tỷ).
    """
    symbol = symbol.upper()
    try:
        mkt = vnstock.Market()
        eq = mkt.equity(symbol)
        df = eq.trades()
        
        if df is None or df.empty:
            return None
            
        # Tính toán giá trị lệnh (price trên bảng giá thường chia 1000)
        # Giả định: price trong df là số chia 1000 (VD: 32.40), volume là số lượng thực
        df['value_vnd'] = df['price'] * 1000 * df['volume']
        
        # Lọc ra các lệnh mua chủ động lớn hơn ngưỡng
        sharks = df[(df['match_type'] == 'buy') & (df['value_vnd'] >= min_value_vnd)]
        
        # Sắp xếp theo thời gian mới nhất
        sharks = sharks.sort_values(by='time', ascending=False)
        
        return sharks
        
    except SystemExit:
        logger.warning(f"Bị chặn API khi quét cá mập mã {symbol}")
        return None
    except Exception as e:
        logger.error(f"Lỗi khi lấy dữ liệu khớp lệnh {symbol}: {e}")
        return None

def format_shark_message(symbol: str, df_sharks, min_value_vnd=5_000_000_000) -> str:
    """Format kết quả thành tin nhắn Telegram"""
    symbol = symbol.upper()
    min_bil = min_value_vnd / 1_000_000_000
    
    if df_sharks is None:
        return f"❌ Lỗi khi lấy dữ liệu hoặc bị giới hạn API cho mã <b>{symbol}</b>."
        
    if df_sharks.empty:
        return f"🦈 <b>SMART MONEY: {symbol}</b>\n\nKhông phát hiện lệnh mua chủ động nào >= {min_bil:g} tỷ trong phiên hôm nay."
        
    msg = f"🦈 <b>SMART MONEY: {symbol}</b>\n"
    msg += f"<i>(Các lệnh MUA KHỦNG >= {min_bil:g} tỷ hôm nay)</i>\n"
    msg += "➖➖➖➖➖➖➖➖➖➖➖➖\n"
    
    for _, row in df_sharks.head(15).iterrows():
        time_str = str(row['time']).split()[-1][:8]  # Lấy HH:MM:SS
        price = row['price']
        vol = row['volume']
        val = row['value_vnd']
        
        msg += f"⏱ <code>{time_str}</code> | 🟢 <b>MUA</b>\n"
        msg += f"▫️ Giá: <code>{config.format_number(price * 1000, 0)} đ</code>\n"
        msg += f"▫️ KL: <code>{config.format_number(vol, 0)}</code>\n"
        msg += f"▫️ Trị giá: <b>{config.format_currency_vn(val)}</b>\n"
        msg += "┈┈┈┈┈┈┈┈┈┈┈┈\n"
        
    if len(df_sharks) > 15:
        msg += f"<i>... và {len(df_sharks) - 15} lệnh siêu khủng khác.</i>\n"
        
    return msg
