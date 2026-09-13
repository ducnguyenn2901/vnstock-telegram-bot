# -*- coding: utf-8 -*-
"""
Module 6: Thống kê giao dịch & Định giá (Valuation & Statistics).
P/E, P/B, EPS, BVPS, biên độ 52 tuần, vị thế giá và độ biến động lịch sử.
"""

import logging
import datetime
import pandas as pd
import numpy as np
import vnstock
from config import format_number, format_percent

logger = logging.getLogger("ValuationStats")

def get_valuation_and_stats(symbol: str) -> dict:
    """
    Tính toán các chỉ số định giá và thống kê biến động 52 tuần.
    """
    symbol = symbol.upper().strip()
    res = {
        "symbol": symbol,
        "success": False,
        "valuation": {},
        "range_52w": {},
        "volatility": None,
        "error": None
    }
    
    try:
        # 1. Lấy chỉ số định giá từ Fundamental
        try:
            fun = vnstock.Fundamental()
            df_r = fun.equity(symbol).ratio()
            if df_r is not None and not df_r.empty and "item" in df_r.columns:
                period_cols = [c for c in df_r.columns if c not in ["item", "item_id", "category_id", "source"]]
                latest_col = period_cols[0] if period_cols else None
                
                def _get_val(search_text):
                    m = df_r[df_r["item"].str.contains(search_text, case=False, na=False)]
                    if not m.empty and latest_col:
                        try:
                            return float(m.iloc[0].get(latest_col))
                        except (ValueError, TypeError):
                            return None
                    return None
                    
                res["valuation"] = {
                    "pe": _get_val("Chỉ số giá thị trường trên thu nhập (P/E)"),
                    "pb": _get_val("Chỉ số giá thị trường trên giá trị sổ sách (P/B)"),
                    "ps": _get_val("Chỉ số giá thị trường trên doanh thu thuần (P/S)"),
                    "eps": _get_val("Thu nhập trên mỗi cổ phần của 4 quý gần nhất (EPS)"),
                    "bvps": _get_val("Giá trị sổ sách của cổ phiếu (BVPS)"),
                    "dividend_yield": _get_val("Tỷ suất cổ tức"),
                    "beta": _get_val("Beta"),
                }
        except Exception as e:
            logger.warning(f"Không thể lấy valuation ratio cho {symbol}: {e}")
            
        # 2. Lấy dữ liệu 1 năm để tính 52-week High/Low và Volatility
        try:
            today = datetime.date.today()
            start_date = (today - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")
            
            mkt = vnstock.Market()
            df_ohlcv = mkt.equity(symbol).ohlcv(start=start_date, end=end_date)
            
            if df_ohlcv is not None and len(df_ohlcv) >= 20:
                df_ohlcv["close"] = pd.to_numeric(df_ohlcv["close"], errors="coerce")
                df_ohlcv["high"] = pd.to_numeric(df_ohlcv["high"], errors="coerce")
                df_ohlcv["low"] = pd.to_numeric(df_ohlcv["low"], errors="coerce")
                
                h52 = float(df_ohlcv["high"].max())
                l52 = float(df_ohlcv["low"].min())
                curr = float(df_ohlcv["close"].iloc[-1])
                
                pct_from_high = ((curr - h52) / h52 * 100) if h52 > 0 else 0
                pct_from_low = ((curr - l52) / l52 * 100) if l52 > 0 else 0
                
                # Volatility hàng năm (Annualized Volatility)
                returns = df_ohlcv["close"].pct_change().dropna()
                annual_vol = float(returns.std() * np.sqrt(252) * 100)
                
                res["range_52w"] = {
                    "high_52w": h52,
                    "low_52w": l52,
                    "current": curr,
                    "pct_from_high": pct_from_high,
                    "pct_from_low": pct_from_low,
                }
                res["volatility"] = annual_vol
                res["success"] = True
        except Exception as e:
            logger.warning(f"Không thể tính thống kê 52 tuần cho {symbol}: {e}")
            
    except Exception as e:
        logger.error(f"Lỗi khi xử lý valuation & stats cho {symbol}: {e}")
        res["error"] = str(e)
        
    return res

def format_valuation_html(data: dict) -> str:
    """Định dạng thống kê & định giá thành thông điệp HTML cho Telegram."""
    if not data.get("success") and not data.get("valuation"):
        return f"❌ <b>Không tìm thấy dữ liệu thống kê & định giá cho mã {data.get('symbol')}</b>"
        
    symbol = data.get("symbol", "")
    val = data.get("valuation", {})
    r52 = data.get("range_52w", {})
    vol = data.get("volatility")
    
    pe = val.get("pe")
    pb = val.get("pb")
    ps = val.get("ps")
    eps = val.get("eps")
    bvps = val.get("bvps")
    beta = val.get("beta")
    div_yield = val.get("dividend_yield")
    
    # Đánh giá sơ bộ về P/E
    pe_eval = ""
    if pe is not None:
        if pe <= 10:
            pe_eval = " (Vùng định giá HẤP DẪN)"
        elif pe <= 18:
            pe_eval = " (Mức định giá HỢP LÝ)"
        else:
            pe_eval = " (Định giá CAO / Đã phản ánh kỳ vọng)"
            
    html = [
        f"💎 <b>THỐNG KÊ & ĐỊNH GIÁ: {symbol}</b>",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"📊 <b>Bội Số Định Giá:</b>",
        f"• P/E (Hiện tại): <b>{format_number(pe, 2)} lần</b>{pe_eval}",
        f"• P/B (P/B hiện tại): <b>{format_number(pb, 2)} lần</b>",
    ]
    
    if ps is not None:
        html.append(f"• P/S: <b>{format_number(ps, 2)} lần</b>")
        
    html.extend([
        f"• EPS: <b>{format_number(eps, 0)} đ</b>",
        f"• BVPS: <b>{format_number(bvps, 0)} đ</b>",
        f"• Tỷ suất cổ tức: <b>{format_percent(div_yield)}</b>",
        f"• Hệ số Beta: <b>{format_number(beta, 2)}</b>",
    ])
    
    if r52:
        h52 = r52.get("high_52w", 0)
        l52 = r52.get("low_52w", 0)
        from_h = r52.get("pct_from_high", 0)
        from_l = r52.get("pct_from_low", 0)
        
        html.extend([
            f"\n📈 <b>Biên Độ 52 Tuần:</b>",
            f"• Đỉnh 52 tuần: <b>{format_number(h52, 2)}</b> ({format_percent(from_h)} so với đỉnh)",
            f"• Đáy 52 tuần: <b>{format_number(l52, 2)}</b> (+{format_number(from_l, 2)}% so với đáy)",
        ])
        
    if vol is not None:
        html.append(f"• Độ biến động hàng năm (Volatility): <b>{format_number(vol, 2)}%</b>")
        
    return "\n".join(html)
