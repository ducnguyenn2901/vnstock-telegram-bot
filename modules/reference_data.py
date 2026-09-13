# -*- coding: utf-8 -*-
"""
Module 1: Dữ liệu tham chiếu & Hồ sơ doanh nghiệp (Reference Data).
Trích xuất thông tin niêm yết, vốn điều lệ, ban lãnh đạo và cơ cấu cổ đông lớn.
"""

import logging
import vnstock
from config import format_number, format_percent

logger = logging.getLogger("ReferenceData")

def get_reference_data(symbol: str) -> dict:
    """
    Lấy thông tin tham chiếu và hồ sơ doanh nghiệp.
    """
    symbol = symbol.upper().strip()
    res = {
        "symbol": symbol,
        "success": False,
        "info": {},
        "shareholders": [],
        "officers": [],
        "error": None
    }
    
    try:
        ref = vnstock.Reference()
        comp = ref.company(symbol)
        
        # 1. Lấy thông tin chung
        try:
            df_info = comp.info()
            if df_info is not None and not df_info.empty:
                res["info"] = df_info.iloc[0].to_dict()
                res["success"] = True
        except Exception as e:
            logger.warning(f"Không thể lấy company info cho {symbol}: {e}")
            
        # 2. Cổ đông lớn
        try:
            df_sh = comp.shareholders()
            if df_sh is not None and not df_sh.empty:
                top_sh = df_sh.head(5).to_dict(orient="records")
                res["shareholders"] = top_sh
        except Exception as e:
            logger.debug(f"Không thể lấy shareholders cho {symbol}: {e}")
            
        # 3. Ban lãnh đạo chủ chốt
        try:
            df_off = comp.officers()
            if df_off is not None and not df_off.empty:
                top_off = df_off.head(5).to_dict(orient="records")
                res["officers"] = top_off
        except Exception as e:
            logger.debug(f"Không thể lấy officers cho {symbol}: {e}")
            
    except Exception as e:
        logger.error(f"Lỗi khi truy vấn tham chiếu cho {symbol}: {e}")
        res["error"] = str(e)
        
    return res

def format_reference_html(data: dict) -> str:
    """Định dạng dữ liệu tham chiếu thành thông điệp HTML cho Telegram."""
    if not data.get("success"):
        return f"❌ <b>Không tìm thấy dữ liệu tham chiếu cho mã {data.get('symbol')}</b>"
        
    info = data.get("info", {})
    symbol = data.get("symbol", "")
    exchange = info.get("exchange", "N/A")
    comp_type = info.get("company_type", "Doanh nghiệp")
    charter_cap = info.get("charter_capital", "N/A")
    outstanding = info.get("outstanding_shares", "N/A")
    ceo = info.get("ceo_name", "N/A")
    ceo_pos = info.get("ceo_position", "Đại diện")
    website = info.get("website", "N/A")
    founded = info.get("founded_date", "N/A")
    listing_date = info.get("listing_date", "N/A")
    
    html = [
        f"🏢 <b>HỒ SƠ DOANH NGHIỆP: {symbol}</b>",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"• <b>Sàn niêm yết:</b> <code>{exchange}</code> ({comp_type})",
        f"• <b>Ngày thành lập:</b> {founded} | <b>Niêm yết:</b> {listing_date}",
        f"• <b>Vốn điều lệ:</b> {format_number(charter_cap, 0)} tỷ VNĐ",
        f"• <b>CP lưu hành:</b> {format_number(outstanding, 0)} CP",
        f"• <b>Đại diện / CEO:</b> {ceo} ({ceo_pos})",
        f"• <b>Website:</b> {website}",
    ]
    
    # Danh sách ban lãnh đạo
    officers = data.get("officers", [])
    if officers:
        html.append(f"\n👔 <b>Ban Lãnh Đạo Chủ Chốt:</b>")
        for off in officers:
            name = off.get("name", "N/A")
            pos = off.get("position", "")
            html.append(f"  ▫️ {name} - <i>{pos}</i>")
            
    # Danh sách cổ đông lớn
    shareholders = data.get("shareholders", [])
    if shareholders:
        html.append(f"\n👥 <b>Cổ Đông Lớn:</b>")
        for sh in shareholders:
            name = sh.get("name", "N/A")
            pct = sh.get("ownership_percentage", 0)
            shares = sh.get("shares_owned", 0)
            html.append(f"  ▫️ {name}: <b>{format_percent(pct)}</b> ({format_number(shares, 0)} CP)")
            
    return "\n".join(html)
