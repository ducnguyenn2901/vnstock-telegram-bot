import logging
from telegram import Update
from telegram.ext import ContextTypes
import database as db

logger = logging.getLogger(__name__)

async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Xử lý lệnh /alert
    Cú pháp:
    /alert add <symbol> price <operator> <value>
    /alert list
    /alert remove <id>
    """
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        msg = (
            "🚨 <b>CÔNG CỤ CẢNH BÁO TỰ ĐỘNG</b> 🚨\n\n"
            "Các lệnh hỗ trợ:\n"
            "1. Thêm cảnh báo giá:\n"
            "<code>/alert add TCB price > 35000</code>\n"
            "<code>/alert add HPG price <= 25500</code>\n\n"
            "2. Xem danh sách cảnh báo của bạn:\n"
            "<code>/alert list</code>\n\n"
            "3. Xóa cảnh báo:\n"
            "<code>/alert remove <id></code>"
        )
        await update.message.reply_text(msg, parse_mode='HTML')
        return

    action = args[0].lower()
    
    if action == 'list':
        alerts = db.get_active_alerts(user_id=user_id)
        if not alerts:
            await update.message.reply_text("📭 Bạn chưa cài đặt cảnh báo nào.")
            return
            
        msg = "📋 <b>DANH SÁCH CẢNH BÁO CỦA BẠN:</b>\n\n"
        for a in alerts:
            msg += f"🔹 <b>ID: {a['id']}</b> | {a['symbol']} | {a['condition_type'].upper()} {a['operator']} {a['target_value']}\n"
        await update.message.reply_text(msg, parse_mode='HTML')
        
    elif action == 'remove':
        if len(args) < 2:
            await update.message.reply_text("❌ Vui lòng nhập ID cảnh báo. Ví dụ: <code>/alert remove 1</code>", parse_mode='HTML')
            return
        
        try:
            alert_id = int(args[1])
            success = db.remove_alert(alert_id, user_id)
            if success:
                await update.message.reply_text(f"✅ Đã xóa thành công cảnh báo ID: {alert_id}")
            else:
                await update.message.reply_text(f"❌ Không tìm thấy cảnh báo ID: {alert_id} hoặc bạn không có quyền xóa.")
        except ValueError:
            await update.message.reply_text("❌ ID phải là một số.")
            
    elif action == 'add':
        # Cú pháp: /alert add TCB price > 35000
        if len(args) < 5:
            await update.message.reply_text("❌ Cú pháp sai. Ví dụ: <code>/alert add TCB price > 35000</code>", parse_mode='HTML')
            return
            
        symbol = args[1].upper()
        condition_type = args[2].lower()
        operator = args[3]
        
        try:
            target_value = float(args[4])
        except ValueError:
            await update.message.reply_text("❌ Giá trị phải là số (ví dụ: 35000, 25.5)")
            return
            
        if condition_type not in ['price']:
            await update.message.reply_text("❌ Hiện tại bot chỉ mới hỗ trợ cảnh báo 'price' (giá).")
            return
            
        if operator not in ['>', '<', '>=', '<=']:
            await update.message.reply_text("❌ Toán tử không hợp lệ. Vui lòng dùng: >, <, >=, <=")
            return
            
        alert_id = db.add_alert(user_id, symbol, condition_type, operator, target_value)
        await update.message.reply_text(f"✅ Đã thêm cảnh báo (ID: {alert_id}): Báo cho tôi khi <b>{symbol} {condition_type} {operator} {target_value}</b>.", parse_mode='HTML')
        
    else:
        await update.message.reply_text("❌ Lệnh không hợp lệ. Gõ <code>/alert</code> để xem hướng dẫn.", parse_mode='HTML')
