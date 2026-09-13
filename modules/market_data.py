# -*- coding: utf-8 -*-
"""
Module 2: Dữ liệu giao dịch & Bảng giá thời gian thực (Market Data).
Bảng giá tức thời, biên độ giá trần/sàn/tham chiếu, khối lượng, nước ngoài và dòng tiền chủ động.
"""

import logging
import vnstock
from config import format_number, format_percent, format_currency_vn

logger = logging.getLogger("MarketData")

def get_market_quote(symbol: str) -> dict:
    """
    Lấy bảng giá trực tuyến và phân tích dòng tiền khớp lệnh.
    """
    symbol = symbol.upper().strip()
    res = {
        "symbol": symbol,
        "success": False,
        "quote": {},
        "order_flow": {
            "buy_vol": 0,
            "sell_vol": 0,
            "buy_ratio": 0.0,
            "sell_ratio": 0.0,
        },
        "error": None
    }
    
    try:
        mkt = vnstock.Market()
        eq = mkt.equity(symbol)
        
        # 1. Bảng giá realtime
        try:
            df_q = eq.quote()
            if df_q is not None and not df_q.empty:
                res["quote"] = df_q.iloc[0].to_dict()
                res["success"] = True
        except Exception as e:
            logger.warning(f"Không thể lấy quote cho {symbol}: {e}")
            
        # 2. Phân tích tick giao dịch mua/bán chủ động
        try:
            df_t = eq.trades()
            if df_t is not None and not df_t.empty and "match_type" in df_t.columns and "volume" in df_t.columns:
                buy_vol = df_t[df_t["match_type"].str.lower() == "buy"]["volume"].sum()
                sell_vol = df_t[df_t["match_type"].str.lower() == "sell"]["volume"].sum()
                total_vol = buy_vol + sell_vol
                buy_ratio = (buy_vol / total_vol * 100) if total_vol > 0 else 0
                sell_ratio = (sell_vol / total_vol * 100) if total_vol > 0 else 0
                
                res["order_flow"] = {
                    "buy_vol": int(buy_vol),
                    "sell_vol": int(sell_vol),
                    "buy_ratio": round(buy_ratio, 1),
                    "sell_ratio": round(sell_ratio, 1),
                }
        except Exception as e:
            logger.debug(f"Không thể phân tích trades cho {symbol}: {e}")
            
    except Exception as e:
        logger.error(f"Lỗi khi truy vấn market data cho {symbol}: {e}")
        res["error"] = str(e)
        
    return res

def format_market_html(data: dict) -> str:
    """Định dạng dữ liệu giao dịch thành thông điệp HTML cho Telegram."""
    if not data.get("success"):
        return f"❌ <b>Không tìm thấy dữ liệu giao dịch cho mã {data.get('symbol')}</b>"
        
    q = data.get("quote", {})
    symbol = data.get("symbol", "")
    
    price = q.get("close_price", 0)
    ref_price = q.get("reference_price", 0)
    ceil_price = q.get("ceiling_price", 0)
    floor_price = q.get("floor_price", 0)
    high_price = q.get("high_price", 0)
    low_price = q.get("low_price", 0)
    open_price = q.get("open_price", 0)
    
    change = q.get("price_change", 0)
    pct_change = q.get("percent_change", 0)
    volume = q.get("volume_accumulated", 0)
    total_val = q.get("total_value", 0)
    
    # Khối ngoại
    f_buy = q.get("foreign_buy_volume", 0)
    f_sell = q.get("foreign_sell_volume", 0)
    f_net = (f_buy or 0) - (f_sell or 0)
    
    # Icon biến động
    if change > 0:
        icon_stat = "🟢"
        color_change = f"<b>+{format_number(change, 0)} (+{format_number(pct_change, 2)}%)</b>"
    elif change < 0:
        icon_stat = "🔴"
        color_change = f"<b>{format_number(change, 0)} ({format_number(pct_change, 2)}%)</b>"
    else:
        icon_stat = "🟡"
        color_change = f"<b>0.0 (0.00%)</b>"
        
    flow = data.get("order_flow", {})
    buy_ratio = flow.get("buy_ratio", 0)
    sell_ratio = flow.get("sell_ratio", 0)
    
    # 3 mức giá đặt mua / bán
    b1_p, b1_v = q.get("bid_price_1", 0), q.get("bid_vol_1", 0)
    a1_p, a1_v = q.get("ask_price_1", 0), q.get("ask_vol_1", 0)
    
    html = [
        f"{icon_stat} <b>BẢNG GIÁ & GIAO DỊCH: {symbol}</b>",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"• <b>Giá hiện tại:</b> <code>{format_number(price, 0)}</code> {color_change}",
        f"• <b>Tham chiếu:</b> {format_number(ref_price, 0)} | <b>Mở cửa:</b> {format_number(open_price, 0)}",
        f"• <b>Trần / Sàn:</b> <code>{format_number(ceil_price, 0)}</code> / <code>{format_number(floor_price, 0)}</code>",
        f"• <b>Cao / Thấp nhất:</b> {format_number(high_price, 0)} / {format_number(low_price, 0)}",
        f"• <b>Tổng khối lượng:</b> {format_number(volume, 0)} CP",
        f"• <b>Giá trị giao dịch:</b> {format_currency_vn(total_val)}",
        f"\n🎯 <b>Dòng Tiền Khớp Lệnh:</b>",
        f"• Mua chủ động: <b>{buy_ratio}%</b> ({format_number(flow.get('buy_vol', 0), 0)} CP)",
        f"• Bán chủ động: <b>{sell_ratio}%</b> ({format_number(flow.get('sell_vol', 0), 0)} CP)",
        f"\n🌍 <b>Giao Dịch Khối Ngoại:</b>",
        f"• Mua: {format_number(f_buy, 0)} | Bán: {format_number(f_sell, 0)} CP",
        f"• Mua ròng: <b>{'+' if f_net > 0 else ''}{format_number(f_net, 0)} CP</b>",
        f"\n⚖️ <b>Sổ Lệnh Tốt Nhất (L1):</b>",
        f"• Mua 1: {format_number(b1_p, 0)} ({format_number(b1_v, 0)} CP)",
        f"• Bán 1: {format_number(a1_p, 0)} ({format_number(a1_v, 0)} CP)",
    ]
    return "\n".join(html)
