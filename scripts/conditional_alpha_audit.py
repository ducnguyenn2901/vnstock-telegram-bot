import sys
import os
import numpy as np
import pandas as pd
from modules.ml_predictor import train_and_predict

VN30_UNIVERSE = ["FPT", "MBB", "HPG", "MWG", "VCB", "SSI", "STB", "TCB", "PNJ", "VHM"]

def run_conditional_audit():
    print("="*80)
    print("🔬 PHASE 6A: CONDITIONAL ALPHA AUDIT (v5.3.1-calibration-hygiene-fixed)")
    print("="*80)
    
    all_preds = []
    for sym in VN30_UNIVERSE:
        print(f"🔄 Đang thu thập dữ liệu OOS cho {sym}...")
        res = train_and_predict(sym, target_days=3, threshold=0.010, prob_threshold=0.40)
        if res.get("success"):
            preds = res.get("prediction_logs", [])
            for p in preds:
                p['symbol'] = sym
                p['stock_regime'] = res.get('stock_regime', 'N/A')
            all_preds.extend(preds)
            
    df = pd.DataFrame(all_preds)
    if df.empty:
        print("Không có dữ liệu OOS.")
        return

    df['date'] = pd.to_datetime(df['date'])
    df['year'] = df['date'].dt.year

    print("\n" + "="*80)
    print("📊 1. BREADTH & MEDIAN SPREAD AUDIT (Global)")
    print("="*80)
    
    symbol_spreads = []
    for sym in VN30_UNIVERSE:
        sym_df = df[df['symbol'] == sym]
        if len(sym_df) < 5: continue
        q20 = sym_df['p_buy'].quantile(0.20)
        q80 = sym_df['p_buy'].quantile(0.80)
        
        q1_avg = sym_df[sym_df['p_buy'] <= q20]['actual_t3'].mean()
        q5_avg = sym_df[sym_df['p_buy'] >= q80]['actual_t3'].mean()
        
        if pd.notna(q1_avg) and pd.notna(q5_avg):
            symbol_spreads.append(q5_avg - q1_avg)
        
    breadth = sum(1 for s in symbol_spreads if s > 0) / len(symbol_spreads) if symbol_spreads else 0
    median_spread = np.median(symbol_spreads) if symbol_spreads else 0
    mean_spread = np.mean(symbol_spreads) if symbol_spreads else 0
    
    print(f"Q5 Breadth (Winning Symbols): {breadth*100:.1f}%")
    print(f"Median Spread (Q5-Q1):        {median_spread:+.2f}%")
    print(f"Mean Spread   (Q5-Q1):        {mean_spread:+.2f}%")
    
    def print_audit_table(group_col, title):
        print("\n" + "="*80)
        print(f"🎯 {title}")
        print("="*80)
        print(f"{group_col:<15} | {'N':<6} | {'Q1 Actual':<12} | {'Q5 Actual':<12} | {'Spread (Q5-Q1)':<16} | {'Net Q5 (Cost 0.5%)'}")
        print("-" * 90)
        
        for name, group in df.groupby(group_col):
            if len(group) < 10: continue
            
            q20 = group['p_buy'].quantile(0.20)
            q80 = group['p_buy'].quantile(0.80)
            
            q1_avg = group[group['p_buy'] <= q20]['actual_t3'].mean()
            q5_avg = group[group['p_buy'] >= q80]['actual_t3'].mean()
            
            if pd.isna(q1_avg) or pd.isna(q5_avg): continue
            
            spread = q5_avg - q1_avg
            net_q5 = q5_avg - 0.50
            
            print(f"{str(name):<15} | {len(group):<6} | {q1_avg:>11.2f}% | {q5_avg:>11.2f}% | {spread:>15.2f}% | {net_q5:>16.2f}%")

    print_audit_table('market_regime', "2. MARKET REGIME AUDIT")
    print_audit_table('stock_regime', "3. STOCK REGIME AUDIT")
    print_audit_table('year', "4. TEMPORAL (YEAR) AUDIT")

if __name__ == "__main__":
    run_conditional_audit()
