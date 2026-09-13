# -*- coding: utf-8 -*-
"""
Module 4: Dữ liệu vĩ mô (Macro Data).
Sức khỏe thị trường (VNINDEX, xu hướng, thanh khoản), tỷ giá ngoại tệ và giá vàng.
"""

import logging
import datetime
import pandas as pd
import vnstock
from config import format_number, format_percent, format_currency_vn

logger = logging.getLogger("MacroData")

def get_macro_overview() -> dict:
    """
    Lấy dữ liệu vĩ mô: VNINDEX, tỷ giá USD/EUR và giá vàng.
    """
    res = {
        "success": False,
        "vnindex": {},
        "exchange_rates": {},
        "gold": {},
        "error": None
    }
    
    try:
        # 1. VNINDEX
        try:
            today = datetime.date.today()
            start_date = (today - datetime.timedelta(days=120)).strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")
            
            mkt = vnstock.Market()
            df_idx = mkt.index("VNINDEX").ohlcv(start=start_date, end=end_date)
            
            if df_idx is not None and len(df_idx) >= 2:
                df_idx["close"] = pd.to_numeric(df_idx["close"], errors="coerce")
                df_idx["volume"] = pd.to_numeric(df_idx["volume"], errors="coerce")
                
                # Tính MA20, MA50
                df_idx["ma20"] = df_idx["close"].rolling(20).mean()
                df_idx["ma50"] = df_idx["close"].rolling(50).mean()
                
                last_row = df_idx.iloc[-1]
                prev_row = df_idx.iloc[-2]
                
                close_p = last_row["close"]
                prev_close = prev_row["close"]
                change = close_p - prev_close
                pct_change = (change / prev_close) * 100 if prev_close != 0 else 0
                
                ma20 = last_row["ma20"]
                ma50 = last_row["ma50"]
                
                # Xác định xu hướng
                if pd.notna(ma20) and pd.notna(ma50):
                    if close_p > ma20 and ma20 > ma50:
                        trend = "Uptrend mạnh (Trên MA20 & MA50)"
                    elif close_p > ma20:
                        trend = "Tích cực (Trên MA20)"
                    elif close_p < ma20 and close_p < ma50:
                        trend = "Downtrend (Dưới MA20 & MA50)"
                    else:
                        trend = "Đi ngang / Giằng co (Sideway)"
                else:
                    trend = "Chờ thêm dữ liệu"
                    
                res["vnindex"] = {
                    "date": str(last_row.get("time", ""))[:10],
                    "close": float(close_p),
                    "change": float(change),
                    "pct_change": float(pct_change),
                    "volume": float(last_row["volume"]),
                    "ma20": float(ma20) if pd.notna(ma20) else None,
                    "ma50": float(ma50) if pd.notna(ma50) else None,
                    "trend": trend
                }
                res["success"] = True
        except Exception as e:
            logger.warning(f"Lỗi khi lấy dữ liệu VNINDEX: {e}")
            
        # 2. Tỷ giá ngoại tệ & Vàng từ Retail
        try:
            ret = vnstock.Retail()
            # Tỷ giá
            df_ex = ret.exchange_rate()
            if df_ex is not None and not df_ex.empty:
                rates = {}
                for curr in ["USD", "EUR", "CNY"]:
                    row = df_ex[df_ex["currency_code"] == curr]
                    if not row.empty:
                        rates[curr] = {
                            "buy": row.iloc[0].get("buy_transfer") or row.iloc[0].get("buy_cash"),
                            "sell": row.iloc[0].get("sell"),
                            "date": row.iloc[0].get("date")
                        }
                res["exchange_rates"] = rates
                
            # Giá vàng
            df_gold = ret.gold()
            if df_gold is not None and not df_gold.empty:
                sjc = df_gold[df_gold["name"].str.contains("SJC", na=False)]
                if not sjc.empty:
                    first_sjc = sjc.iloc[0]
                    res["gold"] = {
                        "name": first_sjc.get("name"),
                        "buy": first_sjc.get("buy_price"),
                        "sell": first_sjc.get("sell_price"),
                        "date": first_sjc.get("date")
                    }
        except Exception as e:
            logger.warning(f"Lỗi khi lấy tỷ giá / giá vàng: {e}")
            
    except Exception as e:
        logger.error(f"Lỗi tổng quát khi lấy dữ liệu vĩ mô: {e}")
        res["error"] = str(e)
        
    return res

def format_macro_html(data: dict) -> str:
    """Định dạng dữ liệu vĩ mô thành thông điệp HTML cho Telegram."""
    if not data.get("success") and not data.get("exchange_rates"):
        return "❌ <b>Không thể cập nhật dữ liệu vĩ mô vào lúc này.</b>"
        
    vni = data.get("vnindex", {})
    rates = data.get("exchange_rates", {})
    gold = data.get("gold", {})
    
    html = [
        f"🌐 <b>TỔNG QUAN THỊ TRƯỜNG VĨ MÔ</b>",
        f"━━━━━━━━━━━━━━━━━━━━",
    ]
    
    if vni:
        close = vni.get("close", 0)
        change = vni.get("change", 0)
        pct = vni.get("pct_change", 0)
        vol = vni.get("volume", 0)
        ma20 = vni.get("ma20")
        ma50 = vni.get("ma50")
        trend = vni.get("trend", "N/A")
        
        icon = "🟢" if change >= 0 else "🔴"
        sign = "+" if change > 0 else ""
        
        html.extend([
            f"📊 <b>Chỉ Số VN-INDEX ({vni.get('date')}):</b>",
            f"• Điểm số: <b>{format_number(close, 2)}</b> {icon} <b>{sign}{format_number(change, 2)} ({sign}{format_number(pct, 2)}%)</b>",
            f"• Khối lượng: {format_number(vol, 0)} CP",
            f"• MA20: {format_number(ma20, 2)} | MA50: {format_number(ma50, 2)}",
            f"• Trạng thái thị trường: <b>{trend}</b>",
        ])
        
    if rates:
        html.append(f"\n💵 <b>Tỷ Giá Ngoại Tệ (Vietcombank):</b>")
        for curr, val in rates.items():
            html.append(f"• <b>{curr}/VND:</b> Mua {val.get('buy')} | Bán {val.get('sell')}")
            
    if gold:
        buy_g = gold.get("buy", 0)
        sell_g = gold.get("sell", 0)
        html.extend([
            f"\n🪙 <b>Giá Vàng Trong Nước:</b>",
            f"• {gold.get('name', 'Vàng SJC')}:",
            f"  ▫️ Mua vào: {format_currency_vn(buy_g)} / lượng",
            f"  ▫️ Bán ra: {format_currency_vn(sell_g)} / lượng",
        ])
        
    return "\n".join(html)
