import sys
import os
import argparse
import logging
import sqlite3
import traceback
from datetime import datetime
import pandas as pd

# Giả định chạy trong môi trường cùng cấp với các modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.ml_predictor import train_and_predict
from modules.market_data import get_market_quote
from modules.paper_trading_logger import (
    log_signal_t0, update_entry_t1, update_actual_t3, 
    check_t0_exists, get_pending_t1, get_pending_t3
)
import vnstock

# Cấu hình Logging
if not os.path.exists('logs'):
    os.makedirs('logs')
logging.basicConfig(
    filename='logs/operational_runner.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

VN30_UNIVERSE = ["FPT", "MBB", "HPG", "MWG", "VCB", "SSI", "STB", "TCB", "PNJ", "VHM"]

def run_t0(dry_run=False):
    logging.info(f"🚀 BẮT ĐẦU CHU TRÌNH T0 (AI PREDICTION) - DRY RUN: {dry_run}")
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    success_count = 0
    for sym in VN30_UNIVERSE:
        try:
            if check_t0_exists(sym, today_str):
                logging.info(f"⏭️  [T0] {sym}: Đã có Signal cho ngày {today_str}. Bỏ qua (Idempotent).")
                continue
                
            logging.info(f"🔄 [T0] {sym}: Đang phân tích...")
            res = train_and_predict(sym, target_days=3, threshold=0.010, prob_threshold=0.40)
            
            if res.get("success"):
                data = {
                    'symbol': sym,
                    'date': today_str,
                    'model_version': 'v5.3.1',
                    'target_days': 3,
                    'threshold': 0.010,
                    'prob_threshold': 0.40,
                    'p_buy': res['prob_buy'],
                    'p_hold': res['prob_hold'],
                    'p_sell': res['prob_sell'],
                    'expected_return': res['expected_return'],
                    'expected_edge': res['expected_edge'],
                    'market_regime': res['market_context'],
                    'stock_regime': res.get('stock_regime', 'UNKNOWN'),
                    'signal_quality': res['signal_quality'],
                    'suggested_position': res.get('suggested_position', 0),
                    'position_risk': res.get('position_risk', 0),
                    'current_close': res.get('current_close', 0)
                }
                if not dry_run:
                    sig_id = log_signal_t0(data)
                    logging.info(f"✅ [T0] {sym}: Đã lưu tín hiệu {sig_id}")
                else:
                    logging.info(f"✅ [T0] {sym}: [DRY-RUN] Dự báo thành công P(BUY)={res['prob_buy']:.1f}%")
                success_count += 1
            else:
                logging.error(f"❌ [T0] {sym}: AI Lỗi - {res.get('error')}")
        
        except Exception as e:
            logging.error(f"❌ [T0] {sym}: Lỗi hệ thống bất ngờ - {e}")
            
    logging.info(f"🏁 KẾT THÚC T0: {success_count}/{len(VN30_UNIVERSE)} thành công.")

def run_t1(dry_run=False):
    logging.info(f"🚀 BẮT ĐẦU CHU TRÌNH T1 (OPEN PRICE EXECUTION) - DRY RUN: {dry_run}")
    pending_signals = get_pending_t1()
    
    if not pending_signals:
        logging.info("T1: Không có lệnh chờ.")
        return
        
    for sig_id, sym in pending_signals:
        try:
            quote_res = get_market_quote(sym)
            if quote_res.get("success"):
                open_p = quote_res["quote"].get("open_price", 0)
                if open_p > 0:
                    if not dry_run:
                        update_entry_t1(sig_id, open_p)
                        logging.info(f"✅ [T1] {sym}: Đã khớp lệnh ảo giá mở cửa {open_p} (Sig: {sig_id})")
                    else:
                        logging.info(f"✅ [T1] {sym}: [DRY-RUN] Sẽ khớp lệnh ảo giá mở cửa {open_p}")
                else:
                    logging.warning(f"⚠️ [T1] {sym}: Giá mở cửa chưa hợp lệ (Market chưa mở?). Bỏ qua.")
            else:
                logging.warning(f"⚠️ [T1] {sym}: Lỗi lấy quote - {quote_res.get('error')}")
        except Exception as e:
            logging.error(f"❌ [T1] {sym}: Lỗi hệ thống - {e}")

def run_t3(dry_run=False):
    logging.info(f"🚀 BẮT ĐẦU CHU TRÌNH T3 (ACTUAL RETURN AUDIT) - DRY RUN: {dry_run}")
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    entered_signals = get_pending_t3()
    
    mkt = vnstock.Market()
    for sig_id, sym, date_str in entered_signals:
        try:
            eq = mkt.equity(sym)
            df = eq.ohlcv(start=date_str, end=today_str)
            
            if df is not None and not df.empty and len(df) >= 4:
                quote_res = get_market_quote(sym)
                if quote_res.get("success"):
                    close_p = quote_res["quote"].get("close_price", 0)
                    if close_p > 0:
                        if not dry_run:
                            update_actual_t3(sig_id, close_p)
                            logging.info(f"✅ [T3] {sym}: Đã chốt vị thế T+3 giá {close_p}. Trạng thái COMPLETED. (Sig: {sig_id})")
                        else:
                            logging.info(f"✅ [T3] {sym}: [DRY-RUN] Tới hạn T3. Giá chốt ảo {close_p}.")
                    else:
                        logging.warning(f"⚠️ [T3] {sym}: Giá đóng cửa chưa hợp lệ.")
                else:
                    logging.warning(f"⚠️ [T3] {sym}: Lỗi lấy quote.")
            else:
                tdays = len(df) - 1 if df is not None else 0
                logging.info(f"⏳ [T3] {sym}: Chưa tới T3. Hiện tại mới là T+{tdays}.")
        except Exception as e:
            logging.error(f"❌ [T3] {sym}: Lỗi hệ thống - {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VNSTOCK QUANT Forward Paper Trading Runner")
    parser.add_argument("--task", type=str, choices=["t0", "t1", "t3"], required=True, help="Chu trình cần chạy (t0: Prediction, t1: Open Exec, t3: Close Audit)")
    parser.add_argument("--dry-run", action="store_true", help="Chạy thử nghiệm, không ghi vào DB")
    
    args = parser.parse_args()
    
    try:
        if args.task == "t0":
            run_t0(args.dry_run)
        elif args.task == "t1":
            run_t1(args.dry_run)
        elif args.task == "t3":
            run_t3(args.dry_run)
        sys.exit(0)
    except Exception as e:
        logging.critical(f"FATAL ERROR: {e}")
        sys.exit(1)
