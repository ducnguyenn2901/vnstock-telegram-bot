import os
import uuid
from datetime import datetime
from supabase import create_client, Client

def get_supabase_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("❌ Lỗi: Cần khai báo biến môi trường SUPABASE_URL và SUPABASE_KEY")
    return create_client(url, key)

def check_t0_exists(symbol, date_str):
    sb = get_supabase_client()
    res = sb.table("paper_trading_logs").select("signal_id").eq("symbol", symbol).eq("date", date_str).execute()
    return len(res.data) > 0

def get_pending_t1():
    sb = get_supabase_client()
    res = sb.table("paper_trading_logs").select("signal_id, symbol").eq("status", "T0_LOGGED").execute()
    return [(r['signal_id'], r['symbol']) for r in res.data]

def get_pending_t3():
    sb = get_supabase_client()
    res = sb.table("paper_trading_logs").select("signal_id, symbol, date").eq("status", "T1_ENTERED").execute()
    return [(r['signal_id'], r['symbol'], r['date']) for r in res.data]

def log_signal_t0(data: dict):
    sb = get_supabase_client()
    sig_id = str(uuid.uuid4())[:8] + "-" + data['symbol'] + "-" + data['date'].replace("-", "")
    now_ts = datetime.now().isoformat()
    
    insert_data = {
        "signal_id": sig_id,
        "experiment_id": data.get('experiment_id', 'EXP_V531_FORWARD_001'),
        "feature_version": data.get('feature_version', 'v1.0'),
        "date": data['date'],
        "symbol": data['symbol'],
        "model_version": data.get('model_version', 'v5.3.1'),
        "target_days": data.get('target_days', 3),
        "threshold": data.get('threshold', 0.01),
        "prob_threshold": data.get('prob_threshold', 0.40),
        "p_buy": data['p_buy'],
        "p_hold": data['p_hold'],
        "p_sell": data['p_sell'],
        "expected_return": data['expected_return'],
        "expected_edge": data['expected_edge'],
        "market_regime": data['market_regime'],
        "stock_regime": data['stock_regime'],
        "signal_quality": data['signal_quality'],
        "suggested_position": data['suggested_position'],
        "position_risk": data['position_risk'],
        "price_t": data.get('current_close', 0.0),
        "data_timestamp": data.get('data_timestamp', now_ts),
        "prediction_timestamp": now_ts,
        "status": "T0_LOGGED"
    }
    sb.table("paper_trading_logs").insert(insert_data).execute()
    return sig_id

def update_entry_t1(signal_id, entry_price_t1):
    sb = get_supabase_client()
    now_ts = datetime.now().isoformat()
    update_data = {
        "entry_price_t1": entry_price_t1,
        "execution_timestamp": now_ts,
        "status": "T1_ENTERED"
    }
    sb.table("paper_trading_logs").update(update_data).eq("signal_id", signal_id).execute()

def update_actual_t3(signal_id, actual_price_t3):
    sb = get_supabase_client()
    res = sb.table("paper_trading_logs").select("expected_return, entry_price_t1, price_t").eq("signal_id", signal_id).execute()
    if res.data:
        row = res.data[0]
        exp_ret = row.get("expected_return")
        entry_t1 = row.get("entry_price_t1")
        price_t = row.get("price_t")
        
        base_price = entry_t1 if entry_t1 else price_t 
        if base_price and base_price > 0:
            actual_return_t3 = ((actual_price_t3 - base_price) / base_price) * 100
            prediction_error = actual_return_t3 - exp_ret
            
            update_data = {
                "actual_price_t3": actual_price_t3,
                "actual_return_t3": actual_return_t3,
                "prediction_error": prediction_error,
                "status": "COMPLETED"
            }
            sb.table("paper_trading_logs").update(update_data).eq("signal_id", signal_id).execute()
