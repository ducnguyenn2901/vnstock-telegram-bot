import logging
from telegram import Update
from telegram.ext import ContextTypes
import database as db
import vnstock
import pandas as pd
import config

logger = logging.getLogger("PortfolioHandlers")

def parse_number(val_str: str) -> float:
    """Chuyển đổi chuỗi số người dùng nhập (hỗ trợ dấu . và , cho cả số thập phân và phân cách nghìn)"""
    s = str(val_str).strip().replace(" ", "")
    if not s:
        raise ValueError("Chuỗi rỗng")
        
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) != 3:
            s = s.replace(",", ".")
        elif len(parts) > 2:
            s = s.replace(",", "")
        else:
            if float(parts[0]) < 100:
                s = s.replace(",", ".")
            else:
                s = s.replace(",", "")
    elif "." in s:
        parts = s.split(".")
        if len(parts) > 2:
            s = s.replace(".", "")
        elif len(parts) == 2 and len(parts[1]) == 3 and float(parts[0]) >= 100:
            s = s.replace(".", "")
            
    return float(s)

def format_decimal(qty: float) -> str:
    """Hiển thị số lượng/giá: nếu là số nguyên thì không hiện số thập phân, nếu có lẻ thì hiện tối đa 4 số thập phân"""
    if qty == int(qty):
        return config.format_number(int(qty), 0)
    return f"{qty:,.4f}".rstrip('0').rstrip('.')

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Xử lý lệnh /buy
    Cú pháp 1 (Giá đơn vị): /buy <mã> <khối lượng> <giá 1 CP/CCQ> (VD: /buy TCB 1000 35000)
    Cú pháp 2 (Tổng tiền nạp): /buy <mã> <khối lượng> <tổng tiền> (VD: /buy DCDS 15.95 1500000)
    """
    user_id = update.effective_user.id
    args = context.args
    
    if len(args) < 3:
        await update.message.reply_text(
            "❌ <b>Cú pháp chưa đúng!</b>\n"
            "• Mua cổ phiếu: <code>/buy TCB 1000 35000</code>\n"
            "• Mua quỹ theo giá NAV: <code>/buy DCDS 15.95 93997.38</code>\n"
            "• Mua quỹ theo tổng tiền: <code>/buy DCDS 15.95 1500000</code>\n"
            "<i>(Bot tự động chia giá vốn nếu số tiền nạp &gt; 500.000 đ)</i>",
            parse_mode='HTML'
        )
        return
        
    symbol = args[0].upper().strip()
    try:
        val1 = parse_number(args[1])
        val2 = parse_number(args[2])
    except ValueError:
        await update.message.reply_text("❌ Khối lượng và giá/tiền mua phải là số hợp lệ.", parse_mode='HTML')
        return
        
    if val1 <= 0 or val2 <= 0:
        await update.message.reply_text("❌ Khối lượng và giá phải lớn hơn 0.", parse_mode='HTML')
        return

    # Tự động nhận diện nếu người dùng đảo vị trí (VD: /buy DCDS 1500000 15.95)
    if val1 > 500_000 and val2 < 500_000:
        quantity = val2
        buy_price_raw = val1
    else:
        quantity = val1
        buy_price_raw = val2

    # Tự động quy đổi nếu nhập giá < 1000 (ví dụ cổ phiếu giá 35 -> 35000)
    if buy_price_raw < 1000:
        buy_price = buy_price_raw * 1000
        is_total_cash = False
    elif buy_price_raw > 500_000:
        # Nếu nhập số tiền lớn (> 500.000 đ), tự động hiểu là Tổng tiền nạp cho đợt này
        buy_price = buy_price_raw / quantity
        is_total_cash = True
    else:
        buy_price = buy_price_raw
        is_total_cash = False
        
    db.buy_stock(user_id, symbol, quantity, buy_price)
    
    unit_label = "CCQ" if (4 <= len(symbol) <= 6 and not symbol.startswith("FUE") and not symbol.startswith("E1V")) else "cổ phiếu"
    
    extra_note = "\n<i>💡 Bot đã tự động nhận diện tổng tiền nạp và quy đổi giá vốn cho bạn.</i>" if is_total_cash else ""
    
    msg = (
        f"✅ <b>GHI NHẬN MUA THÀNH CÔNG</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 Mã tài sản: <b>{symbol}</b>\n"
        f"📦 Khối lượng: <b>{format_decimal(quantity)}</b> {unit_label}\n"
        f"💵 Giá vốn quy đổi: <b>{format_decimal(buy_price)} đ</b> / {unit_label}\n"
        f"💰 Tổng tiền đầu tư đợt này: <b>{format_decimal(quantity * buy_price)} đ</b>\n"
        f"{extra_note}\n"
        f"<i>Gõ <code>/portfolio</code> để xem danh mục tích lũy tổng thể.</i>"
    )
    
    await update.message.reply_text(msg, parse_mode='HTML')

async def dca_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias chuyên biệt cho lệnh đầu tư định kỳ: /dca <MÃ> <TỔNG_TIỀN> <SỐ_CCQ> hoặc ngược lại"""
    return await buy_command(update, context)

async def sell_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Xử lý lệnh /sell
    Cú pháp: /sell <mã> <khối lượng>
    VD: /sell TCB 500 hoặc /sell DCDS 13.43
    """
    user_id = update.effective_user.id
    args = context.args
    
    if len(args) < 2:
        await update.message.reply_text("❌ <b>Cú pháp chưa đúng!</b>\nVí dụ: <code>/sell TCB 500</code> hoặc <code>/sell DCDS 13.43</code>", parse_mode='HTML')
        return
        
    symbol = args[0].upper().strip()
    try:
        sell_qty = parse_number(args[1])
    except ValueError:
        await update.message.reply_text("❌ Khối lượng bán phải là số hợp lệ.", parse_mode='HTML')
        return
        
    if sell_qty <= 0:
        await update.message.reply_text("❌ Khối lượng bán phải lớn hơn 0.", parse_mode='HTML')
        return
        
    remaining = db.sell_stock(user_id, symbol, sell_qty)
    unit_label = "CCQ" if (4 <= len(symbol) <= 6 and not symbol.startswith("FUE") and not symbol.startswith("E1V")) else "cổ phiếu"
    
    if remaining == sell_qty:
        await update.message.reply_text(f"❌ Bạn không sở hữu mã <b>{symbol}</b> trong danh mục hoặc không đủ số lượng.", parse_mode='HTML')
    elif remaining > 0:
        sold = sell_qty - remaining
        await update.message.reply_text(
            f"⚠️ Đã bán <b>{format_decimal(sold)}</b> {symbol}. Còn dư <b>{format_decimal(remaining)}</b> {unit_label} do vượt quá số lượng đang có.",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(f"✅ Đã bán thành công <b>{format_decimal(sell_qty)}</b> {unit_label} <b>{symbol}</b> khỏi danh mục.", parse_mode='HTML')

async def portfolio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Xử lý lệnh /portfolio
    Hiển thị danh mục đầu tư, tính toán PnL.
    """
    user_id = update.effective_user.id
    portfolio_rows = db.get_portfolio(user_id)
    
    if not portfolio_rows:
        await update.message.reply_text(
            "📭 Danh mục của bạn hiện đang trống.\n\n"
            "Hãy dùng lệnh <code>/buy &lt;MÃ&gt; &lt;KL&gt; &lt;GIÁ&gt;</code> để thêm cổ phiếu vào sổ tay theo dõi!",
            parse_mode='HTML'
        )
        return
        
    wait_msg = await update.message.reply_text("⏳ Đang kết nối bảng giá thị trường để tính toán PnL...", parse_mode='HTML')
    
    symbols = set(row['symbol'] for row in portfolio_rows)
    current_prices = {}
    
    try:
        mkt = vnstock.Market()
        import modules.fund_data as fd
        for symbol in symbols:
            try:
                # 1. Thử lấy giá cổ phiếu/ETF trên sàn
                eq = mkt.equity(symbol)
                q = eq.quote()
                if q is not None and not q.empty and 'close_price' in q.columns:
                    p = float(q['close_price'].iloc[0])
                    if p <= 0 or pd.isna(p):
                        p = float(q['reference_price'].iloc[0])
                    if p > 0:
                        current_prices[symbol] = p
                        continue
            except Exception:
                pass
                
            # 2. Nếu không có giá sàn, thử tra cứu giá NAV của Quỹ Mở
            try:
                fund_res = fd.get_fund_info(symbol)
                if fund_res.get("success"):
                    nav = float(fund_res["info"].get("nav", 0))
                    if nav > 0:
                        current_prices[symbol] = nav
            except Exception as fe:
                logger.error(f"Lỗi lấy NAV quỹ mở cho {symbol}: {fe}")
    except Exception as e:
        logger.error(f"Lỗi khởi tạo Market: {e}")
            
    total_invested = 0
    total_current_value = 0
    
    # Gom tổng hợp theo từng mã
    summary_by_symbol = {}
    for row in portfolio_rows:
        sym = row['symbol']
        qty = row['quantity']
        buy_p = float(row['buy_price'])
        if buy_p < 1000:
            buy_p *= 1000
            
        if sym not in summary_by_symbol:
            summary_by_symbol[sym] = {'qty': 0, 'cost': 0}
            
        summary_by_symbol[sym]['qty'] += qty
        summary_by_symbol[sym]['cost'] += (qty * buy_p)
        
    msg = "💼 <b>DANH MỤC ĐẦU TƯ CỦA BẠN</b>\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    
    for sym, data in summary_by_symbol.items():
        qty = data['qty']
        
        # Bỏ qua các mã rác do sai số dấu phẩy động (đã bán hết)
        if qty < 0.0001:
            continue
            
        cost = data['cost']
        avg_price = cost / qty if qty > 0 else 0
        
        curr_p = current_prices.get(sym, avg_price)
        curr_val = qty * curr_p
        
        pnl = curr_val - cost
        pnl_pct = (pnl / cost) * 100 if cost > 0 else 0
        
        total_invested += cost
        total_current_value += curr_val
        
        sign = "🟢" if pnl >= 0 else "🔴"
        pnl_sign = "+" if pnl > 0 else ""
        unit_lbl = "CCQ" if (4 <= len(sym) <= 6 and not sym.startswith("FUE") and not sym.startswith("E1V")) else "CP"
        
        msg += f"📌 <b>{sym}</b> | SL: <b>{format_decimal(qty)}</b> {unit_lbl}\n"
        msg += f"• Giá vốn: <code>{format_decimal(avg_price)} đ</code>\n"
        msg += f"• Giá TT: <code>{format_decimal(curr_p)} đ</code>\n"
        msg += f"• Lãi/Lỗ: {sign} <b>{pnl_sign}{config.format_number(pnl, 0)} đ ({pnl_sign}{config.format_number(pnl_pct, 2)}%)</b>\n"
        msg += "──────────────────\n"
        
    total_pnl = total_current_value - total_invested
    total_pnl_pct = (total_pnl / total_invested) * 100 if total_invested > 0 else 0
    t_sign = "🟢" if total_pnl >= 0 else "🔴"
    t_pnl_sign = "+" if total_pnl > 0 else ""
    
    msg += f"💰 <b>Tổng vốn đầu tư:</b> <code>{config.format_number(total_invested, 0)} đ</code>\n"
    msg += f"💵 <b>Giá trị hiện tại:</b> <code>{config.format_number(total_current_value, 0)} đ</code>\n"
    msg += f"📊 <b>Tổng Lãi/Lỗ:</b> {t_sign} <b>{t_pnl_sign}{config.format_number(total_pnl, 0)} đ ({t_pnl_sign}{config.format_number(total_pnl_pct, 2)}%)</b>\n"
    
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = [
        [InlineKeyboardButton("🤖 AI Tư Vấn Danh Mục", callback_data=f"ai_port:{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await wait_msg.edit_text(msg, parse_mode='HTML', reply_markup=reply_markup)
