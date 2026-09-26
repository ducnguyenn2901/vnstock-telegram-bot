# -*- coding: utf-8 -*-
"""
Module Dự Đoán Xu Hướng Cổ Phiếu — VNSTOCK QUANT v5.3 (Validation & Audit Engine).

Nâng cấp:
- Restore SIDEWAY regime.
- Pure T+3 Prediction Logging for Calibration Audit.
"""

import logging
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV, cross_val_score
from sklearn.metrics import f1_score, log_loss, brier_score_loss
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression
import database as db

logger = logging.getLogger("MLPredictor")
MODEL_REGISTRY = {}
FEATURES = [
    'ret_1d', 'ret_3d', 'ret_5d', 'ret_10d', 'ret_20d',
    'dist_ma20', 'dist_ma50', 'ma20_slope', 'bbw', 'atr_ratio',
    'vol_ratio', 'vol_ratio_5_20', 'rsi', 'macd_signal',
    'dist_high20', 'dist_low20'
]

def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['ret_1d'] = df['close'].pct_change(1)
    df['ret_3d'] = df['close'].pct_change(3)
    df['ret_5d'] = df['close'].pct_change(5)
    df['ret_10d'] = df['close'].pct_change(10)
    df['ret_20d'] = df['close'].pct_change(20)

    ma20 = df['close'].rolling(20).mean()
    ma50 = df['close'].rolling(50).mean()
    df['dist_ma20'] = (df['close'] - ma20) / (ma20 + 1e-9)
    df['dist_ma50'] = (df['close'] - ma50) / (ma50 + 1e-9)
    df['ma20_slope'] = (ma20 - ma20.shift(5)) / (ma20.shift(5) + 1e-9)

    std20 = df['close'].rolling(20).std()
    df['bbw'] = ((ma20 + 2 * std20) - (ma20 - 2 * std20)) / (ma20 + 1e-9)

    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - df['close'].shift(1)).abs()
    tr3 = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr14 = tr.ewm(alpha=1/14, adjust=False).mean()
    df['atr_ratio'] = atr14 / (df['close'] + 1e-9)

    vol_ma20 = df['volume'].rolling(20).mean()
    vol_ma5 = df['volume'].rolling(5).mean()
    df['vol_ratio'] = df['volume'] / (vol_ma20 + 1e-9)
    df['vol_ratio_5_20'] = vol_ma5 / (vol_ma20 + 1e-9)

    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0)
    loss_s = (-delta.where(delta < 0, 0.0))
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss_s.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    df['rsi'] = 100.0 - (100.0 / (1.0 + rs))

    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    df['macd_signal'] = (macd - signal) / (df['close'] + 1e-9)

    high20 = df['high'].rolling(20).max()
    low20 = df['low'].rolling(20).min()
    df['dist_high20'] = (df['close'] / (high20 + 1e-9)) - 1.0
    df['dist_low20'] = (df['close'] / (low20 + 1e-9)) - 1.0

    df['avg_traded_value_20'] = (df['close'] * df['volume']).rolling(20).mean()
    return df

def get_vnindex_context(start_date, end_date):
    try:
        import datetime, requests
        start_ts = int(datetime.datetime.strptime(start_date, "%Y-%m-%d").timestamp())
        end_ts = int(datetime.datetime.strptime(end_date, "%Y-%m-%d").timestamp())
        url = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/index?resolution=1D&symbol=VNINDEX&from={start_ts}&to={end_ts}"
        r = requests.get(url, timeout=10)
        data = r.json()
        if 't' in data and len(data['t']) > 0:
            df = pd.DataFrame({
                'date': pd.to_datetime(data['t'], unit='s').astype(str).str[:10],
                'vni_close': data['c']
            })
            df['vni_ma20'] = df['vni_close'].rolling(20).mean()
            df['vni_ma50'] = df['vni_close'].rolling(50).mean()
            df['vni_ma20_slope'] = (df['vni_ma20'] - df['vni_ma20'].shift(5)) / (df['vni_ma20'].shift(5) + 1e-9)
            return df
    except Exception:
        pass
    return None

def train_and_predict(symbol: str, target_days: int = 3, threshold: float = 0.015, prob_threshold: float = 0.60) -> dict:
    global MODEL_REGISTRY
    symbol = symbol.upper().strip()

    try:
        raw_df = db.get_all_price_history(symbols=[symbol])
        import datetime
        end_date = datetime.date.today().strftime("%Y-%m-%d")
        start_date = (datetime.date.today() - datetime.timedelta(days=365 * 4)).strftime("%Y-%m-%d")

        if raw_df.empty or len(raw_df) < 150:
            import os, requests
            os.environ["VNSTOCK_TELEMETRY"] = "off"
            try:
                start_ts = int(datetime.datetime.strptime(start_date, "%Y-%m-%d").timestamp())
                end_ts = int(datetime.datetime.strptime(end_date, "%Y-%m-%d").timestamp())
                url = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?resolution=1D&symbol={symbol}&from={start_ts}&to={end_ts}"
                r = requests.get(url, timeout=15)
                data = r.json()
                if 't' in data and len(data['t']) > 0:
                    raw_df = pd.DataFrame({
                        'date': pd.to_datetime(data['t'], unit='s'),
                        'open': data['o'], 'high': data['h'], 'low': data['l'], 'close': data['c'], 'volume': data['v']
                    })
            except Exception:
                return {"success": False, "error": f"Không tải được dữ liệu cho {symbol}."}

        raw_df.columns = [str(c).lower() for c in raw_df.columns]
        if 'time' in raw_df.columns: raw_df.rename(columns={'time': 'date'}, inplace=True)
        elif 'datetime' in raw_df.columns: raw_df.rename(columns={'datetime': 'date'}, inplace=True)
        raw_df['date'] = raw_df['date'].astype(str).str[:10]
        raw_df = raw_df.sort_values('date').reset_index(drop=True)

        vni_df = get_vnindex_context(start_date, end_date)
        if vni_df is not None:
            raw_df = pd.merge(raw_df, vni_df, on='date', how='left')
            raw_df[['vni_close', 'vni_ma20', 'vni_ma50', 'vni_ma20_slope']] = raw_df[['vni_close', 'vni_ma20', 'vni_ma50', 'vni_ma20_slope']].ffill()

        latest_date = raw_df['date'].iloc[-1]
        metadata = {}
        best_rf = None

        cache_key = f"{symbol}_{target_days}_{threshold}_{prob_threshold}"
        if cache_key in MODEL_REGISTRY and MODEL_REGISTRY[cache_key]['latest_date'] == latest_date:
            best_rf = MODEL_REGISTRY[cache_key]['model']
            metadata = MODEL_REGISTRY[cache_key]['metadata']
            df = compute_features(raw_df)
        else:
            df = compute_features(raw_df)
            future_return = (df['close'].shift(-target_days) / df['close']) - 1.0
            target = pd.Series(1, index=df.index)
            target[future_return > threshold] = 2
            target[future_return < -threshold] = 0
            df['target'] = target

            labeled_df = df.dropna(subset=FEATURES).iloc[:-target_days].copy()
            labeled_df['target'] = labeled_df['target'].astype(int)
            if len(labeled_df) < 60: return {"success": False, "error": "Dữ liệu không đủ."}

            split_idx = int(len(labeled_df) * 0.8)
            train_df = labeled_df.iloc[:split_idx - target_days]
            test_df = labeled_df.iloc[split_idx:]

            X_train, y_train = train_df[FEATURES].values, train_df['target'].values
            X_test, y_test = test_df[FEATURES].values, test_df['target'].values

            tscv = TimeSeriesSplit(n_splits=5, gap=target_days)
            search = RandomizedSearchCV(
                RandomForestClassifier(random_state=42, class_weight='balanced'),
                param_distributions={'n_estimators': [50], 'max_depth': [3, 5], 'min_samples_leaf': [3]},
                n_iter=4, cv=tscv, scoring='f1_macro', random_state=42, n_jobs=1
            )
            search.fit(X_train, y_train)
            best_estimator = search.best_estimator_

            # Walk-Forward OOF
            train_future_ret = (train_df['close'].shift(-target_days) / train_df['close'] - 1.0).values * 100
            oof_buy_proba = np.full(len(X_train), np.nan)
            for fold_tr_idx, fold_val_idx in tscv.split(X_train):
                fold_rf = RandomForestClassifier(**best_estimator.get_params())
                # Đồng nhất Calibration Space với Inference
                fold_calib = CalibratedClassifierCV(fold_rf, cv=3, method='sigmoid')
                fold_calib.fit(X_train[fold_tr_idx], y_train[fold_tr_idx])
                fold_p = fold_calib.predict_proba(X_train[fold_val_idx])
                fold_cls = list(fold_calib.classes_)
                if 2 in fold_cls: oof_buy_proba[fold_val_idx] = fold_p[:, fold_cls.index(2)]

            valid_mask = ~np.isnan(oof_buy_proba) & ~np.isnan(train_future_ret)
            ir = IsotonicRegression(out_of_bounds='clip')
            if valid_mask.sum() > 10: ir.fit(oof_buy_proba[valid_mask], train_future_ret[valid_mask])
            else: ir = None

            try:
                best_rf = CalibratedClassifierCV(best_estimator, method='sigmoid', cv=tscv)
                best_rf.fit(X_train, y_train)
            except: best_rf = best_estimator
            
            y_proba = best_rf.predict_proba(X_test)
            classes_list = list(best_rf.classes_)

            FEE_PER_SIDE = 0.0015
            SLIPPAGE_PER_SIDE = 0.0010
            TOTAL_COST_PER_SIDE = FEE_PER_SIDE + SLIPPAGE_PER_SIDE

            buy_idx = classes_list.index(2) if 2 in classes_list else -1
            sell_idx = classes_list.index(0) if 0 in classes_list else -1

            cash = 100000.0  
            shares = 0.0
            entry_price = 0.0
            active_quality = "NONE"
            active_atr = 0.0
            
            equity_curve = [cash]
            trades = []
            prediction_logs = []  # PURE T+3 ALPHA LOGS
            pending_buy = False
            pending_sell = False

            test_closes = test_df['close'].values
            test_opens = test_df['open'].values
            test_lows = test_df['low'].values

            for i in range(len(test_df)):
                curr_open = float(test_opens[i])
                curr_close = float(test_closes[i])
                curr_low = float(test_lows[i])
                
                p_buy = float(y_proba[i, buy_idx]) if buy_idx != -1 else 0.0
                p_sell = float(y_proba[i, sell_idx]) if sell_idx != -1 else 0.0

                # Log pure T+3 prediction alpha
                if i + target_days < len(test_df):
                    idx = test_df['date'].iloc[i] if 'date' in test_df.columns else i
                    prob_buy_val = p_buy
                    expected_return = float(ir.predict([p_buy])[0]) if ir is not None else 0.0
                    future_ret = (test_closes[i + target_days] - curr_close) / curr_close
                    actual_t3 = future_ret * 100
                    stock_bulls = sum([test_df['dist_ma50'].iloc[i] > 0, test_df['dist_ma20'].iloc[i] > 0, test_df['ma20_slope'].iloc[i] > 0])
                    stock_regime = "BULL" if stock_bulls >= 2 else ("SIDEWAY" if stock_bulls == 1 else "BEAR")
                    if 'vni_close' in test_df.columns and pd.notna(test_df['vni_close'].iloc[i]):
                        mkt_bulls = sum([test_df['vni_close'].iloc[i] > test_df['vni_ma50'].iloc[i], 
                                         test_df['vni_close'].iloc[i] > test_df['vni_ma20'].iloc[i], 
                                         test_df['vni_ma20_slope'].iloc[i] > 0])
                        market_regime = "BULL" if mkt_bulls >= 2 else ("SIDEWAY" if mkt_bulls == 1 else "BEAR")
                    else:
                        market_regime = "UNKNOWN"
                    if market_regime == "BULL" and stock_regime == "BULL": context = "🟢 STRONG LONG"
                    elif market_regime == "BULL" and stock_regime == "BEAR": context = "🟡 WEAK RELATIVE"
                    elif market_regime == "BEAR" and stock_regime == "BULL": context = "🟡 CAUTION (COUNTER)"
                    elif market_regime == "SIDEWAY" or stock_regime == "SIDEWAY": context = f"⚪ TRANSITION ({market_regime}/{stock_regime})"
                    else: context = "🔴 FULL BEAR"

                    prediction_logs.append({
                        'date': str(idx)[:10] if hasattr(idx, '__str__') else str(idx),
                        'p_buy': prob_buy_val * 100,
                        'expected_return': expected_return,
                        'actual_t3': actual_t3,
                        'error': actual_t3 - expected_return,
                        'market_regime': context,
                        'stock_regime': stock_regime
                    })

                if pending_buy and shares == 0:
                    eff_buy = curr_open * (1.0 + TOTAL_COST_PER_SIDE)
                    shares = cash / eff_buy
                    entry_price = eff_buy
                    cash = 0.0
                    pending_buy = False

                if pending_sell and shares > 0:
                    eff_sell = curr_open * (1.0 - TOTAL_COST_PER_SIDE)
                    cash_pnl = (shares * eff_sell) - (shares * entry_price)
                    pnl = ((eff_sell - entry_price) / entry_price) * 100
                    cash = shares * eff_sell
                    trades.append({'pnl_pct': pnl, 'cash_pnl': cash_pnl, 'quality': active_quality})
                    shares = 0.0
                    entry_price = 0.0
                    pending_sell = False

                if shares > 0:
                    stop_pct = max(active_atr * 1.5, 0.04)
                    stop_price = entry_price * (1.0 - stop_pct)
                    if curr_low <= stop_price:
                        exec_price = min(curr_open, stop_price)
                        eff_sell_net = exec_price * (1.0 - TOTAL_COST_PER_SIDE)
                        cash_pnl = (shares * eff_sell_net) - (shares * entry_price)
                        pnl = ((eff_sell_net - entry_price) / entry_price) * 100
                        cash = shares * eff_sell_net
                        trades.append({'pnl_pct': pnl, 'cash_pnl': cash_pnl, 'quality': active_quality})
                        shares = 0.0
                        entry_price = 0.0
                        pending_sell = False

                if shares > 0: equity_curve.append(shares * curr_close)
                else: equity_curve.append(cash)

                if i + 1 < len(test_df):
                    if shares == 0 and not pending_buy:
                        if p_buy >= prob_threshold:
                            pending_buy = True
                            active_atr = float(test_df['atr_ratio'].iloc[i])
                            stock_bulls = sum([test_df['dist_ma50'].iloc[i] > 0, test_df['dist_ma20'].iloc[i] > 0, test_df['ma20_slope'].iloc[i] > 0])
                            # KHÔI PHỤC SIDEWAY CHO HISTORICAL
                            hist_stock_regime = "BULL" if stock_bulls >= 2 else ("SIDEWAY" if stock_bulls == 1 else "BEAR")
                            hist_ir_val = float(ir.predict([p_buy])[0]) if ir is not None else 0.0
                            hist_edge = hist_ir_val - (TOTAL_COST_PER_SIDE * 2) * 100
                            
                            reasons = 0
                            if p_buy >= prob_threshold: reasons += 1
                            if hist_stock_regime == "BULL": reasons += 1
                            if hist_edge > 0: reasons += 1
                            active_quality = "HIGH" if reasons >= 3 else ("MEDIUM" if reasons == 2 else "LOW")
                            
                    elif shares > 0 and not pending_sell:
                        if p_sell >= prob_threshold:
                            pending_sell = True

            if shares > 0:
                last_close = float(test_closes[-1])
                eff_sell = last_close * (1.0 - TOTAL_COST_PER_SIDE)
                cash_pnl = (shares * eff_sell) - (shares * entry_price)
                pnl = ((eff_sell - entry_price) / entry_price) * 100
                cash = shares * eff_sell
                trades.append({'pnl_pct': pnl, 'cash_pnl': cash_pnl, 'quality': active_quality})
                equity_curve[-1] = cash

            eq_series = pd.Series(equity_curve)
            daily_returns = eq_series.pct_change().dropna()
            
            sharpe_ratio = sortino_ratio = None
            if len(daily_returns) > 1 and daily_returns.std() != 0:
                sharpe_ratio = float((daily_returns.mean() / daily_returns.std()) * np.sqrt(252))
                downside_diff = np.minimum(daily_returns, 0)
                downside_dev = np.sqrt(np.mean(downside_diff**2))
                if downside_dev != 0: sortino_ratio = float(daily_returns.mean() / downside_dev * np.sqrt(252))
            
            win_trades = [t['pnl_pct'] for t in trades if t['pnl_pct'] > 0]
            loss_trades = [t['pnl_pct'] for t in trades if t['pnl_pct'] <= 0]
            win_rate = (len(win_trades) / len(trades)) if trades else 0.0
            avg_win = float(np.mean(win_trades)) if win_trades else 0.0
            avg_loss = float(np.mean(loss_trades)) if loss_trades else 0.0
            expectancy = float((win_rate * avg_win) + ((1 - win_rate) * avg_loss)) if trades else None
            
            gross_profit_dollar = sum([t['cash_pnl'] for t in trades if t['cash_pnl'] > 0])
            gross_loss_dollar = abs(sum([t['cash_pnl'] for t in trades if t['cash_pnl'] < 0]))
            profit_factor = float(gross_profit_dollar / gross_loss_dollar) if gross_loss_dollar != 0 else (float('inf') if gross_profit_dollar > 0 else None)

            q_stats = {}
            for q in ["HIGH", "MEDIUM", "LOW"]:
                q_pnl = [t['pnl_pct'] for t in trades if t['quality'] == q]
                if q_pnl:
                    q_w = [x for x in q_pnl if x > 0]
                    q_l = [x for x in q_pnl if x <= 0]
                    qw_r = len(q_w) / len(q_pnl)
                    qw_a = np.mean(q_w) if q_w else 0.0
                    ql_a = np.mean(q_l) if q_l else 0.0
                    q_stats[q] = (qw_r * qw_a) + ((1 - qw_r) * ql_a)
                else: q_stats[q] = None

            metadata = {
                "isotonic_regressor": ir, "sharpe_ratio": sharpe_ratio, "sortino_ratio": sortino_ratio,
                "win_rate": win_rate, "avg_win": avg_win, "avg_loss": avg_loss,
                "expectancy": expectancy, "profit_factor": profit_factor,
                "total_trades": len(trades), "q_stats": q_stats,
                "trades": trades, "prediction_logs": prediction_logs, # EXPOSED CHO VALIDATION CAMPAIGN
                "roundtrip_cost": (TOTAL_COST_PER_SIDE * 2) * 100, "classes_list": classes_list,
            }
            MODEL_REGISTRY[cache_key] = {"model": best_rf, "latest_date": latest_date, "metadata": metadata}

        # ===== BƯỚC 3: INFERENCE & DECISION ENGINE =====
        current_row = df.iloc[-1:].copy()
        current_feature_row = current_row[FEATURES].copy()
        if current_feature_row.isna().any().any(): return {"success": False, "error": "Đặc trưng chứa NaN."}

        curr_proba = best_rf.predict_proba(current_feature_row.values)[0]
        classes_list = metadata["classes_list"]
        prob_sell = float(curr_proba[classes_list.index(0)] * 100) if 0 in classes_list else 0.0
        prob_hold = float(curr_proba[classes_list.index(1)] * 100) if 1 in classes_list else 0.0
        prob_buy = float(curr_proba[classes_list.index(2)] * 100) if 2 in classes_list else 0.0

        ir = metadata.get("isotonic_regressor")
        expected_return = float(ir.predict([prob_buy / 100.0])[0]) if ir is not None else 0.0
        roundtrip_cost_pct = metadata.get("roundtrip_cost", 0.5)
        expected_edge = expected_return - roundtrip_cost_pct

        dist_ma50, dist_ma20, ma20_slope = float(current_row['dist_ma50'].iloc[0]), float(current_row['dist_ma20'].iloc[0]), float(current_row['ma20_slope'].iloc[0])
        stock_bulls = sum([dist_ma50 > 0, dist_ma20 > 0, ma20_slope > 0])
        stock_regime = "BULL" if stock_bulls >= 2 else ("SIDEWAY" if stock_bulls == 1 else "BEAR")
        
        if 'vni_close' in current_row.columns and pd.notna(current_row['vni_close'].iloc[0]):
            mkt_bulls = sum([current_row['vni_close'].iloc[0] > current_row['vni_ma50'].iloc[0], 
                             current_row['vni_close'].iloc[0] > current_row['vni_ma20'].iloc[0], 
                             current_row['vni_ma20_slope'].iloc[0] > 0])
            market_regime = "BULL" if mkt_bulls >= 2 else ("SIDEWAY" if mkt_bulls == 1 else "BEAR")
        else: market_regime = "UNKNOWN"

        if market_regime == "BULL" and stock_regime == "BULL": context = "🟢 STRONG LONG"
        elif market_regime == "BULL" and stock_regime == "BEAR": context = "🟡 WEAK RELATIVE"
        elif market_regime == "BEAR" and stock_regime == "BULL": context = "🟡 CAUTION (COUNTER)"
        elif market_regime == "SIDEWAY" or stock_regime == "SIDEWAY": context = f"⚪ TRANSITION ({market_regime}/{stock_regime})"
        else: context = "🔴 FULL BEAR"

        reasons = 0
        if prob_buy >= prob_threshold * 100: reasons += 1
        if stock_regime == "BULL": reasons += 1
        if expected_edge > 0: reasons += 1
        signal_quality = "HIGH" if reasons >= 3 else ("MEDIUM" if reasons == 2 else "LOW")

        if "FULL BEAR" in context: final_decision = "🔴 NO TRADE (FULL BEAR)"
        elif signal_quality == "LOW" or prob_buy < prob_threshold * 100: final_decision = "🔴 NO TRADE (TÍN HIỆU YẾU)"
        elif expected_edge <= 0: final_decision = "🔴 NO TRADE (EDGE ÂM SAU PHÍ)"
        elif signal_quality == "HIGH": final_decision = "🟢 CƠ HỘI TỐT"
        else: final_decision = "🟢 CÓ THỂ CÂN NHẮC"

        atr_ratio = float(current_row['atr_ratio'].iloc[0])
        stop_loss_pct = max(atr_ratio * 1.5, 0.04) 

        if "NO TRADE" in final_decision or expected_edge <= 0:
            suggested_position, position_risk = 0.0, 0.0
        else:
            raw_size = 0.015 / stop_loss_pct
            edge_scalar = max(0.0, min(1.0, expected_edge / 2.0))
            quality_scalar = 1.0 if signal_quality == "HIGH" else 0.6  
            suggested_position = min(raw_size * edge_scalar * quality_scalar, 0.25) * 100
            position_risk = (suggested_position / 100) * stop_loss_pct * 100

        res = {
            "success": True, "symbol": symbol, "prob_buy": prob_buy, "prob_hold": prob_hold, "prob_sell": prob_sell,
            "expected_return": expected_return, "expected_edge": expected_edge, "market_context": context,
            "market_regime": market_regime, "stock_regime": stock_regime,
            "signal_quality": signal_quality, "suggested_position": suggested_position, "position_risk": position_risk,
            "final_decision": final_decision
        }
        res.update(metadata)
        return res
    except Exception as e:
        logger.error(f"Lỗi Quant ML: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

def format_prediction_message(res: dict) -> str:
    if not res.get("success"): return f"❌ <b>Lỗi Dự Báo AI Quant:</b> {res.get('error')}"
    sym = res["symbol"]
    
    msg =  f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"VNSTOCK QUANT v5.3.1\n"
    msg += f"DECISION SUPPORT\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    msg += f"Symbol:       {sym}\n\n"
    
    msg += f"P(BUY):       {res['prob_buy']:.1f}%\n"
    msg += f"Expected T+3: {res['expected_return']:+.2f}%\n"
    msg += f"Market:       {res['market_context']}\n"
    msg += f"Stock:        {res['stock_regime']}\n\n"
    
    msg += f"Signal Quality:\n{res['signal_quality']}\n\n"
    
    pos, prk = res.get('suggested_position', 0), res.get('position_risk', 0)
    stop = max(float(res.get('atr_ratio', 0.04)) * 1.5, 0.04) * 100
    msg += f"Risk:\n"
    msg += f"Stop:         {stop:.1f}%\n"
    msg += f"Position Cap: {pos:.1f}%\n\n"
    
    msg += f"Decision:\n{res['final_decision']}\n\n"
    
    msg += f"Reason:\n"
    if "CƠ HỘI" in res['final_decision'] or "CÂN NHẮC" in res['final_decision']:
        msg += f"Positive ranking evidence exists,\n"
        msg += f"but universe-wide robustness is not established.\n"
    else:
        msg += f"Insufficient edge or defensive market regime.\n"
    
    return msg
