import logging
from telegram.ext import ContextTypes
from sqlalchemy import text
import database as db
import vnstock
import pandas as pd
import config

logger = logging.getLogger("AlertChecker")

async def check_alerts_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Hàm này được gọi định kỳ bởi JobQueue.
    Lấy tất cả các cảnh báo đang active VÀ tất cả các mã trong portfolio.
    Gom nhóm theo mã chứng khoán để hạn chế gọi API nhiều lần.
    """
    alerts = db.get_active_alerts()
    
    # Lấy toàn bộ portfolio trong DB
    with db.engine.connect() as conn:
        res = conn.execute(text('SELECT * FROM portfolio WHERE quantity > 0'))
        all_portfolios = [dict(row) for row in res.mappings().all()]

    if not alerts and not all_portfolios:
        return

    # Gom nhóm symbol cần quét
    symbols = set()
    if alerts:
        symbols.update(a['symbol'] for a in alerts)
    if all_portfolios:
        symbols.update(p['symbol'] for p in all_portfolios)
        
    current_prices = {}
    try:
        mkt = vnstock.Market()
        for symbol in symbols:
            try:
                eq = mkt.equity(symbol)
                q = eq.quote()
                if q is not None and not q.empty:
                    p = float(q['close_price'].iloc[0])
                    if p <= 0 or pd.isna(p):
                        p = float(q['reference_price'].iloc[0])
                    current_prices[symbol] = p
            except SystemExit:
                logger.warning(f"Cảnh báo tự động bị chặn do đạt giới hạn API (Rate limit) khi check mã {symbol}.")
                break
            except Exception as e:
                logger.error(f"Lỗi khi lấy dữ liệu giá cho {symbol}: {e}")
    except Exception as e:
        logger.error(f"Lỗi khởi tạo Market: {e}")
            
    # 1. Kiểm tra Cảnh báo Giá (Alerts)
    if alerts:
        for alert in alerts:
            symbol = alert['symbol']
            if symbol not in current_prices:
                continue
                
            current_price = current_prices[symbol]
            target_value = float(alert['target_value'])
            
            # Chuẩn hóa nếu người dùng nhập nghìn đồng (ví dụ 32.5 thay vì 32500)
            if target_value < 1000 and current_price >= 1000:
                calc_target = target_value * 1000
            else:
                calc_target = target_value
                
            operator = alert['operator']
            is_triggered = False
            
            if alert['condition_type'] == 'price':
                if operator == '>' and current_price > calc_target:
                    is_triggered = True
                elif operator == '<' and current_price < calc_target:
                    is_triggered = True
                elif operator == '>=' and current_price >= calc_target:
                    is_triggered = True
                elif operator == '<=' and current_price <= calc_target:
                    is_triggered = True
                    
            if is_triggered:
                msg = (
                    f"🚨 <b>CẢNH BÁO GIÁ: {symbol}</b> 🚨\n\n"
                    f"Điều kiện theo dõi của bạn đã thỏa mãn!\n"
                    f"📈 Giá hiện tại: <b>{config.format_number(current_price, 0)} đ</b>\n"
                    f"🎯 Điều kiện: Giá {operator} {config.format_number(calc_target, 0)} đ\n\n"
                    f"<i>Cảnh báo này đã được tự động tắt sau khi kích hoạt.</i>"
                )
                
                try:
                    await context.bot.send_message(
                        chat_id=alert['user_id'],
                        text=msg,
                        parse_mode='HTML'
                    )
                    db.deactivate_alert(alert['id'])
                except Exception as e:
                    logger.error(f"Lỗi khi gửi tin nhắn alert {alert['id']}: {e}")

    # 2. Kiểm tra Quản trị Danh mục (Cắt lỗ -7% và Chốt lời +15%)
    if all_portfolios:
        LOSS_THRESHOLD = -7.0
        PROFIT_THRESHOLD = 15.0
        
        with db.engine.begin() as conn:
            # Lấy danh sách portfolio chưa được cảnh báo hoặc mới cảnh báo loại khác
            res = conn.execute(text('SELECT * FROM portfolio WHERE quantity > 0.0001 AND (is_alerted IS NULL OR is_alerted IN (0, 1, 2))'))
            active_portfolios = [dict(row) for row in res.mappings().all()]
            
            for p in active_portfolios:
                sym = p['symbol']
                if sym not in current_prices:
                    continue
                curr_p = current_prices[sym]
                buy_p = float(p['buy_price'])
                
                if buy_p < 1000 and curr_p >= 1000:
                    calc_buy_p = buy_p * 1000
                else:
                    calc_buy_p = buy_p
                    
                pnl_pct = ((curr_p - calc_buy_p) / calc_buy_p) * 100 if calc_buy_p > 0 else 0
                
                is_alerted_status = p.get('is_alerted', 0) or 0
                
                # Cắt lỗ (-7%) -> Ghi is_alerted = 1
                if pnl_pct <= LOSS_THRESHOLD and is_alerted_status != 1:
                    msg = (
                        f"🛑 <b>CẢNH BÁO CẮT LỖ</b> 🛑\n\n"
                        f"Mã <b>{sym}</b> trong danh mục của bạn đã giảm <b>{config.format_number(pnl_pct, 2)}%</b>!\n"
                        f"🔹 Giá mua: {config.format_number(calc_buy_p, 0)} đ\n"
                        f"🔹 Giá thị trường: {config.format_number(curr_p, 0)} đ\n\n"
                        f"⚠️ <b>Lời khuyên:</b> Hãy cân nhắc tuân thủ kỷ luật cắt lỗ để bảo vệ an toàn nguồn vốn."
                    )
                    try:
                        await context.bot.send_message(chat_id=p['user_id'], text=msg, parse_mode='HTML')
                        conn.execute(text("UPDATE portfolio SET is_alerted = 1 WHERE id = :pid"), {"pid": p['id']})
                    except Exception as e:
                        logger.error(f"Lỗi gửi Risk Alert cho user {p['user_id']}: {e}")
                        
                # Chốt lời (+15%) -> Ghi is_alerted = 2
                elif pnl_pct >= PROFIT_THRESHOLD and is_alerted_status != 2:
                    msg = (
                        f"🎉 <b>CẢNH BÁO CHỐT LỜI</b> 🎉\n\n"
                        f"Mã <b>{sym}</b> trong danh mục của bạn đã lãi <b>+{config.format_number(pnl_pct, 2)}%</b>!\n"
                        f"🔹 Giá mua: {config.format_number(calc_buy_p, 0)} đ\n"
                        f"🔹 Giá thị trường: {config.format_number(curr_p, 0)} đ\n\n"
                        f"💡 <b>Lời khuyên:</b> Bạn có thể cân nhắc hiện thực hóa lợi nhuận hoặc nâng chặn lãi (trailing stop)."
                    )
                    try:
                        await context.bot.send_message(chat_id=p['user_id'], text=msg, parse_mode='HTML')
                        conn.execute(text("UPDATE portfolio SET is_alerted = 2 WHERE id = :pid"), {"pid": p['id']})
                    except Exception as e:
                        logger.error(f"Lỗi gửi Profit Alert cho user {p['user_id']}: {e}")
