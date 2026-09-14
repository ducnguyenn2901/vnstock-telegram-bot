# -*- coding: utf-8 -*-
"""
Module 5: Phân tích kỹ thuật chuyên sâu (Technical Analysis).
Tính toán MA, RSI, MACD, Bollinger Bands, Khối lượng và Đánh giá trạng thái kỹ thuật.
"""

import logging
import datetime
import pandas as pd
import numpy as np
import vnstock
from config import format_number

logger = logging.getLogger("TechnicalAnalysis")

def get_technical_analysis(symbol: str) -> dict:
    """
    Tính toán các chỉ báo kỹ thuật và tổng hợp tín hiệu giao dịch.
    """
    symbol = symbol.upper().strip()
    res = {
        "symbol": symbol,
        "success": False,
        "indicators": {},
        "signals": [],
        "verdict": "TRUNG LẬP",
        "verdict_score": 0,
        "error": None
    }
    
    try:
        today = datetime.date.today()
        start_date = (today - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        
        mkt = vnstock.Market()
        df = mkt.equity(symbol).ohlcv(start=start_date, end=end_date)
        
        if df is None or len(df) < 30:
            res["error"] = "Dữ liệu lịch sử giá không đủ (tối thiểu 30 phiên)."
            return res
            
        df = df.copy()
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        df["high"] = pd.to_numeric(df["high"], errors="coerce")
        df["low"] = pd.to_numeric(df["low"], errors="coerce")
        df = df.dropna(subset=["close"]).reset_index(drop=True)
        
        # 1. Moving Averages
        df["sma20"] = df["close"].rolling(20).mean()
        df["sma50"] = df["close"].rolling(50).mean()
        df["sma200"] = df["close"].rolling(200).mean() if len(df) >= 200 else np.nan
        df["vol_sma20"] = df["volume"].rolling(20).mean()
        
        # 2. RSI (14)
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss.replace(0, np.nan))
        df["rsi"] = 100 - (100 / (1 + rs))
        
        # 3. MACD (12, 26, 9)
        ema12 = df["close"].ewm(span=12, adjust=False).mean()
        ema26 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = ema12 - ema26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]
        
        # 4. Bollinger Bands (20, 2)
        df["bb_mid"] = df["sma20"]
        df["bb_std"] = df["close"].rolling(20).std()
        df["bb_upper"] = df["bb_mid"] + 2 * df["bb_std"]
        df["bb_lower"] = df["bb_mid"] - 2 * df["bb_std"]
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"] * 100
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        close_val = float(last["close"])
        sma20_val = float(last["sma20"]) if pd.notna(last["sma20"]) else None
        sma50_val = float(last["sma50"]) if pd.notna(last["sma50"]) else None
        sma200_val = float(last["sma200"]) if pd.notna(last["sma200"]) else None
        rsi_val = float(last["rsi"]) if pd.notna(last["rsi"]) else 50.0
        macd_val = float(last["macd"])
        signal_val = float(last["macd_signal"])
        hist_val = float(last["macd_hist"])
        prev_hist = float(prev["macd_hist"])
        
        bb_upper = float(last["bb_upper"]) if pd.notna(last["bb_upper"]) else None
        bb_lower = float(last["bb_lower"]) if pd.notna(last["bb_lower"]) else None
        bb_width = float(last["bb_width"]) if pd.notna(last["bb_width"]) else None
        
        vol = float(last["volume"])
        vol_ma = float(last["vol_sma20"]) if pd.notna(last["vol_sma20"]) else vol
        vol_ratio = (vol / vol_ma) if vol_ma > 0 else 1.0
        
        # Đánh giá tín hiệu tổng hợp
        score = 0
        signals = []
        
        # Trend
        if sma20_val:
            if close_val > sma20_val:
                score += 1
                signals.append("✅ Giá nằm trên SMA20 (Xu hướng ngắn hạn TÍCH CỰC)")
            else:
                score -= 1
                signals.append("⚠️ Giá nằm dưới SMA20 (Xu hướng ngắn hạn TIÊU CỰC)")
                
        if sma50_val:
            if close_val > sma50_val:
                score += 1
                signals.append("✅ Giá nằm trên SMA50 (Xu hướng trung hạn TỐT)")
            else:
                score -= 1
                signals.append("⚠️ Giá nằm dưới SMA50 (Áp lực trung hạn)")
                
        # RSI
        if rsi_val >= 70:
            score -= 1
            signals.append(f"⚠️ RSI = {rsi_val:.1f} (Vùng QUÁ MUA - Cảnh báo điều chỉnh)")
        elif rsi_val <= 30:
            score += 1
            signals.append(f"💡 RSI = {rsi_val:.1f} (Vùng QUÁ BÁN - Tiềm năng đảo chiều)")
        else:
            signals.append(f"▫️ RSI = {rsi_val:.1f} (Vùng trung tính)")
            
        # MACD
        if macd_val > signal_val:
            score += 1
            if hist_val > 0 and prev_hist <= 0:
                signals.append("🔥 MACD vừa cắt lên đường Tín hiệu (Golden Cross)")
            else:
                signals.append("✅ MACD trên Signal (Động lượng TĂNG)")
        else:
            score -= 1
            if hist_val < 0 and prev_hist >= 0:
                signals.append("⚡ MACD vừa cắt xuống đường Tín hiệu (Death Cross)")
            else:
                signals.append("⚠️ MACD dưới Signal (Động lượng GIẢM)")
                
        # Bollinger Bands Squeeze
        if bb_width and bb_width < 10:
            signals.append("🌀 Dải Bollinger Bands co thắt hẹp (Squeeze - Chuẩn bị biến động mạnh)")
            
        # Volume
        if vol_ratio >= 1.5:
            signals.append(f"🚀 Thanh khoản bùng nổ (+{(vol_ratio-1)*100:.0f}% so với TB 20 phiên)")
            
        # Kết luận
        if score >= 3:
            verdict = "🟢 MUA MẠNH"
        elif score in [1, 2]:
            verdict = "🌱 KHẢ QUAN / TÍCH LŨY"
        elif score == 0:
            verdict = "⚪ TRUNG LẬP / QUAN SÁT"
        elif score in [-1, -2]:
            verdict = "🍂 THẬN TRỌNG / RỦI RO NHẸ"
        else:
            verdict = "🔴 BÁN / RỦI RO CAO"
            
        res["success"] = True
        res["indicators"] = {
            "close": close_val,
            "sma20": sma20_val,
            "sma50": sma50_val,
            "sma200": sma200_val,
            "rsi": rsi_val,
            "macd": macd_val,
            "macd_signal": signal_val,
            "macd_hist": hist_val,
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
            "bb_width": bb_width,
            "vol_ratio": vol_ratio
        }
        res["signals"] = signals
        res["verdict"] = verdict
        res["verdict_score"] = score
        
    except Exception as e:
        logger.error(f"Lỗi khi tính toán kỹ thuật cho {symbol}: {e}")
        res["error"] = str(e)
        
    return res

def format_technical_html(data: dict) -> str:
    """Định dạng phân tích kỹ thuật thành thông điệp HTML cho Telegram."""
    if not data.get("success"):
        return f"❌ <b>Không thể phân tích kỹ thuật cho mã {data.get('symbol')}</b>: {data.get('error', '')}"
        
    symbol = data.get("symbol", "")
    ind = data.get("indicators", {})
    verdict = data.get("verdict", "TRUNG LẬP")
    signals = data.get("signals", [])
    
    close = ind.get("close", 0)
    sma20 = ind.get("sma20")
    sma50 = ind.get("sma50")
    rsi = ind.get("rsi", 50)
    macd = ind.get("macd", 0)
    bb_u = ind.get("bb_upper")
    bb_l = ind.get("bb_lower")
    
    html = [
        f"📈 <b>PHÂN TÍCH KỸ THUẬT: {symbol}</b>",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"🏆 <b>Đánh Giá Chung:</b> <b>{verdict}</b> (Điểm: {data.get('verdict_score', 0)})",
        f"\n📐 <b>Chỉ Báo Kỹ Thuật Chính:</b>",
        f"• Giá đóng cửa: <b>{format_number(close, 2)}</b>",
        f"• SMA20: {format_number(sma20, 2)} | SMA50: {format_number(sma50, 2)}",
        f"• RSI (14): <b>{format_number(rsi, 1)}</b>",
        f"• MACD: {format_number(macd, 3)}",
        f"• Bollinger Bands: [{format_number(bb_l, 2)} - {format_number(bb_u, 2)}]",
        f"\n🔍 <b>Tín Hiệu Chi Tiết:</b>",
    ]
    
    for s in signals:
        html.append(f"• {s}")
        
    return "\n".join(html)
