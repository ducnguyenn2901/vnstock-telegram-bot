import logging
import google.generativeai as genai
import config
from modules.reference_data import get_reference_data
from modules.market_data import get_market_quote
from modules.fundamental_data import get_fundamental_data
from modules.technical_analysis import get_technical_analysis
from modules.valuation_stats import get_valuation_and_stats

logger = logging.getLogger("AIAssistant")

# Khởi tạo Gemini
if config.GEMINI_API_KEY:
    genai.configure(api_key=config.GEMINI_API_KEY)
else:
    logger.warning("Chưa cấu hình GEMINI_API_KEY. Tính năng AI sẽ không hoạt động.")

def _format_dict_for_prompt(title, data):
    """Định dạng dữ liệu thành văn bản để gửi cho AI"""
    if not data:
        return f"--- {title} ---\nKhông có dữ liệu\n"
    text = f"--- {title} ---\n"
    for k, v in data.items():
        text += f"{k}: {v}\n"
    return text + "\n"

def get_ai_evaluation(symbol: str) -> str:
    """Thu thập toàn bộ thông tin mã cổ phiếu và yêu cầu AI phân tích."""
    if not config.GEMINI_API_KEY:
        return "❌ Tính năng AI chưa được cấu hình (Thiếu GEMINI_API_KEY). Hãy cấu hình trong file .env."
        
    symbol = symbol.upper()
    try:
        # Gom dữ liệu
        ref_data = get_reference_data(symbol)
        mkt_data = get_market_quote(symbol)
        fun_data = get_fundamental_data(symbol)
        ta_data = get_technical_analysis(symbol)
        val_data = get_valuation_and_stats(symbol)
        
        # Build prompt
        prompt = f"Bạn là một chuyên gia phân tích chứng khoán chuyên nghiệp tại Việt Nam. Hãy đánh giá ngắn gọn, súc tích (khoảng 150-250 từ) về mã cổ phiếu {symbol} dựa trên các dữ liệu sau đây:\n\n"
        
        prompt += _format_dict_for_prompt("Hồ sơ công ty", ref_data)
        prompt += _format_dict_for_prompt("Thị trường hiện tại", mkt_data)
        prompt += _format_dict_for_prompt("Kỹ thuật (MA, RSI, BB)", ta_data)
        prompt += _format_dict_for_prompt("Cơ bản & Định giá", {**(fun_data or {}), **(val_data or {})})
        
        prompt += "Yêu cầu:\n1. Tóm tắt điểm tích cực và tiêu cực.\n2. Đưa ra nhận định xu hướng ngắn hạn và dài hạn.\n3. Kết luận: Có nên cân nhắc MUA, BÁN hay GIỮ không và rủi ro là gì.\nĐịnh dạng trả về: Sử dụng định dạng văn bản bình thường, có thể dùng emoji."
        
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        
        return response.text
        
    except Exception as e:
        logger.error(f"Lỗi khi gọi AI phân tích {symbol}: {e}")
        return "❌ Đã có lỗi xảy ra khi kết nối với AI. Vui lòng thử lại sau."

def chat_with_ai(user_message: str, user_id: int = None) -> str:
    """Cho phép chat tự do với AI có bộ nhớ (Memory)."""
    if not config.GEMINI_API_KEY:
        return "❌ Tính năng AI chưa được cấu hình. (Thiếu GEMINI_API_KEY)"
        
    try:
        import database as db
        system_prompt = "Bạn là trợ lý AI chuyên về chứng khoán Việt Nam (Vnstock Telegram Bot). Nhiệm vụ của bạn là giải đáp thắc mắc về thị trường, cách đầu tư hoặc cung cấp thông tin chung cho người dùng bằng tiếng Việt, ngắn gọn, thân thiện và hữu ích. Nhớ xem lại lịch sử trò chuyện để hiểu bối cảnh và danh mục của người dùng nếu họ đề cập đến."
        
        model = genai.GenerativeModel(
            "gemini-2.0-flash",
            system_instruction=system_prompt
        )
        
        history_formatted = []
        if user_id:
            try:
                raw_history = db.get_chat_history(user_id, limit=10)
                for row in raw_history:
                    role = row['role']
                    # Gemini expects 'user' or 'model'
                    if role not in ['user', 'model']:
                        role = 'user'
                    history_formatted.append({
                        "role": role,
                        "parts": [row['content']]
                    })
            except Exception as db_e:
                logger.error(f"Lỗi đọc lịch sử chat: {db_e}")
                
        # Khởi tạo phiên chat với bộ nhớ
        chat = model.start_chat(history=history_formatted)
        response = chat.send_message(user_message)
        reply = response.text
        
        # Lưu vào lịch sử
        if user_id:
            try:
                db.save_chat_message(user_id, "user", user_message)
                db.save_chat_message(user_id, "model", reply)
            except Exception as db_save_e:
                logger.error(f"Lỗi lưu lịch sử chat: {db_save_e}")
                
        return reply
    except Exception as e:
        logger.error(f"Lỗi AI Chat: {e}")
        return "❌ Xin lỗi, tôi không thể trả lời lúc này do lỗi hệ thống AI."

def evaluate_portfolio(portfolio_str: str) -> str:
    """Đánh giá toàn bộ danh mục của người dùng."""
    if not config.GEMINI_API_KEY:
        return "❌ Tính năng AI chưa được cấu hình. (Thiếu GEMINI_API_KEY)"
        
    try:
        system_prompt = "Bạn là một Quản lý Quỹ đầu tư xuất sắc tại Việt Nam. Người dùng sẽ cung cấp trạng thái danh mục cổ phiếu hiện tại của họ (gồm Mã, Khối lượng, Giá vốn, Lãi/Lỗ). Hãy phân tích xem danh mục này có rủi ro gì không (quá tập trung một ngành, mã nào đang gãy trend, v.v.) và đưa ra 1-3 lời khuyên cơ cấu lại danh mục. Hãy trả lời ngắn gọn, súc tích."
        
        prompt = f"Đây là danh mục hiện tại của tôi:\n\n{portfolio_str}\n\nHãy tư vấn giúp tôi!"
        
        model = genai.GenerativeModel(
            "gemini-2.0-flash",
            system_instruction=system_prompt
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Lỗi AI Portfolio: {e}")
        return "❌ Có lỗi xảy ra khi AI phân tích danh mục."

def summarize_market_news() -> str:
    """Cào tin tức từ các mã trụ cột để tổng hợp Bản tin Sáng."""
    from modules.news_events import get_company_news
    if not config.GEMINI_API_KEY:
        return "❌ Tính năng AI chưa được cấu hình. (Thiếu GEMINI_API_KEY)"
        
    try:
        # Lấy tin tức từ 3 mã đại diện: Ngân hàng, Thép, Chứng khoán
        news_text = ""
        for sym in ["VCB", "HPG", "SSI"]:
            res = get_company_news(sym)
            if res.get("success"):
                news_text += f"\n--- TIN TỨC {sym} ---\n"
                for item in res.get("news", []):
                    news_text += f"- {item['title']} ({item['time']})\n"
                    
        if not news_text.strip():
            return "Không có tin tức mới để tổng hợp."
            
        system_prompt = "Bạn là Biên tập viên Tài chính kỳ cựu. Người dùng cung cấp tin tức từ các mã trụ cột của thị trường chứng khoán Việt Nam. Hãy đọc và viết một Bản Tin Sáng (khoảng 150-200 từ), bao gồm: Điểm nhấn thị trường, Xu hướng chung, và Lưu ý cho nhà đầu tư."
        
        model = genai.GenerativeModel(
            "gemini-2.0-flash",
            system_instruction=system_prompt
        )
        response = model.generate_content(f"Tin tức tổng hợp:\n{news_text}")
        return response.text
    except Exception as e:
        logger.error(f"Lỗi AI News: {e}")
        return "❌ Có lỗi xảy ra khi AI tổng hợp tin tức."
