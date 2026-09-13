# -*- coding: utf-8 -*-
"""
Module 3: Dữ liệu cơ bản & Báo cáo tài chính (Fundamental Data).
Trích xuất các chỉ số tài chính quan trọng: P/E, P/B, ROE, ROA, EPS, BVPS, biên lợi nhuận.
"""

import logging
import vnstock
from config import format_number, format_percent

logger = logging.getLogger("FundamentalData")

def get_fundamental_data(symbol: str) -> dict:
    """
    Lấy và xử lý các chỉ số tài chính cơ bản.
    """
    symbol = symbol.upper().strip()
    res = {
        "symbol": symbol,
        "success": False,
        "metrics": {},
        "quarters": [],
        "error": None
    }
    
    try:
        fun = vnstock.Fundamental()
        eq = fun.equity(symbol)
        
        df_r = eq.ratio()
        if df_r is not None and not df_r.empty and "item" in df_r.columns:
            res["success"] = True
            
            # Lấy danh sách các cột quý (loại bỏ item, item_id)
            period_cols = [c for c in df_r.columns if c not in ["item", "item_id", "category_id", "source"]]
            res["quarters"] = period_cols[:4] if period_cols else []
            latest_col = period_cols[0] if period_cols else None
            
            # Map các chỉ tiêu quan trọng
            metrics_map = {
                "EPS": ["Thu nhập trên mỗi cổ phần của 4 quý gần nhất (EPS)", "EPS"],
                "BVPS": ["Giá trị sổ sách của cổ phiếu (BVPS)", "BVPS"],
                "PE": ["Chỉ số giá thị trường trên thu nhập (P/E)", "P/E"],
                "PB": ["Chỉ số giá thị trường trên giá trị sổ sách (P/B)", "P/B"],
                "PS": ["Chỉ số giá thị trường trên doanh thu thuần (P/S)", "P/S"],
                "ROE": ["Tỷ suất lợi nhuận trên vốn chủ sở hữu bình quân (ROEA)", "ROE bình quân 4 quý gần nhất", "ROEA"],
                "ROA": ["Tỷ suất sinh lợi trên tổng tài sản bình quân (ROAA)", "ROA bình quân 4 quý gần nhất", "ROAA"],
                "GrossMargin": ["Tỷ suất lợi nhuận gộp biên", "Biên lợi nhuận gộp"],
                "NetMargin": ["Tỷ suất sinh lợi trên doanh thu thuần", "Biên lợi nhuận ròng"],
                "Beta": ["Beta"],
                "DividendYield": ["Tỷ suất cổ tức"]
            }
            
            parsed_metrics = {}
            for key, search_terms in metrics_map.items():
                val = None
                for term in search_terms:
                    matched = df_r[df_r["item"].str.contains(term, case=False, na=False)]
                    if not matched.empty and latest_col:
                        raw_val = matched.iloc[0].get(latest_col)
                        try:
                            val = float(raw_val)
                            break
                        except (ValueError, TypeError):
                            continue
                parsed_metrics[key] = val
                
            res["metrics"] = parsed_metrics
            res["latest_period"] = latest_col
            
    except Exception as e:
        logger.error(f"Lỗi khi truy vấn dữ liệu cơ bản cho {symbol}: {e}")
        res["error"] = str(e)
        
    return res

def format_fundamental_html(data: dict) -> str:
    """Định dạng dữ liệu cơ bản thành thông điệp HTML cho Telegram."""
    if not data.get("success"):
        return f"❌ <b>Không tìm thấy dữ liệu tài chính cơ bản cho mã {data.get('symbol')}</b>"
        
    m = data.get("metrics", {})
    symbol = data.get("symbol", "")
    period = data.get("latest_period", "Quý gần nhất")
    
    eps = m.get("EPS")
    bvps = m.get("BVPS")
    pe = m.get("PE")
    pb = m.get("PB")
    ps = m.get("PS")
    roe = m.get("ROE")
    roa = m.get("ROA")
    gross_margin = m.get("GrossMargin")
    net_margin = m.get("NetMargin")
    div_yield = m.get("DividendYield")
    beta = m.get("Beta")
    
    html = [
        f"📑 <b>TÀI CHÍNH CƠ BẢN: {symbol}</b> (Kỳ: {period})",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"💰 <b>Khả Năng Sinh Lời:</b>",
        f"• ROE (Hiệu quả VCSH): <b>{format_percent(roe)}</b>",
        f"• ROA (Hiệu quả Tài sản): <b>{format_percent(roa)}</b>",
    ]
    
    if gross_margin is not None:
        html.append(f"• Biên lợi nhuận gộp: <b>{format_percent(gross_margin)}</b>")
    if net_margin is not None:
        html.append(f"• Biên lợi nhuận ròng: <b>{format_percent(net_margin)}</b>")
        
    html.extend([
        f"\n💎 <b>Chỉ Số Định Giá Cơ Bản:</b>",
        f"• P/E (Giá / Thu nhập): <b>{format_number(pe, 2)} lần</b>",
        f"• P/B (Giá / Giá trị sổ sách): <b>{format_number(pb, 2)} lần</b>",
    ])
    
    if ps is not None:
        html.append(f"• P/S (Giá / Doanh thu): <b>{format_number(ps, 2)} lần</b>")
        
    html.extend([
        f"\n📊 <b>Giá Trị Cổ Phiếu & Rủi Ro:</b>",
        f"• EPS (Thu nhập/CP): <b>{format_number(eps, 0)} đ</b>",
        f"• BVPS (Giá trị sổ sách/CP): <b>{format_number(bvps, 0)} đ</b>",
        f"• Hệ số Beta (Độ nhạy thị trường): <b>{format_number(beta, 2)}</b>",
        f"• Tỷ suất cổ tức: <b>{format_percent(div_yield)}</b>",
    ])
    
    return "\n".join(html)
