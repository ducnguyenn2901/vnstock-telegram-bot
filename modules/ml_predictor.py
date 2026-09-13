import logging
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import database as db

logger = logging.getLogger("MLPredictor")

def train_and_predict(symbol: str, target_days=3) -> dict:
    """
    Huấn luyện mô hình Random Forest trên dữ liệu EOD của một mã, 
    sau đó dự báo xác suất TĂNG giá trong `target_days` ngày tới.
    """
    symbol = symbol.upper()
    try:
        # Lấy dữ liệu từ DB (Kho dữ liệu nội bộ)
        df = db.get_all_price_history(symbols=[symbol])
        
        if df.empty or len(df) < 50:
            return {"success": False, "error": f"Không đủ dữ liệu lịch sử cho mã {symbol} (Cần gõ /sync)"}
            
        # Sắp xếp đúng theo thời gian
        df = df.sort_values('date').reset_index(drop=True)
        
        # --- TẠO FEATURES (Đặc trưng) ---
        # 1. Biến động giá
        df['ret_1d'] = df['close'].pct_change(1)
        df['ret_3d'] = df['close'].pct_change(3)
        df['ret_5d'] = df['close'].pct_change(5)
        
        # 2. Trung bình động (MA)
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma20'] = df['close'].rolling(20).mean()
        df['dist_ma20'] = (df['close'] - df['ma20']) / df['ma20']
        
        # 3. RSI cơ bản (Window 14)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 4. Đột biến khối lượng
        df['vol_ma20'] = df['volume'].rolling(20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_ma20']
        
        # --- TẠO TARGET (Nhãn) ---
        # Label = 1 nếu giá đóng cửa của 3 ngày sau cao hơn giá đóng cửa hôm nay (Tăng)
        # Shift(-3) mang giá trị của 3 ngày trong tương lai về dòng hiện tại
        df['future_close'] = df['close'].shift(-target_days)
        df['target'] = (df['future_close'] > df['close']).astype(int)
        
        # Xóa các dòng bị NaN do pct_change, rolling, hoặc shift
        # Dòng cuối cùng (hiện tại) sẽ bị rớt nếu dropna toàn bộ (vì future_close là NaN).
        # Nên ta phải tách dòng hiện tại ra trước!
        current_data = df.iloc[-1:].copy()
        
        # Dữ liệu huấn luyện là những dòng có đủ target
        train_data = df.dropna().copy()
        
        if len(train_data) < 30:
            return {"success": False, "error": "Dữ liệu huấn luyện quá ít sau khi tính toán các chỉ báo."}
            
        # Các cột Feature
        features = ['ret_1d', 'ret_3d', 'ret_5d', 'dist_ma20', 'rsi', 'vol_ratio']
        
        X_train = train_data[features]
        y_train = train_data['target']
        
        # Huấn luyện mô hình Random Forest
        model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        model.fit(X_train, y_train)
        
        # Dự báo cho dòng hiện tại (Hôm nay)
        X_current = current_data[features].fillna(0) # Đề phòng NaN
        
        pred_prob = model.predict_proba(X_current)[0] # Trả về [Prob(0), Prob(1)]
        prob_up = pred_prob[1] * 100
        
        # Trích xuất một số chỉ báo hiện tại để báo cáo
        current_price = current_data['close'].values[0]
        current_rsi = current_data['rsi'].values[0]
        
        # Đánh giá tầm quan trọng của các Feature (Optional)
        feature_importances = model.feature_importances_
        top_feature = features[np.argmax(feature_importances)]
        
        return {
            "success": True,
            "symbol": symbol,
            "prob_up": prob_up,
            "current_price": current_price,
            "current_rsi": current_rsi,
            "top_feature": top_feature,
            "train_samples": len(train_data)
        }
        
    except Exception as e:
        logger.error(f"Lỗi khi chạy ML cho {symbol}: {e}")
        return {"success": False, "error": str(e)}

def format_prediction_message(result: dict) -> str:
    """Chuyển đổi kết quả ML thành tin nhắn dễ hiểu."""
    if not result.get("success"):
        return f"❌ Lỗi: {result.get('error')}"
        
    symbol = result["symbol"]
    prob_up = result["prob_up"]
    rsi = result["current_rsi"]
    samples = result["train_samples"]
    
    # Phân loại nhận định
    if prob_up >= 70:
        signal = "🟢 <b>RẤT TÍCH CỰC (STRONG BUY)</b>"
        trend = "Khả năng cao sẽ bứt phá mạnh."
    elif prob_up >= 55:
        signal = "🟢 <b>TÍCH CỰC (BUY)</b>"
        trend = "Xu hướng nghiêng về phe mua."
    elif prob_up >= 45:
        signal = "🟡 <b>ĐI NGANG (NEUTRAL)</b>"
        trend = "Chưa rõ xu hướng, rủi ro 50/50."
    elif prob_up >= 30:
        signal = "🔴 <b>TIÊU CỰC (SELL)</b>"
        trend = "Áp lực bán đang mạnh lên."
    else:
        signal = "🔴 <b>RẤT TIÊU CỰC (STRONG SELL)</b>"
        trend = "Rủi ro giảm giá sâu là rất cao."
        
    msg = f"🧠 <b>AI QUANT PREDICTION: {symbol}</b>\n"
    msg += f"<i>(Dự phóng xu hướng T+3 bằng Machine Learning)</i>\n"
    msg += "➖➖➖➖➖➖➖➖➖➖➖➖\n"
    msg += f"🎯 Tín hiệu: {signal}\n"
    msg += f"📈 <b>Xác suất TĂNG GIÁ: {prob_up:.1f}%</b>\n"
    msg += f"📉 <b>Xác suất GIẢM GIÁ: {100 - prob_up:.1f}%</b>\n"
    msg += f"💡 Nhận định: {trend}\n\n"
    msg += f"📊 <b>Chỉ báo kỹ thuật hiện tại:</b>\n"
    msg += f"▫️ RSI (14): {rsi:.1f} {'(Quá mua)' if rsi > 70 else '(Quá bán)' if rsi < 30 else '(Bình thường)'}\n"
    msg += f"▫️ Yếu tố ảnh hưởng lớn nhất: <code>{result['top_feature']}</code>\n"
    msg += f"<i>(Mô hình Random Forest được huấn luyện trên {samples} dữ liệu lịch sử)</i>\n"
    msg += "\n⚠️ <i>Lưu ý: Dự báo bằng ML chỉ mang tính xác suất thống kê dựa trên dữ liệu quá khứ. Không phải lời khuyên đầu tư chắc chắn 100%.</i>"
    
    return msg
