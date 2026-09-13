# -*- coding: utf-8 -*-
import logging
import vnstock
import pandas as pd
from datetime import datetime, timedelta

logger = logging.getLogger("FundData")
_cached_listing = None
_last_fetch = None

def get_fund_info(symbol: str) -> dict:
    """Lấy dữ liệu Chứng chỉ quỹ mở từ Fmarket"""
    global _cached_listing, _last_fetch
    symbol = symbol.upper().strip()
    
    # Simple cache (ttl 1 hour)
    if _cached_listing is None or _last_fetch is None or datetime.now() - _last_fetch > timedelta(hours=1):
        try:
            _cached_listing = vnstock.Fund().listing()
            _last_fetch = datetime.now()
        except Exception as e:
            logger.error(f"Lỗi lấy danh sách CCQ Mở: {e}")
            return {"success": False, "error": f"Lỗi kết nối CSDL Quỹ Mở: {e}"}
            
    df = _cached_listing
    if df is None or df.empty:
        return {"success": False, "error": "Không có dữ liệu Quỹ Mở lúc này."}
        
    matched = df[df['short_name'].str.upper() == symbol]
    if matched.empty:
        return {"success": False, "error": f"Không tìm thấy chứng chỉ quỹ mở '{symbol}' trong hệ thống."}
        
    info = matched.iloc[0].to_dict()
    return {"success": True, "info": info}

def format_fund_html(data: dict) -> str:
    """Format dữ liệu Quỹ mở thành HTML gửi Telegram"""
    if not data.get("success"):
        return f"❌ <b>{data.get('error')}</b>"
        
    info = data["info"]
    name = info.get("short_name", "")
    full_name = info.get("name", "")
    f_type = info.get("fund_type", "")
    owner = info.get("fund_owner_name", "")
    nav = info.get("nav", 0)
    
    # Changes
    c_1m = info.get("nav_change_1m", 0) or 0
    c_3m = info.get("nav_change_3m", 0) or 0
    c_6m = info.get("nav_change_6m", 0) or 0
    c_12m = info.get("nav_change_12m", 0) or 0
    c_ytd = info.get("nav_change_last_year", 0) or 0
    update_at = info.get("nav_update_at", "")
    
    msg = f"🏦 <b>QUỸ MỞ: {name}</b>\n"
    msg += f"📜 Tên: <i>{full_name}</i>\n"
    msg += f"🏢 Quản lý bởi: {owner}\n"
    msg += f"🏷 Loại quỹ: {f_type}\n"
    msg += f"➖➖➖➖➖➖➖➖➖➖➖➖\n"
    msg += f"💰 <b>NAV/CCQ:</b> <code>{nav:,.0f} đ</code>\n"
    msg += f"🕒 Cập nhật: {update_at}\n\n"
    
    msg += f"📈 <b>Hiệu suất sinh lời:</b>\n"
    msg += f"▫️ 1 Tháng: <b>{c_1m:+.2f}%</b>\n"
    msg += f"▫️ 3 Tháng: <b>{c_3m:+.2f}%</b>\n"
    msg += f"▫️ 6 Tháng: <b>{c_6m:+.2f}%</b>\n"
    msg += f"▫️ 12 Tháng: <b>{c_12m:+.2f}%</b>\n"
    msg += f"▫️ YTD (Từ đầu năm): <b>{c_ytd:+.2f}%</b>\n"
    
    msg += f"➖➖➖➖➖➖➖➖➖➖➖➖\n"
    msg += f"💡 <i>Gợi ý: Chứng chỉ quỹ mở được giao dịch với giá NAV qua Fmarket hoặc trực tiếp công ty Quản lý Quỹ (không giao dịch trên sàn chứng khoán).</i>"
    
    return msg
