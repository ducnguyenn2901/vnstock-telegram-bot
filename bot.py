# -*- coding: utf-8 -*-
"""
Telegram Bot Phân Tích Chứng Khoán Vnstock Toàn Diện.
Tác giả: Duc Nguyen
"""

import os
import sys
import logging
import asyncio

# Đảm bảo đường dẫn thư mục dự án luôn nằm trong sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import config
from modules.reference_data import get_reference_data, format_reference_html
from modules.market_data import get_market_quote, format_market_html
from modules.fundamental_data import get_fundamental_data, format_fundamental_html
from modules.macro_data import get_macro_overview, format_macro_html
from modules.technical_analysis import get_technical_analysis, format_technical_html
from modules.valuation_stats import get_valuation_and_stats, format_valuation_html
from modules.news_events import get_company_news, format_news_html
from modules.chart_generator import generate_technical_chart, generate_financial_chart
import database as db
from modules.alert_handlers import alert_command
from modules.alert_checker import check_alerts_job
from modules.portfolio_handlers import buy_command, sell_command, portfolio_command
from modules.screener_handlers import screen_command
import modules.ai_assistant as ai_module

# Khởi tạo CSDL nếu chưa có
db.init_db()

logger = logging.getLogger("VnstockTelegramBot")

def get_symbol_keyboard(symbol: str) -> InlineKeyboardMarkup:
    """Tạo bàn phím nút bấm tương tác cho từng mã cổ phiếu."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Giá & Lệnh", callback_data=f"mkt:{symbol}"),
            InlineKeyboardButton("🏢 Hồ sơ", callback_data=f"ref:{symbol}"),
        ],
        [
            InlineKeyboardButton("📈 Kỹ thuật", callback_data=f"ta:{symbol}"),
            InlineKeyboardButton("💰 Cơ bản", callback_data=f"fun:{symbol}"),
        ],
        [
            InlineKeyboardButton("⚖️ Định giá", callback_data=f"val:{symbol}"),
            InlineKeyboardButton("📰 Tin tức", callback_data=f"news:{symbol}"),
        ],
        [
            InlineKeyboardButton("🖼 Biểu đồ Kỹ thuật", callback_data=f"chart:{symbol}"),
            InlineKeyboardButton("📊 Biểu đồ Tài chính", callback_data=f"chart_fa:{symbol}"),
        ],
        [
            InlineKeyboardButton("🤖 AI Đánh Giá", callback_data=f"ai:{symbol}"),
            InlineKeyboardButton("🦈 Cá Mập", callback_data=f"shark:{symbol}"),
            InlineKeyboardButton("🔮 Dự báo", callback_data=f"predict:{symbol}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /start và /help."""
    welcome_text = (
        "👋 <b>Chào mừng bạn đến với Vnstock Telegram Bot!</b>\n\n"
        "Tôi là trợ lý AI phân tích thị trường chứng khoán Việt Nam.\n\n"
        "<b>Các lệnh cơ bản:</b>\n"
        "🔹 <code>/analyze &lt;MÃ&gt;</code> - Phân tích toàn diện 1 mã\n"
        "🔹 <code>/quick &lt;MÃ&gt;</code> - Xem nhanh giá và xu hướng\n"
        "🔹 <code>/chart &lt;MÃ&gt;</code> - Vẽ biểu đồ kỹ thuật\n"
        "🔹 <code>/macro</code> - Tóm tắt thị trường chung\n"
        "🔹 <code>/news</code> - Nhận Bản Tin Sáng AI (RAG)\n"
        "🔹 <code>/alert</code> - Cài đặt cảnh báo giá\n"
        "🔹 <code>/shark &lt;MÃ&gt;</code> - Dò dòng tiền Cá Mập\n"
        "🔹 <code>/predict &lt;MÃ&gt;</code> - Dự báo xu hướng (AI Quant)\n"
        "🔹 <code>/backtest &lt;MÃ&gt; &lt;CL&gt;</code> - Test chiến lược quá khứ\n"
        "🔹 <code>/screen</code> - Máy quét cổ phiếu tiềm năng\n"
        "🔹 <code>/fund &lt;MÃ&gt;</code> - Tra cứu Chứng chỉ Quỹ Mở (Ví dụ: VESAF, DCDS)\n"
        "🔹 <code>/sync</code> - Đồng bộ Kho Dữ Liệu nội bộ\n\n"
        "<b>Quản lý Danh mục:</b>\n"
        "🔹 <code>/buy &lt;MÃ&gt; &lt;KL&gt; &lt;GIÁ&gt;</code> - Mua cổ phiếu\n"
        "🔹 <code>/sell &lt;MÃ&gt; &lt;KL&gt;</code> - Bán cổ phiếu\n"
        "🔹 <code>/portfolio</code> - Xem tổng kết lãi/lỗ\n\n"
        "💡 <i>Mẹo: Gõ trực tiếp tên mã (VD: <b>VNM</b> hoặc <b>VESAF</b>) vào chat để tôi phân tích nhé!</i>"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)

async def macro_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /macro."""
    msg = await update.message.reply_text("⏳ Đang tải dữ liệu vĩ mô thị trường...")
    data = get_macro_overview()
    html = format_macro_html(data)
    await msg.edit_text(html, parse_mode=ParseMode.HTML)

async def quick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /quick <MÃ>."""
    if not context.args:
        await update.message.reply_text("⚠️ Vui lòng nhập mã cổ phiếu. Ví dụ: <code>/quick FPT</code>", parse_mode=ParseMode.HTML)
        return
    symbol = context.args[0].upper().strip()
    msg = await update.message.reply_text(f"⏳ Đang lấy dữ liệu giao dịch cho <b>{symbol}</b>...", parse_mode=ParseMode.HTML)
    data = get_market_quote(symbol)
    html = format_market_html(data)
    await msg.edit_text(html, parse_mode=ParseMode.HTML, reply_markup=get_symbol_keyboard(symbol))

async def chart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /chart <MÃ>."""
    if not context.args:
        await update.message.reply_text("⚠️ Vui lòng nhập mã cổ phiếu. Ví dụ: <code>/chart HPG</code>", parse_mode=ParseMode.HTML)
        return
    symbol = context.args[0].upper().strip()
    msg = await update.message.reply_text(f"⏳ Đang khởi tạo biểu đồ kỹ thuật cho <b>{symbol}</b>...", parse_mode=ParseMode.HTML)
    buf = generate_technical_chart(symbol, days=90)
    if buf:
        await update.message.reply_photo(
            photo=buf,
            caption=f"📉 <b>Biểu đồ kỹ thuật: {symbol}</b> (Nến Nhật, MA20, MA50, Bollinger Bands & RSI)",
            parse_mode=ParseMode.HTML,
            reply_markup=get_symbol_keyboard(symbol)
        )
        await msg.delete()
    else:
        await msg.edit_text(f"❌ Không thể tạo biểu đồ cho mã <b>{symbol}</b>.", parse_mode=ParseMode.HTML)

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /analyze <MÃ> hoặc khi người dùng gõ mã cổ phiếu."""
    symbol = None
    if context.args:
        symbol = context.args[0].upper().strip()
    elif update.message and update.message.text:
        text = update.message.text.strip().upper()
        if len(text) == 3 and text.isalpha():
            symbol = text
            
    if not symbol:
        await update.message.reply_text("⚠️ Vui lòng nhập mã cổ phiếu. Ví dụ: <code>/analyze TCB</code> hoặc gõ trực tiếp <code>TCB</code>", parse_mode=ParseMode.HTML)
        return
        
    msg = await update.message.reply_text(f"🔍 Đang phân tích đa chiều cho mã <b>{symbol}</b>, xin vui lòng chờ giây lát...", parse_mode=ParseMode.HTML)
    
    # Lấy nhanh dữ liệu tổng quan
    mkt = get_market_quote(symbol)
    ta = get_technical_analysis(symbol)
    val = get_valuation_and_stats(symbol)
    
    q = mkt.get("quote", {})
    price = q.get("close_price", 0)
    change = q.get("price_change", 0)
    pct = q.get("percent_change", 0)
    sign = "+" if change > 0 else ""
    
    v_dict = val.get("valuation", {})
    pe = v_dict.get("pe", "N/A")
    pb = v_dict.get("pb", "N/A")
    roe = v_dict.get("roe", "N/A")
    verdict = ta.get("verdict", "N/A")
    
    summary_html = [
        f"🎯 <b>TỔNG QUAN PHÂN TÍCH: {symbol}</b>",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"• <b>Giá hiện tại:</b> <code>{config.format_number(price, 0)}</code> ({sign}{config.format_number(change, 0)} / {sign}{config.format_number(pct, 2)}%)",
        f"• <b>Đánh giá Kỹ thuật:</b> <b>{verdict}</b>",
        f"• <b>Định giá:</b> P/E: <b>{config.format_number(pe, 2)}x</b> | P/B: <b>{config.format_number(pb, 2)}x</b>",
        f"• <b>RSI(14):</b> {config.format_number(ta.get('indicators', {}).get('rsi'), 1)}",
        f"\n<i>Bấm vào các nút bên dưới để xem chi tiết từng nhóm phân tích:</i>"
    ]
    
    await msg.edit_text(
        "\n".join(summary_html),
        parse_mode=ParseMode.HTML,
        reply_markup=get_symbol_keyboard(symbol)
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý sự kiện khi người dùng bấm vào các nút Inline Keyboard."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if ":" not in data:
        return
        
    action, symbol = data.split(":", 1)
    symbol = symbol.upper()
    
    # Helper gửi text
    async def _send_or_edit_text(html_text, disable_preview=False):
        if query.message.photo:
            await query.message.delete()
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=html_text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_symbol_keyboard(symbol),
                disable_web_page_preview=disable_preview
            )
        else:
            await query.edit_message_text(
                html_text, 
                parse_mode=ParseMode.HTML, 
                reply_markup=get_symbol_keyboard(symbol),
                disable_web_page_preview=disable_preview
            )
            
    if action == "mkt":
        mkt_data = get_market_quote(symbol)
        html = format_market_html(mkt_data)
        await _send_or_edit_text(html)
        
    elif action == "ref":
        ref_data = get_reference_data(symbol)
        html = format_reference_html(ref_data)
        await _send_or_edit_text(html)
        
    elif action == "fun":
        fun_data = get_fundamental_data(symbol)
        html = format_fundamental_html(fun_data)
        await _send_or_edit_text(html)
        
    elif action == "ta":
        ta_data = get_technical_analysis(symbol)
        html = format_technical_html(ta_data)
        await _send_or_edit_text(html)
        
    elif action == "val":
        val_data = get_valuation_and_stats(symbol)
        html = format_valuation_html(val_data)
        await _send_or_edit_text(html)
        
    elif action == "news":
        news_data = get_company_news(symbol)
        html = format_news_html(news_data)
        await _send_or_edit_text(html, disable_preview=True)
        
    elif action == "chart":
        buf = generate_technical_chart(symbol, days=90)
        if buf:
            if query.message.photo:
                await query.message.delete()
            chat_id = query.message.chat_id
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=buf,
                caption=f"📈 <b>Biểu đồ kỹ thuật: {symbol}</b> (Nến Nhật, MA20, MA50, Bollinger Bands & RSI)",
                parse_mode=ParseMode.HTML,
                reply_markup=get_symbol_keyboard(symbol)
            )
        else:
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"❌ Không thể tạo biểu đồ kỹ thuật cho mã <b>{symbol}</b>.", parse_mode=ParseMode.HTML)
            
    elif action == "chart_fa":
        buf = generate_financial_chart(symbol)
        if buf:
            if query.message.photo:
                await query.message.delete()
            chat_id = query.message.chat_id
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=buf,
                caption=f"📊 <b>Biểu đồ Tài chính: {symbol}</b> (Doanh thu & Lợi nhuận 4 quý gần nhất)",
                parse_mode=ParseMode.HTML,
                reply_markup=get_symbol_keyboard(symbol)
            )
        else:
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"❌ Không thể tạo biểu đồ tài chính cho mã <b>{symbol}</b>.", parse_mode=ParseMode.HTML)

    elif action == "ai":
        await query.message.reply_text("🤖 AI đang tổng hợp dữ liệu và phân tích. Vui lòng đợi trong giây lát...", parse_mode=ParseMode.HTML)
        # Vì gọi AI có thể mất vài giây, nên đưa vào hàm gọi bất đồng bộ hoặc chạy thẳng
        ai_response = ai_module.get_ai_evaluation(symbol)
        await query.message.reply_text(f"🤖 AI ĐÁNH GIÁ MÃ {symbol}\n\n{ai_response}")
        
    elif action == "shark":
        await query.message.reply_text(f"⏳ Đang dò quét dữ liệu khớp lệnh (tick-by-tick) của mã {symbol}...", parse_mode=ParseMode.HTML)
        from modules.smart_money import get_shark_trades, format_shark_message
        df_sharks = get_shark_trades(symbol, min_value_vnd=5_000_000_000)
        msg = format_shark_message(symbol, df_sharks, min_value_vnd=5_000_000_000)
        await query.message.reply_text(msg, parse_mode=ParseMode.HTML)
        
    elif action == "predict":
        await query.message.reply_text(f"🧠 Đang huấn luyện siêu mô hình Random Forest cho mã <b>{symbol}</b>. Quá trình này mất khoảng vài giây...", parse_mode=ParseMode.HTML)
        import modules.ml_predictor as ml
        res = ml.train_and_predict(symbol, target_days=3)
        msg = ml.format_prediction_message(res)
        await query.message.reply_text(msg, parse_mode=ParseMode.HTML)

    elif action == "ai_port":
        # Tách user_id (dù thực ra current_user_id cũng được)
        port_uid = int(symbol)
        if query.from_user.id != port_uid:
            await query.answer("❌ Bạn không có quyền xem danh mục của người khác!", show_alert=True)
            return
            
        await query.answer("🤖 AI đang đọc danh mục...")
        await query.message.reply_text("🤖 AI đang phân tích rủi ro và đánh giá danh mục của bạn. Vui lòng đợi trong giây lát...", parse_mode=ParseMode.HTML)
        
        # Parse nội dung tin nhắn hiện tại làm string gửi cho AI
        portfolio_str = query.message.text
        ai_response = ai_module.evaluate_portfolio(portfolio_str)
        await query.message.reply_text(f"🤖 AI TƯ VẤN DANH MỤC\n\n{ai_response}")

async def market_news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh gọi AI tóm tắt tin tức thị trường"""
    await update.message.reply_text("📰 Đang thu thập điểm báo và gửi cho AI phân tích. Vui lòng đợi...", parse_mode=ParseMode.HTML)
    ai_response = ai_module.summarize_market_news()
    await update.message.reply_text(f"🌅 BẢN TIN SÁNG AI\n\n{ai_response}")

async def shark_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh dò tìm dòng tiền cá mập (Chạy ngầm tránh block bot)"""
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ <b>Cú pháp chưa đúng!</b>\nVí dụ: <code>/shark TCB</code>", parse_mode=ParseMode.HTML)
        return
        
    symbol = args[0].upper().strip()
    chat_id = update.message.chat_id
    await update.message.reply_text(f"⏳ Đang chạy ngầm dò quét dữ liệu khớp lệnh cá mập cho mã <b>{symbol}</b>...\n<i>(Bot sẽ thông báo cho bạn ngay khi quét xong)</i>", parse_mode=ParseMode.HTML)
    
    async def run_shark_task():
        from modules.smart_money import get_shark_trades, format_shark_message
        try:
            # Chạy hàm đồng bộ trong thread riêng để không treo bot
            df_sharks = await asyncio.to_thread(get_shark_trades, symbol, 5_000_000_000)
            
            # Xử lý kết quả trả về
            if df_sharks is None:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ Mã cổ phiếu <b>{symbol}</b> không hợp lệ, không có dữ liệu, hoặc hệ thống đang bị giới hạn. Vui lòng kiểm tra lại!", parse_mode='HTML')
            else:
                msg = format_shark_message(symbol, df_sharks, min_value_vnd=5_000_000_000)
                await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode='HTML')
                await context.bot.send_message(chat_id=chat_id, text=f"✅ <b>HOÀN TẤT:</b> Quá trình chạy ngầm dò quét mã {symbol} đã xong!", parse_mode='HTML')
        except Exception as e:
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Có lỗi xảy ra khi quét mã {symbol}: {e}")
            
    # Đẩy vào chạy nền
    asyncio.create_task(run_shark_task())

async def predict_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh dự báo AI Quant bằng Machine Learning (Chạy ngầm)"""
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ <b>Cú pháp chưa đúng!</b>\nVí dụ: <code>/predict SSI</code>", parse_mode=ParseMode.HTML)
        return
        
    symbol = args[0].upper().strip()
    chat_id = update.message.chat_id
    await update.message.reply_text(f"🧠 Đang chạy ngầm huấn luyện mô hình ML cho mã <b>{symbol}</b>...\n<i>(Bot sẽ thông báo khi quá trình học hoàn tất)</i>", parse_mode=ParseMode.HTML)
    
    async def run_predict_task():
        import modules.ml_predictor as ml
        try:
            res = await asyncio.to_thread(ml.train_and_predict, symbol, 3)
            if "error" in res:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ Mã cổ phiếu <b>{symbol}</b> không hợp lệ hoặc dữ liệu không đủ để huấn luyện.", parse_mode='HTML')
            else:
                msg = ml.format_prediction_message(res)
                await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode='HTML')
                await context.bot.send_message(chat_id=chat_id, text=f"✅ <b>HOÀN TẤT:</b> Quá trình học máy mô hình cho {symbol} đã xong!", parse_mode='HTML')
        except Exception as e:
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Có lỗi trong quá trình học máy: {e}")
            
    asyncio.create_task(run_predict_task())

async def backtest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh chạy Backtest lịch sử chiến lược (Chạy ngầm)"""
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("⚠️ <b>Cú pháp chưa đúng!</b>\nVí dụ: <code>/backtest TCB breakout</code>\n(Chiến lược: breakout, squeeze, uptrend)", parse_mode=ParseMode.HTML)
        return
        
    symbol = args[0].upper().strip()
    strategy = args[1].lower().strip()
    chat_id = update.message.chat_id
    
    await update.message.reply_text(f"🧪 Đang chạy ngầm cỗ máy thời gian mô phỏng chiến lược <b>{strategy}</b> trên mã <b>{symbol}</b>...\n<i>(Bạn cứ làm việc khác, bot sẽ gửi báo cáo khi xong)</i>", parse_mode=ParseMode.HTML)
    
    async def run_backtest_task():
        import modules.backtester as bt
        try:
            res = await asyncio.to_thread(bt.run_backtest, symbol, strategy)
            if "error" in res:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ Lỗi Backtest: <b>{res.get('error', 'Mã cổ phiếu không hợp lệ hoặc dữ liệu không đủ.')}</b>", parse_mode='HTML')
            else:
                msg = bt.format_backtest_report(res)
                await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode='HTML')
                await context.bot.send_message(chat_id=chat_id, text=f"✅ <b>HOÀN TẤT:</b> Quá trình Backtest mô phỏng mã {symbol} đã xong!", parse_mode='HTML')
        except Exception as e:
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Có lỗi trong quá trình Backtest: {e}")
            
    asyncio.create_task(run_backtest_task())

async def fund_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /fund <MÃ> cho quỹ mở"""
    if not context.args:
        await update.message.reply_text("⚠️ Vui lòng nhập mã chứng chỉ quỹ mở. Ví dụ: <code>/fund VESAF</code>", parse_mode=ParseMode.HTML)
        return
        
    symbol = context.args[0].upper().strip()
    msg = await update.message.reply_text(f"⏳ Đang tra cứu thông tin Quỹ Mở <b>{symbol}</b>...", parse_mode=ParseMode.HTML)
    
    import modules.fund_data as fd
    # Gọi qua to_thread vì fmarket API có thể chậm
    data = await asyncio.to_thread(fd.get_fund_info, symbol)
    html = fd.format_fund_html(data)
    await msg.edit_text(html, parse_mode=ParseMode.HTML)

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bắt các tin nhắn dạng text thông thường."""
    text = update.message.text.strip()
    text_upper = text.upper()
    
    # Tự động nhận diện Mã cổ phiếu (3 chữ cái) hoặc ETF (bắt đầu bằng FUE, E1V)
    is_stock_or_etf = (len(text_upper) == 3 and text_upper.isalpha()) or text_upper.startswith("FUE") or text_upper.startswith("E1V")
    # Tự động nhận diện Quỹ Mở (4-6 chữ cái)
    is_open_fund = 4 <= len(text_upper) <= 6 and text_upper.isalpha() and not is_stock_or_etf

    if is_stock_or_etf:
        context.args = [text_upper]
        await analyze_command(update, context)
    elif is_open_fund:
        context.args = [text_upper]
        await fund_command(update, context)
    else:
        # Xử lý chat tự do với AI có bộ nhớ
        await update.message.chat.send_action(action="typing")
        user_id = update.message.from_user.id
        
        try:
            # Chạy ngầm tránh block bot
            ai_reply = await asyncio.to_thread(ai_module.chat_with_ai, text, user_id)
            await update.message.reply_text(ai_reply)
        except Exception as e:
            await update.message.reply_text(f"❌ AI gặp lỗi: {e}")

async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh kích hoạt đồng bộ dữ liệu EOD (Local Data Warehouse)"""
    chat_id = update.message.chat_id
    await update.message.reply_text("⏳ Đang khởi chạy tiến trình đồng bộ Kho dữ liệu (VN100)... Việc này sẽ diễn ra ngầm và tốn khoảng 3-5 phút.", parse_mode=ParseMode.HTML)
    
    async def run_sync_task():
        from modules.data_sync import sync_all_stocks_data
        try:
            await sync_all_stocks_data(context)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ <b>TỰ ĐỘNG ĐỒNG BỘ HOÀN TẤT</b>\nĐã tải xong dữ liệu EOD cho các mã VN100 vào Kho dữ liệu nội bộ (Supabase/SQLite).",
                parse_mode='HTML'
            )
        except Exception as e:
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Lỗi chạy ngầm (Sync): {str(e)}")
            
    # Chạy task nền
    asyncio.create_task(run_sync_task())

def start_health_check_server():
    """Khởi động web server mini để Render nhận diện port và duy trì kết nối."""
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler
    
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Vnstock Telegram Bot is running 24/7!")
            
        def log_message(self, format, *args):
            pass  # Ẩn log ping định kỳ để terminal gọn gàng
            
    port = int(os.environ.get("PORT", 8080))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        print(f"🌐 Đã mở cổng Health Check Server trên PORT: {port}")
    except Exception as e:
        print(f"⚠️ Không thể mở port web: {e}")

def main():
    """Điểm khởi chạy ứng dụng Telegram Bot."""
    token = config.TELEGRAM_BOT_TOKEN
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("❌ CHƯA CẤU HÌNH TELEGRAM_BOT_TOKEN!")
        return
        
    # Chạy Web Server nền nếu đang chạy trên Cloud (như Render)
    start_health_check_server()
        
    print("🚀 Đang khởi động Vnstock Telegram Bot...")
    app = Application.builder().token(token).build()
    
    # Đăng ký Handlers
    app.add_handler(CommandHandler(["start", "help"], start_command))
    app.add_handler(CommandHandler(["analyze", "pt"], analyze_command))
    app.add_handler(CommandHandler("quick", quick_command))
    app.add_handler(CommandHandler("chart", chart_command))
    app.add_handler(CommandHandler("macro", macro_command))
    app.add_handler(CommandHandler("alert", alert_command))
    app.add_handler(CommandHandler("buy", buy_command))
    app.add_handler(CommandHandler("sell", sell_command))
    app.add_handler(CommandHandler("portfolio", portfolio_command))
    app.add_handler(CommandHandler("screen", screen_command))
    app.add_handler(CommandHandler("sync", sync_command))
    app.add_handler(CommandHandler("news", market_news_command))
    app.add_handler(CommandHandler("shark", shark_command))
    app.add_handler(CommandHandler("predict", predict_command))
    app.add_handler(CommandHandler("backtest", backtest_command))
    app.add_handler(CommandHandler("fund", fund_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    
    # Thiết lập JobQueue cho Cảnh báo tự động (Alerts) và Đồng bộ dữ liệu (Cron Job)
    if app.job_queue:
        # 1. Cảnh báo giá chạy mỗi 5 phút
        app.job_queue.run_repeating(check_alerts_job, interval=300, first=10)
        
        # 2. Đồng bộ Kho Dữ Liệu EOD tự động lúc 15:20 (Giờ VN) từ Thứ 2 đến Thứ 6
        import datetime
        from modules.data_sync import sync_all_stocks_data
        vn_tz = datetime.timezone(datetime.timedelta(hours=7))
        sync_time = datetime.time(hour=15, minute=20, tzinfo=vn_tz)
        app.job_queue.run_daily(sync_all_stocks_data, time=sync_time, days=(1, 2, 3, 4, 5))
        print("⏰ Đã thiết lập Cron Job đồng bộ dữ liệu lúc 15:20 tự động (T2-T6).")
        
    print("✅ Bot đang hoạt động! Nhấn Ctrl+C để dừng bot.")
    app.run_polling()

if __name__ == "__main__":
    main()
