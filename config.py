# -*- coding: utf-8 -*-
"""
Cấu hình hệ thống và các hàm tiện ích định dạng dữ liệu cho Telegram Bot Vnstock.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Đảm bảo UTF-8 encoding trên hệ thống Windows
if sys.platform.startswith("win"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Xác định thư mục gốc của dự án và nạp vào sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Tải biến môi trường từ file .env nằm cùng thư mục dự án
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=env_path)

# Cấu hình logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("VnstockBot")

VNSTOCK_API_KEY = os.getenv("VNSTOCK_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Khởi tạo API Key cho vnstock nếu có
if VNSTOCK_API_KEY and VNSTOCK_API_KEY != "YOUR_TELEGRAM_BOT_TOKEN_HERE":
    try:
        from vnstock.core import setup_api_key
        setup_api_key(VNSTOCK_API_KEY)
        logger.info("Đã nạp Vnstock API Key thành công.")
    except Exception as e:
        logger.warning(f"Không thể khởi tạo Vnstock API Key tự động: {e}")

def format_number(val, decimals=2, default="N/A"):
    """Định dạng số thực với dấu phẩy ngăn cách hàng nghìn."""
    try:
        if val is None or val == "" or str(val).lower() == "nan":
            return default
        num = float(val)
        if decimals == 0:
            return f"{num:,.0f}"
        return f"{num:,.{decimals}f}"
    except (ValueError, TypeError):
        return default

def format_currency_vn(val, default="N/A"):
    """Định dạng số tiền VNĐ thành tỷ hoặc triệu đồng ngắn gọn."""
    try:
        if val is None or val == "" or str(val).lower() == "nan":
            return default
        num = float(val)
        abs_num = abs(num)
        if abs_num >= 1_000_000_000_000:
            return f"{num / 1_000_000_000_000:,.2f} nghìn tỷ"
        elif abs_num >= 1_000_000_000:
            return f"{num / 1_000_000_000:,.2f} tỷ"
        elif abs_num >= 1_000_000:
            return f"{num / 1_000_000:,.2f} tr"
        else:
            return f"{num:,.0f} đ"
    except (ValueError, TypeError):
        return default

def format_percent(val, default="N/A"):
    """Định dạng phần trăm kèm dấu + / -."""
    try:
        if val is None or val == "" or str(val).lower() == "nan":
            return default
        num = float(val)
        sign = "+" if num > 0 else ""
        return f"{sign}{num:.2f}%"
    except (ValueError, TypeError):
        return default
