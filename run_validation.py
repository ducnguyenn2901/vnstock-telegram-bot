import json
import numpy as np
from modules.ml_predictor import train_and_predict

# 10 mã đại diện để chạy test nhanh Validation Campaign
VN30_SAMPLE = ["FPT", "MBB", "HPG", "MWG", "VCB", "SSI", "STB", "TCB", "PNJ", "VHM"]

def run_campaign():
    print("="*60)
    print("🚀 VNSTOCK QUANT v5.3 - GLOBAL VALIDATION CAMPAIGN 🚀")
    print("="*60)
    
    all_trades = []
    all_preds = []
    
    for sym in VN30_SAMPLE:
        print(f"🔄 Đang train & backtest cho {sym}...")
        # Sử dụng threshold phù hợp với VN30 (1%) và prob_threshold = 0.40
        res = train_and_predict(sym, target_days=3, threshold=0.010, prob_threshold=0.40)
        
        if res.get("success"):
            trades = res.get("trades", [])
            preds = res.get("prediction_logs", [])
            
            for t in trades:
                t['symbol'] = sym
            for p in preds:
                p['symbol'] = sym
                
            all_trades.extend(trades)
            all_preds.extend(preds)
        else:
            print(f"❌ Lỗi ở mã {sym}: {res.get('error')}")

    print("\n" + "="*60)
    print("📊 1. GLOBAL QUALITY AUDIT (Strategy Execution)")
    print("="*60)
    print(f"{'Quality':<10} | {'N':<5} | {'Win Rate':<10} | {'Avg Win':<10} | {'Avg Loss':<10} | {'Expectancy':<12} | {'Profit Factor':<15}")
    print("-"*85)
    
    for q in ["HIGH", "MEDIUM", "LOW"]:
        q_trades = [t for t in all_trades if t['quality'] == q]
        if not q_trades:
            print(f"{q:<10} | {'0':<5} | {'-':<10} | {'-':<10} | {'-':<10} | {'-':<12} | {'-':<15}")
            continue
            
        wins = [t for t in q_trades if t['pnl_pct'] > 0]
        losses = [t for t in q_trades if t['pnl_pct'] <= 0]
        
        wr = len(wins) / len(q_trades)
        aw = np.mean([t['pnl_pct'] for t in wins]) if wins else 0.0
        al = np.mean([t['pnl_pct'] for t in losses]) if losses else 0.0
        exp = (wr * aw) + ((1 - wr) * al)
        
        gp = sum([t['cash_pnl'] for t in wins])
        gl = abs(sum([t['cash_pnl'] for t in losses]))
        pf = (gp / gl) if gl != 0 else float('inf')
        
        print(f"{q:<10} | {len(q_trades):<5} | {wr*100:>8.1f}% | {aw:>9.2f}% | {al:>9.2f}% | {exp:>11.2f}% | {pf:>13.2f}")

    print("\n" + "="*60)
    print("🎯 2. RANKING & CALIBRATION AUDIT (Quantile Q1-Q5)")
    print("="*60)
    print(f"{'Quantile (P_BUY)':<20} | {'N':<6} | {'Avg P(BUY)':<12} | {'Avg Actual T+3':<16} | {'Avg Expected':<14} | {'Mean Bias'}")
    print("-"*90)
    
    p_buys = [p['p_buy'] for p in all_preds]
    if len(p_buys) >= 5:
        q_vals = np.percentile(p_buys, [20, 40, 60, 80])
        bins = [
            (0, q_vals[0], "Q1 (Bottom 20%)"),
            (q_vals[0], q_vals[1], "Q2 (20-40%)"),
            (q_vals[1], q_vals[2], "Q3 (40-60%)"),
            (q_vals[2], q_vals[3], "Q4 (60-80%)"),
            (q_vals[3], 101, "Q5 (Top 20%)")
        ]
        
        for (lo, hi, label) in bins:
            b_preds = [p for p in all_preds if lo <= p['p_buy'] < hi]
            if not b_preds:
                continue
                
            avg_pbuy = np.mean([p['p_buy'] for p in b_preds])
            avg_actual = np.mean([p['actual_t3'] for p in b_preds])
            avg_expected = np.mean([p['expected_return'] for p in b_preds])
            mean_bias = np.mean([p['error'] for p in b_preds])
            
            print(f"{label:<20} | {len(b_preds):<6} | {avg_pbuy:>11.2f}% | {avg_actual:>15.2f}% | {avg_expected:>13.2f}% | {mean_bias:>10.2f}%")
    else:
        print("Không đủ dữ liệu để chia Quantile.")
        
    print("\n" + "="*60)
    print("🔍 3. RED TEAM AUDIT: SYMBOL BREAKDOWN (Q5 vs Q1)")
    print("="*60)
    print(f"{'Symbol':<10} | {'Q1 Actual':<12} | {'Q5 Actual':<12} | {'Spread (Q5-Q1)':<16} | {'Net Q5 (Cost 0.5%)'}")
    print("-"*85)
    
    for sym in VN30_SAMPLE:
        sym_preds = [p for p in all_preds if p['symbol'] == sym]
        if len(sym_preds) < 5: 
            continue
            
        sym_pbuys = [p['p_buy'] for p in sym_preds]
        q20 = np.percentile(sym_pbuys, 20)
        q80 = np.percentile(sym_pbuys, 80)
        
        q1_preds = [p['actual_t3'] for p in sym_preds if p['p_buy'] <= q20]
        q5_preds = [p['actual_t3'] for p in sym_preds if p['p_buy'] >= q80]
        
        q1_avg = np.mean(q1_preds) if q1_preds else 0
        q5_avg = np.mean(q5_preds) if q5_preds else 0
        spread = q5_avg - q1_avg
        net_q5 = q5_avg - 0.50 # Trừ round-trip cost giả định
        
        print(f"{sym:<10} | {q1_avg:>11.2f}% | {q5_avg:>11.2f}% | {spread:>15.2f}% | {net_q5:>16.2f}%")
        
    print("\n✅ VNSTOCK QUANT v5.3.1 Validation Baseline Frozen & Forward DB Ready.")

if __name__ == "__main__":
    run_campaign()
