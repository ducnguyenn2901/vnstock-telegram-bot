import logging
import pandas as pd
import numpy as np
import database as db
import config

logger = logging.getLogger("Backtester")

def run_backtest(symbol: str, strategy: str) -> dict:
    """
    Chạy mô phỏng giao dịch (Backtest) trên dữ liệu quá khứ.
    - Mua: Dựa trên tín hiệu của strategy (breakout, squeeze, uptrend, rf_signal)
    - Bán: Lỗ chạm -7%, giá đóng cửa thủng MA20, hoặc giữ quá 20 phiên.
    - rf_signal: Sử dụng mô hình Random Forest Quant ML (gọi qua ml_predictor).
    """
    symbol = symbol.upper()
    strategy = strategy.lower()
    valid_strategies = ['breakout', 'squeeze', 'uptrend', 'rf_signal']
    
    if strategy not in valid_strategies:
        return {"success": False, "error": f"Chiến lược không hợp lệ. Hãy chọn: {', '.join(valid_strategies)}"}

    # Nếu chọn rf_signal, ủy thác hoàn toàn cho ml_predictor (đã tích hợp sẵn Backtest)
    if strategy == 'rf_signal':
        import modules.ml_predictor as ml
        res = ml.train_and_predict(symbol, target_days=3)
        if not res.get("success"):
            return res
        # Chuyển đổi kết quả ml_predictor sang format của backtester
        return {
            "success": True,
            "symbol": symbol,
            "strategy": "RF_SIGNAL (Random Forest Quant ML)",
            "is_rf": True,
            "total_trades": res.get("total_trades", 0),
            "win_rate": res.get("win_rate", 0),
            "avg_pnl": res.get("avg_pnl", 0),
            "max_dd": res.get("max_dd", 0),
            "total_rf_return": res.get("total_rf_return", 0),
            "bh_return": res.get("bh_return", 0),
            "roundtrip_cost": res.get("roundtrip_cost", 0),
            "recent_trades": res.get("recent_trades", []),
            "rf_acc": res.get("rf_acc", 0),
            "baseline_acc": res.get("baseline_acc", 0),
            "macro_f1": res.get("macro_f1", 0),
        }

    # 1. Lấy dữ liệu
    df = db.get_all_price_history(symbols=[symbol])
    
    if df.empty or len(df) < 50:
        logger.info(f"Dữ liệu DB cho {symbol} chưa đủ ({len(df)} phiên). Đang tự động tải từ vnstock...")
        import vnstock
        import datetime
        mkt = vnstock.Market()
        end_date = datetime.date.today().strftime("%Y-%m-%d")
        start_date = (datetime.date.today() - datetime.timedelta(days=365 * 4)).strftime("%Y-%m-%d")
        
        df = mkt.equity(symbol).ohlcv(start=start_date, end=end_date)
        if df is None or df.empty or len(df) < 50:
            return {"success": False, "error": f"Không đủ dữ liệu lịch sử cho {symbol} (cần tối thiểu 50 phiên)."}
            
        # Chuẩn hóa tên cột
        df.columns = [c.lower() for c in df.columns]
        if 'time' in df.columns:
            df.rename(columns={'time': 'date'}, inplace=True)

    # Đảm bảo sắp xếp đúng theo thời gian
    df = df.sort_values('date').reset_index(drop=True)

    # 2. Tính toán các chỉ báo kỹ thuật
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma50'] = df['close'].rolling(50).mean()
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    
    # Bollinger Bands
    df['std20'] = df['close'].rolling(20).std()
    df['upper_bb'] = df['ma20'] + (2 * df['std20'])
    df['lower_bb'] = df['ma20'] - (2 * df['std20'])
    df['bb_width'] = (df['upper_bb'] - df['lower_bb']) / df['ma20']
    
    # Đỉnh 20 phiên trước (shift 1 để không tính phiên hiện tại vào đỉnh)
    df['highest_20'] = df['high'].rolling(20).max().shift(1)

    trades = []
    in_position = False
    buy_price = 0
    buy_date = ""
    days_held = 0

    # 3. Vòng lặp mô phỏng giao dịch
    for i in range(50, len(df)):
        row = df.iloc[i]
        
        if not in_position:
            # KIỂM TRA ĐIỂM MUA
            buy_signal = False
            
            if strategy == 'breakout':
                if row['close'] > row['highest_20'] and row['volume'] > (1.5 * row['vol_ma20']) and row['close'] > row['ma20']:
                    buy_signal = True
                    
            elif strategy == 'squeeze':
                if row['bb_width'] < 0.05 and row['close'] > row['ma50'] and row['close'] > row['ma20']:
                    buy_signal = True
                    
            elif strategy == 'uptrend':
                close_20_ago = df.iloc[i-20]['close']
                if row['close'] > row['ma20'] and row['ma20'] > row['ma50'] and row['close'] > close_20_ago:
                    buy_signal = True

            if buy_signal:
                in_position = True
                buy_price = row['close']
                buy_date = row['date']
                days_held = 0
                
        else:
            # KIỂM TRA ĐIỂM BÁN
            days_held += 1
            pnl_pct = (row['close'] - buy_price) / buy_price
            sell_signal = False
            
            # Quy tắc bán:
            if pnl_pct <= -0.07:  # 1. Cắt lỗ cứng -7%
                sell_signal = True
            elif row['close'] < row['ma20']:  # 2. Gãy Trend (Thủng MA20)
                sell_signal = True
            elif days_held >= 20:  # 3. Time stop (Chỉ giữ tối đa 20 phiên để tránh kẹt vốn)
                sell_signal = True

            # Nếu có tín hiệu bán, hoặc là phiên cuối cùng của dữ liệu
            if sell_signal or i == len(df) - 1:
                sell_price = row['close']
                pnl = (sell_price - buy_price) / buy_price * 100
                
                trades.append({
                    'buy_date': buy_date,
                    'sell_date': row['date'],
                    'buy_price': buy_price,
                    'sell_price': sell_price,
                    'pnl_pct': pnl,
                    'days_held': days_held
                })
                in_position = False

    # 4. Tính toán thống kê báo cáo
    if not trades:
        return {"success": True, "symbol": symbol, "strategy": strategy, "total_trades": 0}

    df_trades = pd.DataFrame(trades)
    total_trades = len(df_trades)
    winning_trades = df_trades[df_trades['pnl_pct'] > 0]
    win_rate = (len(winning_trades) / total_trades) * 100
    avg_pnl = df_trades['pnl_pct'].mean()
    max_profit = df_trades['pnl_pct'].max()
    max_loss = df_trades['pnl_pct'].min()

    # Tính toán Max Drawdown (Sụt giảm tài khoản lớn nhất)
    equity = 100.0
    peak = 100.0
    max_dd = 0.0
    
    for pnl in df_trades['pnl_pct']:
        equity *= (1 + pnl / 100)
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100
        if dd > max_dd:
            max_dd = dd

    return {
        "success": True,
        "symbol": symbol,
        "strategy": strategy.upper(),
        "total_trades": total_trades,
        "win_rate": win_rate,
        "avg_pnl": avg_pnl,
        "max_profit": max_profit,
        "max_loss": max_loss,
        "max_dd": max_dd,
        "recent_trades": trades[-3:]  # Lấy 3 lệnh gần nhất
    }


def format_backtest_report(result: dict) -> str:
    """Định dạng kết quả backtest thành tin nhắn Telegram HTML."""
    if not result.get("success"):
        return f"❌ <b>Lỗi Backtest:</b> {result.get('error')}"

    if result.get("total_trades") == 0:
        return f"🧪 <b>BACKTEST: {result['symbol']} | {result['strategy']}</b>\n\nKhông có giao dịch nào được kích hoạt trong dữ liệu lịch sử hiện có."

    # === Báo cáo riêng cho RF_SIGNAL ===
    if result.get("is_rf"):
        msg = f"🧪 <b>BACKTEST: {result['symbol']}</b>\n"
        msg += f"⚙️ Chiến lược: <b>{result['strategy']}</b>\n"
        msg += "<i>(Tín hiệu mua/bán dựa trên xác suất Random Forest ≥ 60%)</i>\n"
        msg += "➖➖➖➖➖➖➖➖➖➖➖➖\n"
        
        msg += f"🔹 <b>Tổng số lệnh:</b> {result['total_trades']}\n"
        wr = result['win_rate']
        wr_icon = "🏆" if wr >= 50 else "⚠️"
        msg += f"{wr_icon} <b>Win Rate:</b> {wr:.1f}%\n"
        
        avg = result.get('avg_pnl', 0)
        avg_sign = "+" if avg > 0 else ""
        msg += f"📈 <b>Lãi/Lỗ trung bình/lệnh:</b> {avg_sign}{avg:.2f}%\n"
        msg += f"📉 <b>Max Drawdown:</b> -{result['max_dd']:.2f}%\n\n"
        
        # So sánh RF vs Buy & Hold (Mục 5.11)
        rf_ret = result.get('total_rf_return', 0)
        bh_ret = result.get('bh_return', 0)
        rf_sign = "+" if rf_ret >= 0 else ""
        bh_sign = "+" if bh_ret >= 0 else ""
        
        msg += "📊 <b>SO SÁNH VỚI BUY & HOLD:</b>\n"
        msg += f"▫️ RF Strategy: <b>{rf_sign}{rf_ret:.2f}%</b>\n"
        msg += f"▫️ Buy & Hold:  <b>{bh_sign}{bh_ret:.2f}%</b>\n"
        
        diff = rf_ret - bh_ret
        diff_sign = "+" if diff >= 0 else ""
        diff_icon = "✅" if diff >= 0 else "❌"
        msg += f"▫️ Alpha: {diff_icon} <b>{diff_sign}{diff:.2f}%</b>\n\n"
        
        msg += f"🔬 <b>Độ chính xác mô hình:</b> {result.get('rf_acc', 0):.1f}% (Baseline: {result.get('baseline_acc', 0):.1f}%)\n"
        msg += f"📐 <b>Macro F1:</b> {result.get('macro_f1', 0):.1f}%\n"
        msg += f"💰 <i>Chi phí giả định: {result.get('roundtrip_cost', 0.5):.2f}%/vòng (Phí + Slippage)</i>\n"
        
        # 3 lệnh gần nhất
        if result.get('recent_trades'):
            msg += "\n🗓 <b>Lệnh gần nhất:</b>\n"
            for t in result['recent_trades']:
                sign = "🟢" if t['pnl_pct'] > 0 else "🔴"
                msg += f"  {sign} {t['buy_date']} → {t['sell_date']}: <b>{t['pnl_pct']:+.2f}%</b>\n"
        
        msg += "\n⚠️ <i>Lưu ý: Đây là kết quả mô phỏng trên dữ liệu lịch sử (out-of-sample). Hiệu quả quá khứ không đảm bảo kết quả tương lai.</i>"
        return msg

    # === Báo cáo cho chiến lược TA cũ (breakout/squeeze/uptrend) ===
    msg = f"🧪 <b>BACKTEST: {result['symbol']}</b>\n"
    msg += f"⚙️ Chiến lược: <b>{result['strategy']}</b>\n"
    msg += "<i>(Quy tắc bán: Lỗ -7%, thủng MA20, hoặc giữ 20 phiên)</i>\n"
    msg += "➖➖➖➖➖➖➖➖➖➖➖➖\n"
    
    msg += f"🔹 <b>Tổng số lệnh:</b> {result['total_trades']}\n"
    
    wr = result['win_rate']
    wr_icon = "🏆" if wr >= 50 else "⚠️"
    msg += f"{wr_icon} <b>Tỷ lệ Thắng (Win Rate):</b> {wr:.1f}%\n"
    
    avg = result['avg_pnl']
    avg_sign = "+" if avg > 0 else ""
    msg += f"📈 <b>Lãi/Lỗ trung bình/lệnh:</b> {avg_sign}{avg:.2f}%\n"
    
    msg += f"📉 <b>Sụt giảm tối đa (Max Drawdown):</b> -{result['max_dd']:.2f}%\n\n"

    msg += f"🟢 Lãi lớn nhất: +{result['max_profit']:.2f}%\n"
    msg += f"🔴 Lỗ lớn nhất: {result['max_loss']:.2f}%\n\n"

    msg += "🗓 <b>3 LỆNH GẦN NHẤT:</b>\n"
    for t in result['recent_trades']:
        sign = "🟢" if t['pnl_pct'] > 0 else "🔴"
        pnl_sign = "+" if t['pnl_pct'] > 0 else ""
        msg += f"▫️ Mua <code>{t['buy_date'][:10]}</code> ➔ Bán <code>{t['sell_date'][:10]}</code>\n"
        msg += f"   {sign} PnL: <b>{pnl_sign}{t['pnl_pct']:.2f}%</b> (T+{t['days_held']})\n"

    msg += "\n⚠️ <i>Lưu ý: Bạn cần chạy lệnh /sync thường xuyên để có đủ dữ liệu lịch sử chuẩn xác nhất cho module Backtest.</i>"
    
    return msg

