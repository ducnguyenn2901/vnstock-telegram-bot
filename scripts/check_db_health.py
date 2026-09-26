import sqlite3
import pandas as pd
import os

DB_PATH = 'data/vnstock_quant.db'

def run_health_check():
    if not os.path.exists(DB_PATH):
        print(f"❌ Không tìm thấy database tại {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query("SELECT * FROM paper_trading_logs", conn)
    except Exception as e:
        print(f"❌ Lỗi đọc database: {e}")
        return
    finally:
        conn.close()

    if df.empty:
        print("⚠️ Database tồn tại nhưng chưa có bất kỳ dữ liệu nào. Task Scheduler có thể chưa chạy.")
        return

    print("="*70)
    print("🩺 BÁO CÁO SỨC KHỎE DỮ LIỆU PAPER TRADING (11 NGÀY QUA)")
    print("="*70)

    # 1. Tổng quan
    print(f"Tổng số bản ghi T0 (Dự đoán): {len(df)} lệnh")
    print(f"Số ngày giao dịch đã ghi nhận: {df['date'].nunique()} ngày")
    dates = sorted(df['date'].unique())
    print(f"Các ngày ghi nhận: {', '.join(dates)}\n")

    # 2. Phân bố trạng thái
    print("📊 Phân bố trạng thái lệnh (Lifecycle Status):")
    status_counts = df['status'].value_counts()
    for status, count in status_counts.items():
        print(f"  - {status:<12}: {count:>4} lệnh")
    print()

    # 3. Kiểm tra tính toàn vẹn (Integrity)
    print("🔍 Kiểm tra Tính toàn vẹn Dữ liệu (Data Integrity):")
    completed = df[df['status'] == 'COMPLETED']
    if not completed.empty:
        missing_t1 = completed['entry_price_t1'].isnull().sum()
        missing_t3 = completed['actual_price_t3'].isnull().sum()
        missing_ret = completed['actual_return_t3'].isnull().sum()
        
        print(f"  - Số lệnh COMPLETED: {len(completed)}")
        print(f"  - Lỗi thiếu giá T1 (entry_price_t1): {missing_t1}")
        print(f"  - Lỗi thiếu giá T3 (actual_price_t3): {missing_t3}")
        print(f"  - Lỗi thiếu Return thực tế: {missing_ret}")
        
        print("\n  - Sample 3 lệnh gần nhất đã hoàn tất vòng đời (COMPLETED):")
        sample = completed.sort_values('date', ascending=False).head(3)
        for _, row in sample.iterrows():
            print(f"    + {row['date']} | {row['symbol']:<4} | P(BUY): {row['p_buy']:.1f}% | Exp Ret: {row['expected_return']:+.2f}% | Act Ret: {row['actual_return_t3']:+.2f}% | Error: {row['prediction_error']:+.2f}%")
    else:
        print("  - Chưa có lệnh nào đạt trạng thái COMPLETED.")
        print("    (Chưa tới hạn T+3, hoặc Task T3 chạy bị lỗi/chưa được gọi).")

    # 4. Kiểm tra kẹt lệnh
    print("\n⚠️ Cảnh báo Operational (Nếu có):")
    latest_date = df['date'].max()
    t0_stuck = df[(df['status'] == 'T0_LOGGED') & (df['date'] < latest_date)]
    if not t0_stuck.empty:
        print(f"  - KẸT T1: Có {len(t0_stuck)} lệnh sinh ra từ {t0_stuck['date'].min()} nhưng chưa được khớp giá T1 (Task 09:15 có thể bị miss).")
    else:
        print("  - KẸT T1: OK (Tất cả lệnh cũ đều đã qua bước T1_ENTERED).")

    print("\n✅ Hoàn tất kiểm tra Sức khỏe Dữ liệu.")

if __name__ == "__main__":
    run_health_check()
