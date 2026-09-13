# -*- coding: utf-8 -*-
"""
Module Tiện ích: Tạo biểu đồ kỹ thuật chuyên nghiệp (Chart Generator).
Vẽ biểu đồ nến Nhật, MA20, MA50, Bollinger Bands, Khối lượng và RSI.
Xuất ảnh dạng buffer bộ nhớ (io.BytesIO) sẵn sàng gửi qua Telegram Photo.
"""

import io
import logging
import datetime
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import vnstock

logger = logging.getLogger("ChartGenerator")

def generate_technical_chart(symbol: str, days: int = 90) -> io.BytesIO | None:
    """
    Vẽ biểu đồ kỹ thuật hoàn chỉnh gồm Nến, MA, Bollinger Bands, Volume và RSI.
    Trả về buffer io.BytesIO chứa ảnh PNG hoặc None nếu có lỗi.
    """
    symbol = symbol.upper().strip()
    try:
        today = datetime.date.today()
        # Lấy thêm ngày để tính đủ SMA50 và RSI ban đầu
        start_date = (today - datetime.timedelta(days=days + 80)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        
        mkt = vnstock.Market()
        df = mkt.equity(symbol).ohlcv(start=start_date, end=end_date)
        
        if df is None or len(df) < 20:
            logger.warning(f"Không đủ dữ liệu vẽ biểu đồ cho {symbol}")
            return None
            
        df = df.copy()
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time").reset_index(drop=True)
        
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            
        df = df.dropna(subset=["close"]).reset_index(drop=True)
        
        # Chỉ báo
        df["sma20"] = df["close"].rolling(20).mean()
        df["sma50"] = df["close"].rolling(50).mean()
        df["bb_mid"] = df["sma20"]
        df["bb_std"] = df["close"].rolling(20).std()
        df["bb_upper"] = df["bb_mid"] + 2 * df["bb_std"]
        df["bb_lower"] = df["bb_mid"] - 2 * df["bb_std"]
        df["vol_sma20"] = df["volume"].rolling(20).mean()
        
        # RSI 14
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss.replace(0, np.nan))
        df["rsi"] = 100 - (100 / (1 + rs))
        
        # Lọc lại số phiên hiển thị gần nhất
        df_plot = df.iloc[-days:].reset_index(drop=True)
        if len(df_plot) < 10:
            df_plot = df
            
        # Vẽ biểu đồ 3 subplot: Price + BB + MA (60%), Volume (20%), RSI (20%)
        plt.style.use("dark_background")
        fig, (ax_price, ax_vol, ax_rsi) = plt.subplots(
            nrows=3, ncols=1, figsize=(10, 8),
            gridspec_kw={"height_ratios": [3, 1, 1]},
            sharex=True
        )
        fig.patch.set_facecolor("#121722")
        for ax in [ax_price, ax_vol, ax_rsi]:
            ax.set_facecolor("#181f2f")
            ax.grid(True, linestyle="--", alpha=0.25, color="#5a6275")
            ax.tick_params(colors="#d1d4dc", labelsize=9)
            for spine in ax.spines.values():
                spine.set_color("#2a2e39")
                
        # 1. Vẽ nến Nhật (Candlesticks)
        width = 0.6
        width2 = 0.1
        up_color = "#26a69a"    # Xanh tăng
        down_color = "#ef5350"  # Đỏ giảm
        
        for i, row in df_plot.iterrows():
            o, h, l, c = row["open"], row["high"], row["low"], row["close"]
            color = up_color if c >= o else down_color
            
            # Tim nến (High - Low)
            ax_price.plot([i, i], [l, h], color=color, linewidth=1.2)
            # Thân nến (Open - Close)
            rect_bottom = min(o, c)
            rect_height = max(abs(c - o), (h - l) * 0.01)  # tránh phẳng lỳ
            rect = Rectangle(
                (i - width/2, rect_bottom), width, rect_height,
                facecolor=color, edgecolor=color
            )
            ax_price.add_patch(rect)
            
        # MA & Bollinger Bands
        ax_price.plot(df_plot.index, df_plot["sma20"], label="SMA 20", color="#ffb74d", linewidth=1.4)
        ax_price.plot(df_plot.index, df_plot["sma50"], label="SMA 50", color="#42a5f5", linewidth=1.4)
        ax_price.plot(df_plot.index, df_plot["bb_upper"], linestyle=":", color="#787b86", linewidth=0.9)
        ax_price.plot(df_plot.index, df_plot["bb_lower"], linestyle=":", color="#787b86", linewidth=0.9)
        ax_price.fill_between(df_plot.index, df_plot["bb_upper"], df_plot["bb_lower"], color="#787b86", alpha=0.08)
        
        latest_c = df_plot["close"].iloc[-1]
        ax_price.set_title(
            f"BIỂU ĐỒ KỸ THUẬT: {symbol} - Giá: {latest_c:,.2f}",
            fontsize=13, fontweight="bold", color="#ffffff", pad=10
        )
        ax_price.legend(loc="upper left", facecolor="#1e222d", edgecolor="#363c4e", fontsize=8)
        ax_price.set_ylabel("Giá (VNĐ)", color="#d1d4dc", fontsize=9)
        
        # 2. Volume
        vol_colors = [up_color if c >= o else down_color for o, c in zip(df_plot["open"], df_plot["close"])]
        ax_vol.bar(df_plot.index, df_plot["volume"], color=vol_colors, width=width, alpha=0.85)
        ax_vol.plot(df_plot.index, df_plot["vol_sma20"], color="#ffb74d", linewidth=1.0, label="Vol MA20")
        ax_vol.set_ylabel("Khối Lượng", color="#d1d4dc", fontsize=9)
        ax_vol.legend(loc="upper left", facecolor="#1e222d", edgecolor="#363c4e", fontsize=8)
        
        # 3. RSI
        ax_rsi.plot(df_plot.index, df_plot["rsi"], color="#ab47bc", linewidth=1.5, label="RSI(14)")
        ax_rsi.axhline(70, color="#ef5350", linestyle="--", linewidth=0.8, alpha=0.7)
        ax_rsi.axhline(30, color="#26a69a", linestyle="--", linewidth=0.8, alpha=0.7)
        ax_rsi.fill_between(df_plot.index, 70, 30, color="#ab47bc", alpha=0.06)
        ax_rsi.set_ylim(10, 90)
        ax_rsi.set_ylabel("RSI (14)", color="#d1d4dc", fontsize=9)
        ax_rsi.legend(loc="upper left", facecolor="#1e222d", edgecolor="#363c4e", fontsize=8)
        
        # Format trục thời gian X
        step = max(1, len(df_plot) // 8)
        xticks_idx = list(range(0, len(df_plot), step))
        if xticks_idx[-1] != len(df_plot) - 1:
            xticks_idx.append(len(df_plot) - 1)
        xticklabels = [df_plot["time"].iloc[idx].strftime("%d/%m") for idx in xticks_idx]
        ax_rsi.set_xticks(xticks_idx)
        ax_rsi.set_xticklabels(xticklabels, rotation=0, fontsize=9)
        
        fig.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        return buf
        
    except Exception as e:
        logger.error(f"Lỗi khi tạo biểu đồ: {e}")
        return None

def generate_financial_chart(symbol: str) -> io.BytesIO | None:
    """
    Vẽ biểu đồ hình cột Doanh thu & Lợi nhuận 4 quý gần nhất.
    """
    try:
        symbol = symbol.upper().strip()
        fun = vnstock.Fundamental()
        df = fun.equity(symbol).income_statement(period='quarter')
        if df is None or df.empty:
            return None
            
        # Lấy 4 quý gần nhất (trừ cột item, item_id)
        cols = [c for c in df.columns if c not in ['item', 'item_id']]
        cols = sorted(cols, reverse=False) # Sắp xếp tăng dần theo thời gian (VD: 2023-Q1, 2023-Q2)
        if len(cols) > 4:
            cols = cols[-4:] # Lấy 4 quý gần nhất
            
        # Tìm Doanh thu (revenue hoặc net_interest_income)
        revenue_row = df[df['item_id'] == 'revenue']
        if revenue_row.empty:
            revenue_row = df[df['item_id'] == 'net_interest_income']
            
        # Lấy dòng đầu tiên nếu có nhiều dòng trùng ID
        if not revenue_row.empty:
            revenue_data = revenue_row.iloc[0][cols].astype(float)
        else:
            revenue_data = pd.Series(0, index=cols)
            
        # Tìm Lợi nhuận (net_profit)
        profit_row = df[df['item_id'] == 'net_profit']
        if not profit_row.empty:
            profit_data = profit_row.iloc[0][cols].astype(float)
        else:
            profit_data = pd.Series(0, index=cols)
            
        # Vẽ biểu đồ
        fig, ax = plt.subplots(figsize=(10, 6))
        
        x = np.arange(len(cols))
        width = 0.35
        
        # Đổi đơn vị sang Tỷ VNĐ
        revenue_data = revenue_data / 1e9
        profit_data = profit_data / 1e9
        
        rects1 = ax.bar(x - width/2, revenue_data, width, label='Doanh thu thuần (Tỷ VNĐ)', color='#1f77b4')
        rects2 = ax.bar(x + width/2, profit_data, width, label='Lợi nhuận sau thuế (Tỷ VNĐ)', color='#2ca02c')
        
        ax.set_ylabel('Tỷ VNĐ', fontsize=12)
        ax.set_title(f'Tình hình Kinh doanh 4 Quý gần nhất - {symbol}', fontsize=16, fontweight='bold', color='navy')
        ax.set_xticks(x)
        ax.set_xticklabels(cols, fontsize=11)
        ax.legend()
        
        # Thêm text giá trị lên đầu cột
        ax.bar_label(rects1, padding=3, fmt='%.0f', fontsize=9)
        ax.bar_label(rects2, padding=3, fmt='%.0f', fontsize=9)
        
        fig.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        return buf
        
    except Exception as e:
        logger.error(f"Lỗi khi vẽ biểu đồ tài chính cho {symbol}: {e}")
        return None
