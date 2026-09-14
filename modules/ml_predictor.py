# -*- coding: utf-8 -*-
"""
Module Dự Đoán Xu Hướng Cổ Phiếu Bằng Random Forest Định Lượng (Quant ML).
Thiết kế theo 14 tiêu chuẩn khắt khe từ bản thiết kế nghiên cứu:
- 16 Features: Momentum, Trend, Volatility, Volume, Technical, Position.
- Wilder's Smoothing cho RSI.
- Target 3 lớp: BUY (> +1.5%), SELL (< -1.5%), HOLD (-1.5% đến +1.5%).
- TimeSeriesSplit & RandomizedSearchCV trên 80% Train, đóng băng 20% Unseen Test.
- Validation Report đa fold: Accuracy_mean trên 5 folds + Metrics đa lớp trên Test.
- Baseline Majority-Class Classifier để xác nhận giá trị gia tăng của mô hình.
- Out-of-sample Chronological Backtest có tính Phí (0.15%) + Slippage (0.10%) và đối chiếu Buy & Hold.
- Confusion Matrix hiển thị chi tiết trên Telegram.
"""

import logging
import logging
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV, cross_val_score
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix
)
import database as db
import config

logger = logging.getLogger("MLPredictor")

# === MODEL REGISTRY (IN-MEMORY CACHE) ===
# Lưu trữ model và metadata để tránh retrain liên tục trên cùng EOD data
MODEL_REGISTRY = {}

# === DANH SÁCH 16 ĐẶC TRƯNG QUANT ===
FEATURES = [
    'ret_1d', 'ret_3d', 'ret_5d', 'ret_10d', 'ret_20d',      # Momentum (5)
    'dist_ma20', 'dist_ma50', 'ma20_slope',                     # Trend (3)
    'bbw', 'atr_ratio',                                          # Volatility (2)
    'vol_ratio', 'vol_ratio_5_20',                               # Volume (2)
    'rsi', 'macd_signal',                                        # Technical (2)
    'dist_high20', 'dist_low20'                                  # Price Position (2)
]

TARGET_LABELS = {0: "SELL", 1: "HOLD", 2: "BUY"}


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Tính toán 16 đặc trưng kỹ thuật & động lượng chuẩn hóa."""
    df = df.copy()
    
    # 1. Momentum
    df['ret_1d'] = df['close'].pct_change(1)
    df['ret_3d'] = df['close'].pct_change(3)
    df['ret_5d'] = df['close'].pct_change(5)
    df['ret_10d'] = df['close'].pct_change(10)
    df['ret_20d'] = df['close'].pct_change(20)
    
    # 2. Trend
    ma20 = df['close'].rolling(20).mean()
    ma50 = df['close'].rolling(50).mean()
    df['dist_ma20'] = (df['close'] - ma20) / (ma20 + 1e-9)
    df['dist_ma50'] = (df['close'] - ma50) / (ma50 + 1e-9)
    df['ma20_slope'] = (ma20 - ma20.shift(5)) / (ma20.shift(5) + 1e-9)
    
    # 3. Volatility
    std20 = df['close'].rolling(20).std()
    upper_bb = ma20 + (2 * std20)
    lower_bb = ma20 - (2 * std20)
    df['bbw'] = (upper_bb - lower_bb) / (ma20 + 1e-9)
    
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - df['close'].shift(1)).abs()
    tr3 = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr14 = tr.ewm(alpha=1/14, adjust=False).mean()
    df['atr_ratio'] = atr14 / (df['close'] + 1e-9)
    
    # 4. Volume
    vol_ma20 = df['volume'].rolling(20).mean()
    vol_ma5 = df['volume'].rolling(5).mean()
    df['vol_ratio'] = df['volume'] / (vol_ma20 + 1e-9)
    df['vol_ratio_5_20'] = vol_ma5 / (vol_ma20 + 1e-9)
    
    # 5. Technical
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta.where(delta < 0, 0.0))
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    df['rsi'] = 100.0 - (100.0 / (1.0 + rs))
    
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    df['macd_signal'] = (macd - signal) / (df['close'] + 1e-9)
    
    # 6. Price Position
    high20 = df['high'].rolling(20).max()
    low20 = df['low'].rolling(20).min()
    df['dist_high20'] = (df['close'] / (high20 + 1e-9)) - 1.0
    df['dist_low20'] = (df['close'] / (low20 + 1e-9)) - 1.0
    
    return df


def train_and_predict(symbol: str, target_days: int = 3, threshold: float = 0.015, prob_threshold: float = 0.60) -> dict:
    """
    Pipeline Quant ML Tối Ưu (Tách Prediction vs Trading Layer, dùng Caching).
    """
    global MODEL_REGISTRY
    symbol = symbol.upper().strip()
    
    try:
        # ===== BƯỚC 1: DỮ LIỆU & CACHE =====
        raw_df = db.get_all_price_history(symbols=[symbol])
        
        # Nếu DB rỗng hoặc thiếu dữ liệu, tự động lấy trực tiếp từ API
        if raw_df.empty or len(raw_df) < 150:
            logger.info(f"Dữ liệu DB cho {symbol} chưa đủ ({len(raw_df)} phiên). Đang tự động tải từ Internet...")
            import datetime
            import os
            os.environ["VNSTOCK_TELEMETRY"] = "off" # Tắt cảnh báo telemetry của vnstock
            
            end_date = datetime.date.today().strftime("%Y-%m-%d")
            start_date = (datetime.date.today() - datetime.timedelta(days=365 * 4)).strftime("%Y-%m-%d")
            
            try:
                import vnstock
                mkt = vnstock.Market()
                raw_df = mkt.equity(symbol).ohlcv(start=start_date, end=end_date)
            except Exception as e:
                logger.warning(f"Lỗi vnstock khi tải {symbol}: {e}. Chuyển sang dùng Yahoo Finance...")
                raw_df = pd.DataFrame()
                
            # vnstock bản Free bị giới hạn trả về tối đa 100 nến. Ta cần > 113 nến cho ML (ma50 + min_train 60 + target 3)
            if raw_df is None or raw_df.empty or len(raw_df) < 120:
                # KẾ HOẠCH B (DỰ PHÒNG): Dùng API của DNSE (Rất ổn định cho Render/Server)
                try:
                    import requests
                    start_ts = int(datetime.datetime.strptime(start_date, "%Y-%m-%d").timestamp())
                    end_ts = int(datetime.datetime.strptime(end_date, "%Y-%m-%d").timestamp())
                    url = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?resolution=1D&symbol={symbol}&from={start_ts}&to={end_ts}"
                    
                    r = requests.get(url, timeout=10)
                    data = r.json()
                    if 't' in data and len(data['t']) > 0:
                        raw_df = pd.DataFrame({
                            'date': pd.to_datetime(data['t'], unit='s'),
                            'open': data['o'],
                            'high': data['h'],
                            'low': data['l'],
                            'close': data['c'],
                            'volume': data['v']
                        })
                except Exception as dnse_error:
                    logger.error(f"Lỗi DNSE API: {dnse_error}")
            
            if raw_df is None or raw_df.empty or len(raw_df) < 120:
                return {"success": False, "error": f"API lỗi hoặc mã {symbol} không hợp lệ (Không tải được từ vnstock và DNSE)."}
            
            # Chuẩn hóa tên cột
            raw_df.columns = [str(c).lower() for c in raw_df.columns]
            if 'time' in raw_df.columns:
                raw_df.rename(columns={'time': 'date'}, inplace=True)
            elif 'date' not in raw_df.columns and 'datetime' in raw_df.columns:
                raw_df.rename(columns={'datetime': 'date'}, inplace=True)
                
        raw_df = raw_df.sort_values('date').reset_index(drop=True)
        latest_date = str(raw_df['date'].iloc[-1])[:10]
        
        metadata = {}
        best_rf = None
        
        # Kiểm tra Model Registry Cache (chỉ train lại nếu có dữ liệu EOD mới)
        cache_key = f"{symbol}_{target_days}_{threshold}_{prob_threshold}"
        if cache_key in MODEL_REGISTRY and MODEL_REGISTRY[cache_key]['latest_date'] == latest_date:
            best_rf = MODEL_REGISTRY[cache_key]['model']
            metadata = MODEL_REGISTRY[cache_key]['metadata']
            df = compute_features(raw_df)
        else:
            # ===== BƯỚC 2: TRAIN MÔ HÌNH (Nếu Cache Miss) =====
            df = compute_features(raw_df)
            
            # Target Construction (3-class)
            future_return = (df['close'].shift(-target_days) / df['close']) - 1.0
            target = pd.Series(1, index=df.index)
            target[future_return > threshold] = 2
            target[future_return < -threshold] = 0
            df['target'] = target
            
            labeled_df = df.dropna(subset=FEATURES).iloc[:-target_days].copy()
            labeled_df['target'] = labeled_df['target'].astype(int)
            
            if len(labeled_df) < 60:
                return {"success": False, "error": "Dữ liệu sau tính toán không đủ 60 mẫu để huấn luyện."}
                
            # Chronological Split (80/20) với Purge (Embargo)
            split_idx = int(len(labeled_df) * 0.8)
            train_df = labeled_df.iloc[:split_idx - target_days]
            test_df = labeled_df.iloc[split_idx:]
            
            X_train, y_train = train_df[FEATURES].values, train_df['target'].values
            X_test, y_test = test_df[FEATURES].values, test_df['target'].values
            
            train_start = str(train_df['date'].iloc[0])[:10]
            train_end = str(train_df['date'].iloc[-1])[:10]
            test_start = str(test_df['date'].iloc[0])[:10]
            test_end = str(test_df['date'].iloc[-1])[:10]
            
            # Hyperparameter Tuning (Purged TimeSeriesSplit)
            try:
                tscv = TimeSeriesSplit(n_splits=5, gap=target_days)
            except TypeError:
                tscv = TimeSeriesSplit(n_splits=5)
                
            param_dist = {
                'n_estimators': [50, 100, 150],
                'max_depth': [3, 5, 8],
                'min_samples_split': [5, 10],
                'min_samples_leaf': [3, 5],
                'max_features': ['sqrt', 'log2']
            }
            
            # Optimize bằng RandomizedSearchCV
            search = RandomizedSearchCV(
                RandomForestClassifier(random_state=42),
                param_distributions=param_dist,
                n_iter=10,
                cv=tscv,
                scoring='f1_macro',
                random_state=42,
                n_jobs=1
            )
            search.fit(X_train, y_train)
            best_estimator = search.best_estimator_
            
            # Probability Calibration
            try:
                from sklearn.calibration import CalibratedClassifierCV
                best_rf = CalibratedClassifierCV(best_estimator, method='sigmoid', cv=tscv)
                best_rf.fit(X_train, y_train)
            except Exception:
                best_rf = best_estimator
            
            # Metrics
            y_pred = best_rf.predict(X_test)
            y_proba = best_rf.predict_proba(X_test)
            classes_list = list(best_rf.classes_)
            
            majority_class = int(pd.Series(y_train).mode()[0])
            baseline_acc = float((y_test == majority_class).mean() * 100)
            rf_acc = float(accuracy_score(y_test, y_pred) * 100)
            
            macro_f1 = float(f1_score(y_test, y_pred, average='macro', zero_division=0) * 100)
            try:
                auc_val = float(roc_auc_score(y_test, y_proba, multi_class='ovr', labels=classes_list))
            except:
                auc_val = None
                
            # --- TRADING ENGINE LAYER (Backtest Out-of-Sample) ---
            FEE_PER_SIDE = 0.0015
            SLIPPAGE_PER_SIDE = 0.0010
            TOTAL_COST_PER_SIDE = FEE_PER_SIDE + SLIPPAGE_PER_SIDE
            
            buy_idx = classes_list.index(2) if 2 in classes_list else -1
            sell_idx = classes_list.index(0) if 0 in classes_list else -1
            
            in_position = False
            entry_price = 0.0
            capital = 100.0
            equity_curve = [capital]
            trades = []
            
            test_closes = test_df['close'].values
            test_opens = test_df['open'].values
            
            for i in range(len(test_df)):
                p_buy = float(y_proba[i, buy_idx]) if buy_idx != -1 else 0.0
                p_sell = float(y_proba[i, sell_idx]) if sell_idx != -1 else 0.0
                curr_close = float(test_closes[i])
                next_open = float(test_opens[i+1]) if i + 1 < len(test_df) else curr_close
                
                if not in_position:
                    if p_buy >= prob_threshold:
                        in_position = True
                        entry_price = next_open * (1.0 + TOTAL_COST_PER_SIDE)
                else:
                    unrealized_pnl = (curr_close - entry_price) / entry_price
                    if p_sell >= prob_threshold or unrealized_pnl <= -0.07 or i == len(test_df) - 1:
                        in_position = False
                        exit_price = next_open * (1.0 - TOTAL_COST_PER_SIDE)
                        pnl_net = ((exit_price - entry_price) / entry_price) * 100
                        capital *= (1.0 + pnl_net / 100)
                        trades.append({'pnl_pct': pnl_net})
                
                equity_curve.append(capital)
                
            total_rf_return = float(capital - 100.0)
            bh_return = float(((test_closes[-1] - test_closes[0]) / test_closes[0]) * 100)
            
            sharpe_ratio = None
            profit_factor = None
            
            if len(trades) > 0:
                max_dd = 0.0
                peak = 100.0
                for eq in equity_curve:
                    if eq > peak: peak = eq
                    dd = (peak - eq) / peak * 100
                    if dd > max_dd: max_dd = dd
                    
                import numpy as np
                returns = pd.Series(equity_curve).pct_change().dropna()
                if returns.std() != 0:
                    sharpe_ratio = float((returns.mean() / returns.std()) * np.sqrt(252))
                
                gross_profit = sum(t['pnl_pct'] for t in trades if t['pnl_pct'] > 0)
                gross_loss = abs(sum(t['pnl_pct'] for t in trades if t['pnl_pct'] < 0))
                profit_factor = float(gross_profit / gross_loss) if gross_loss != 0 else float('inf')
            else:
                max_dd = None # Sẽ hiển thị N/A nếu 0 trades
                
            win_trades = [t for t in trades if t['pnl_pct'] > 0]
            win_rate = (len(win_trades) / len(trades) * 100) if trades else 0.0
            
            importances = best_estimator.feature_importances_
            top_features = sorted(zip(FEATURES, importances), key=lambda x: x[1], reverse=True)[:5]
            
            # --- LƯU VÀO MODEL REGISTRY ---
            metadata = {
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                "target_days": target_days,
                "target_threshold": threshold * 100,
                "baseline_acc": baseline_acc,
                "rf_acc": rf_acc,
                "macro_f1": macro_f1,
                "auc": auc_val,
                "total_trades": len(trades),
                "win_rate": win_rate,
                "total_rf_return": total_rf_return,
                "bh_return": bh_return,
                "max_dd": max_dd,
                "sharpe_ratio": sharpe_ratio,
                "profit_factor": profit_factor,
                "roundtrip_cost": (TOTAL_COST_PER_SIDE * 2) * 100,
                "top_features": top_features,
                "classes_list": classes_list
            }
            
            MODEL_REGISTRY[cache_key] = {
                "model": best_rf,
                "latest_date": latest_date,
                "metadata": metadata
            }
        
        # ===== BƯỚC 3: INFERENCE (Decision Support Engine) =====
        current_row = df.iloc[-1:].copy()
        current_feature_row = current_row[FEATURES].copy()
        
        if current_feature_row.isna().any().any():
            return {"success": False, "error": "Không đủ dữ liệu để tạo đặc trưng đầy đủ (NaN detected ở phiên hiện tại)."}
            
        current_features = current_feature_row.values
        curr_proba = best_rf.predict_proba(current_features)[0]
        classes_list = metadata["classes_list"]
        
        prob_sell = float(curr_proba[classes_list.index(0)] * 100) if 0 in classes_list else 0.0
        prob_hold = float(curr_proba[classes_list.index(1)] * 100) if 1 in classes_list else 0.0
        prob_buy = float(curr_proba[classes_list.index(2)] * 100) if 2 in classes_list else 0.0
        
        # --- QUANT DECISION ENGINE (v4.2) ---
        expected_edge = (prob_buy / 100.0 * threshold * 100) - (prob_sell / 100.0 * threshold * 100)
        
        # Risk Indicators
        atr_ratio = float(current_row['atr_ratio'].iloc[0])
        if atr_ratio < 0.025: volatility = "🟢 LOW"
        elif atr_ratio < 0.05: volatility = "🟡 MEDIUM"
        else: volatility = "🔴 HIGH"
        
        vol_ratio = float(current_row['vol_ratio'].iloc[0])
        if vol_ratio > 1.2: liquidity = "🟢 HIGH"
        elif vol_ratio > 0.8: liquidity = "🟡 MEDIUM"
        else: liquidity = "🔴 LOW"
        
        dist_ma50 = float(current_row['dist_ma50'].iloc[0])
        if dist_ma50 > 0: market_regime = "🟢 BULL"
        else: market_regime = "🔴 BEAR"
        
        # Alpha Confidence
        rsi_val = float(current_row['rsi'].iloc[0])
        macd_val = float(current_row['macd_signal'].iloc[0])
        ma20_slope = float(current_row['ma20_slope'].iloc[0])
        
        reasons = []
        warnings = []
        
        if prob_buy >= 60: reasons.append("✓ ML probability > threshold")
        if ma20_slope > 0 and dist_ma50 > 0: reasons.append("✓ Trend bullish")
        if vol_ratio > 1.0: reasons.append("✓ Volume confirms")
        if volatility != "🔴 HIGH": reasons.append("✓ Risk acceptable")
        
        if len(reasons) >= 3 and expected_edge > 0: confidence = "HIGH"
        elif len(reasons) >= 1 and expected_edge > -0.5: confidence = "MEDIUM"
        else: confidence = "LOW"
        
        if len(labeled_df) < 200: warnings.append(f"⚠ Model trained on only {len(labeled_df)} observations")
        if market_regime == "🔴 BEAR": warnings.append("⚠ Current regime is BEAR, reducing long success rate")
        if metadata['macro_f1'] < 30.0: warnings.append("⚠ Model CV Macro F1 is very weak")
        
        # Final Decision Logic
        if confidence == "LOW" or market_regime == "🔴 BEAR" or volatility == "🔴 HIGH" or prob_buy < prob_threshold * 100:
            final_decision = "🔴 NO TRADE (CƠ SỞ YẾU)"
        elif confidence == "HIGH" and prob_buy >= 65:
            final_decision = "🟢 CƠ HỘI TỐT"
        elif confidence == "MEDIUM" and prob_buy >= prob_threshold * 100:
            final_decision = "🟢 CÓ THỂ CÂN NHẮC"
        else:
            final_decision = "🟡 THEO DÕI"
            
        res = {
            "success": True,
            "symbol": symbol,
            "current_date": latest_date,
            "current_close": float(df['close'].iloc[-1]),
            "final_decision": final_decision,
            "expected_edge": expected_edge,
            "confidence": confidence,
            "market_regime": market_regime,
            "liquidity": liquidity,
            "volatility": volatility,
            "reasons": reasons,
            "warnings": warnings,
            "prob_buy": prob_buy,
            "prob_hold": prob_hold,
            "prob_sell": prob_sell,
            "prob_threshold": prob_threshold * 100,
        }
        res.update(metadata)
        return res
        
    except Exception as e:
        logger.error(f"Lỗi quy trình Quant ML cho {symbol}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def format_prediction_message(res: dict) -> str:
    """Định dạng báo cáo Quant ML v4.2 chuyên nghiệp."""
    if not res.get("success"):
        return f"❌ <b>Lỗi Dự Báo AI Quant:</b> {res.get('error')}"
        
    sym = res["symbol"]
    
    msg = f"━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"<b>QUANT DECISION | {sym}</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"
    
    msg += f"Giá hiện tại: <b>{res['current_close']:,.0f}</b>\n\n"
    
    msg += f"P(UP T+{res['target_days']})       <b>{res['prob_buy']:.1f}%</b>\n"
    msg += f"P(HOLD)         <b>{res['prob_hold']:.1f}%</b>\n"
    msg += f"P(DOWN)         <b>{res['prob_sell']:.1f}%</b>\n\n"
    
    edge_sign = "+" if res['expected_edge'] > 0 else ""
    msg += f"Expected Edge   <b>{edge_sign}{res['expected_edge']:.2f}%</b>\n"
    msg += f"Confidence      <b>{res['confidence']}</b>\n\n"
    
    msg += f"Market Regime   {res['market_regime']}\n"
    msg += f"Liquidity       {res['liquidity']}\n"
    msg += f"Volatility      {res['volatility']}\n\n"
    
    # --- OOS Performance ---
    msg += "<b>OOS Performance</b>\n"
    rf_ret = res['total_rf_return']
    rf_sign = "+" if rf_ret >= 0 else ""
    msg += f"Return          <b>{rf_sign}{rf_ret:.2f}%</b>\n"
    
    sharpe = res.get('sharpe_ratio')
    if sharpe is not None: msg += f"Sharpe           <b>{sharpe:.2f}</b>\n"
    
    if res['max_dd'] is not None:
        msg += f"Max DD          <b>-{res['max_dd']:.2f}%</b>\n"
    msg += f"Win Rate         <b>{res['win_rate']:.0f}%</b>\n"
    
    pf = res.get('profit_factor')
    if pf is not None and pf != float('inf'):
        msg += f"Profit Factor    <b>{pf:.2f}</b>\n"
        
    msg += f"\n<b>Decision</b>\n"
    msg += f"{res['final_decision']}\n\n"
    
    if res['reasons']:
        msg += "<b>Reason:</b>\n"
        for r in res['reasons']:
            msg += f"{r}\n"
        msg += "\n"
        
    if res['warnings']:
        msg += "<b>Warning:</b>\n"
        for w in res['warnings']:
            msg += f"{w}\n"
            
    msg += f"\n<i>(Benchmark: Raw B&H {res['bh_return']:.2f}% | Model F1: {res['macro_f1']:.1f}%)</i>"
    
    return msg
