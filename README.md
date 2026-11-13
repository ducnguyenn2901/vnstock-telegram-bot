<p align="center">
  <img src="logo.png" alt="Vnstock Telegram Bot Logo" width="180"/>
</p>

<h1 align="center">VNSTOCK TELEGRAM BOT & QUANT AI ASSISTANT</h1>

<p align="center">
  <b>An End-to-End Quantitative Trading & AI-Powered Vietnamese Stock Market Assistant for Telegram</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python Version"/>
  <img src="https://img.shields.io/badge/Telegram-Bot%20API-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram Bot"/>
  <img src="https://img.shields.io/badge/Data-Vnstock%204.x-008080?style=for-the-badge" alt="Vnstock Data"/>
  <img src="https://img.shields.io/badge/AI-Google%20Gemini-8E75B2?style=for-the-badge&logo=google&logoColor=white" alt="Google Gemini"/>
  <img src="https://img.shields.io/badge/ML-Scikit--Learn-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white" alt="Scikit-Learn"/>
  <img src="https://img.shields.io/badge/Database-SQLite%20%7C%20Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white" alt="Database"/>
</p>

---

## 📑 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Telegram Bot Commands](#-telegram-bot-commands)
- [Automated Workflows & Background Schedules](#-automated-workflows--background-schedules)
- [Project Directory Structure](#-project-directory-structure)
- [Getting Started & Installation](#-getting-started--installation)
  - [1. Prerequisites](#1-prerequisites)
  - [2. Clone & Environment Setup](#2-clone--environment-setup)
  - [3. Install Dependencies](#3-install-dependencies)
  - [4. Environment Variables Configuration (.env)](#4-environment-variables-configuration-env)
  - [5. Run the Bot](#5-run-the-bot)
- [24/7 Cloud Deployment (Render / VPS)](#-247-cloud-deployment-render--vps)
- [Quantitative Validation & Model Audit](#-quantitative-validation--model-audit)
- [Disclaimer](#-disclaimer)
- [Author & License](#-author--license)

---

## 🎯 Overview

**Vnstock Telegram Bot** is a production-grade, 24/7 intelligent financial assistant tailored for the Vietnamese equity market. Built on top of the `vnstock` data framework, **Google Gemini LLM**, and advanced Quantitative Machine Learning algorithms, this bot empowers traders and investors with:

1. **Multidimensional Stock Screening:** Query real-time market depth, corporate profiles, technical indicators, financial statements, valuation metrics, and news with interactive inline keyboards.
2. **Generative AI Analysis:** Leverage Google Gemini for instant stock evaluation, morning market intelligence briefs (RAG), conversational advice with chat history memory, and portfolio risk audits.
3. **Quantitative ML Engine (VNSTOCK QUANT v5.3):** Forecast T+3 return probabilities using an ensemble Random Forest model with TimeSeriesSplit validation, Market Regime detection (*BULL / BEAR / SIDEWAY*), and Kelly Criterion position sizing.
4. **Smart Money Flow Tracking:** Scan tick-by-tick order matching feeds in real time to detect large aggressive institutional buying transactions ($\ge$ 5 Billion VND).
5. **Virtual Portfolio & Risk Management:** Track buy/sell execution, calculate real-time PnL, manage DCA strategies, and trigger custom price alerts automatically.

---

## ✨ Key Features

### 1. Comprehensive Stock Analysis & Interactive Dashboard
- Type any 3-letter ticker directly (e.g., `HPG`, `TCB`, `FPT`) or execute `/analyze <TICKER>` to bring up the comprehensive analysis card.
- Seamless one-click navigation via Telegram Inline Keyboards:
  - 📊 **Quote & Depth:** Real-time trade prices, volume, top-3 bid/ask depth.
  - 🏢 **Company Profile:** Listing history, executive board, and shareholder structure.
  - 📈 **Technical Analysis:** Moving averages (MA20, MA50), RSI(14), MACD, Bollinger Bands, and automated consensus verdict.
  - 💰 **Fundamentals:** Revenue, net profit, net profit margins, and quarterly YoY/QoQ growth.
  - ⚖️ **Valuation & Stats:** P/E, P/B, ROE, ROA, EPS, and Beta coefficients.
  - 📰 **Corporate News:** Dividend schedules, insider trading filings, and financial press updates.

### 2. High-Resolution Chart Generation (Matplotlib)
- **Technical Chart (`/chart <TICKER>`):** Candlestick charting with MA20, MA50, Bollinger Bands overlay, trading volume histogram, and 14-period RSI indicator.
- **Financial Chart (`Financial Chart` button):** Visual quarterly comparisons of revenue and net profit for the last 4 quarters exported directly as an image buffer.

### 3. Generative AI Engine (Google Gemini)
- **AI Stock Valuation:** Synthesizes fundamental, technical, and news data to generate concise SWOT analysis and actionable BUY / HOLD / SELL recommendations.
- **Morning Market Brief (`/news`):** Aggregates daily macro updates, currency/gold movements, and sector highlights into an executive summary.
- **Portfolio Risk Review:** Evaluates user portfolio holdings, asset concentration risk, and sector exposure.
- **Context-Aware Chat:** Conversational financial assistant with multi-turn persistent conversation memory.

### 4. Quantitative Machine Learning (VNSTOCK QUANT v5.3)
- **Supervised Classification:** Random Forest classifier trained on rolling financial features with temporal cross-validation (`TimeSeriesSplit`).
- **Engineered Features:** Multi-horizon returns (`ret_1d`, `ret_3d`, `ret_5d`, `ret_10d`, `ret_20d`), MA distances, MA20 slope, Bollinger Band Width (`bbw`), ATR ratio, volume surges, and market regime labels.
- **Risk & Sizing:** Probability calibration, expected edge calculation, and Kelly-based dynamic position allocation.

### 5. Smart Money Tracker (Whale Order Detection)
- Inspects real-time intraday tick-by-tick transaction logs via `/shark <TICKER>`.
- Flags aggressive block market orders exceeding 5 Billion VND, displaying execution timestamps, matched volumes, and trade values.

### 6. Strategy Backtesting Engine
- Run historical simulations via `/backtest <TICKER> <STRATEGY>`:
  - `breakout`: Resistance breakout with volume confirmation.
  - `squeeze`: Volatility breakout from Bollinger Band squeezes.
  - `uptrend`: Moving average pullbacks and trend following.
  - `rf_signal`: Machine learning model alpha simulation.
- Generates actionable metrics: Trade count, Win Rate (%), Average PnL, Maximum Drawdown (MDD), and Total Return vs. Buy & Hold.

### 7. Virtual Portfolio & DCA Tracker
- Record trades: `/buy`, `/sell`, `/dca`.
- Monitor overall asset valuation and floating PnL (Unrealized Profit/Loss) in real time with `/portfolio`.

### 8. Real-Time Market Scanner & Automated Price Alerts
- `/scanner`: Scans the entire VN100 universe every 30 minutes for Volume Breakouts (> 1.5x MA20) and Golden Cross signals.
- `/alert`: Customizable price thresholds checked every 5 minutes by the background job queue.

### 9. Mutual Funds (Fmarket) & ETF Support
- Direct integration with open-ended mutual funds via `/fund <TICKER>` (e.g., `VESAF`, `DCDS`, `VEOF`), displaying NAV, asset manager, and investment objectives.
- Full support for major Vietnamese ETFs (e.g., `FUESSVFL`, `E1VFVN30`).

---

## 🤖 Telegram Bot Commands

| Command | Usage Example | Description |
| :--- | :--- | :--- |
| `/start` or `/help` | `/start` | Displays the welcome guide and detailed instructions for all features. |
| `/analyze` or `/pt` | `/analyze TCB` | Full multi-dimensional stock evaluation with interactive buttons (or **simply send `TCB`**). |
| `/quick` | `/quick FPT` | Quick price snapshot, volume, and top bid/ask order book depth. |
| `/chart` | `/chart HPG` | Generates a 90-day candlestick chart with MA, Bollinger Bands, Volume, and RSI. |
| `/macro` | `/macro` | Macroeconomic overview: VN-Index, HNX, UPCOM, market breadth, gold & FX rates. |
| `/news` | `/news` | Generates an AI-curated Morning Market Briefing via Google Gemini. |
| `/shark` | `/shark MWG` | Scans intraday tick trades for aggressive block orders ($\ge$ 5 Billion VND). |
| `/predict` | `/predict SSI` | Trains an ML Random Forest model to forecast T+3 return probabilities. |
| `/backtest` | `/backtest TCB breakout` | Simulates trading strategies (`breakout`, `squeeze`, `uptrend`, `rf_signal`). |
| `/screen` | `/screen` | Pre-configured market screener for fundamentally sound and trending stocks. |
| `/scanner` | `/scanner` | Scans VN100 stocks for immediate volume surges and technical crossovers. |
| `/fund` | `/fund VESAF` | Retrieves details and NAV history for open-ended mutual funds from Fmarket. |
| `/buy` | `/buy HPG 1000 28.5` | Adds a buy transaction: 1,000 shares of HPG at 28.5 (k VND/share). |
| `/sell` | `/sell HPG 500` | Sells 500 shares of HPG at the prevailing market price. |
| `/dca` | `/dca FPT 200 130` | Dollar-Cost Averaging: records 200 shares of FPT at 130. |
| `/portfolio` | `/portfolio` | Displays real-time portfolio holdings, capital allocation, and PnL. |
| `/alert` | `/alert HPG > 30` | Sets a real-time price notification triggered when price exceeds 30. |
| `/sync` | `/sync` | Triggers a manual sync of historical EOD price data for VN100 into local storage. |

---

## ⏰ Automated Workflows & Background Schedules

The bot operates a non-blocking `JobQueue` scheduled around Vietnam market trading hours (UTC+7 / GMT+7):

```
       09:15                         15:00       15:20       16:00
─────────┼─────────────────────────────┼───────────┼───────────┼────────►
     [Quant T1]                    [Quant T3]  [Data Sync] [Quant T0]
   Morning Fills                  Afternoon    Sync EOD    VN30 AI Quant
   Execution                      Settlement   Warehouse   Next-Day Signals
```

- **Every 5 Minutes:** Executes `check_alerts_job` to evaluate price triggers and portfolio stop-loss/take-profit alerts.
- **Every 30 Minutes:** Runs `run_scanner_job` across VN100 for intraday breakouts.
- **09:15 (Mon - Fri):** **Quant T1** — Evaluates morning fill prices for active quantitative recommendations.
- **15:00 (Mon - Fri):** **Quant T3** — Closes completed T+3 holding cycles, calculates realized PnL, and logs validation data.
- **15:20 (Mon - Fri):** **Data Sync** — Downloads and updates End-of-Day (EOD) OHLCV records for all VN100 tickers into SQLite/Supabase.
- **16:00 (Mon - Fri):** **Quant T0** — Trains and evaluates all 30 tickers in the VN30 basket, notifying the administrator of high-probability trade setups for the next session.

---

## 📂 Project Directory Structure

```plaintext
vnstock-telegram-bot/
├── bot.py                     # Main application entry point & embedded HTTP health server
├── config.py                  # System settings, environment loader, and number formatters
├── database.py                # Dual-engine database adapter (SQLite / Supabase PostgreSQL)
├── daily_forward_runner.py    # Operational orchestrator for automated T0/T1/T3 Quant cycles
├── run_validation.py          # Standalone ML validation & signal quality benchmark script
├── test_modules.py            # Unit & integration test suite covering all modules
├── requirements.txt           # Python package requirements with vnstock extra index
├── supabase_schema.sql        # Database migration schema for Supabase paper trading logs
├── logo.png                   # Project branding banner
├── .env.example               # Template environment configuration file
│
├── modules/                   # Core business logic & specialized service handlers
│   ├── ai_assistant.py        # Google Gemini integration (evaluations, chatbot, news summary)
│   ├── alert_checker.py       # Background price alert evaluator
│   ├── alert_handlers.py      # User command handlers for creating alerts
│   ├── backtester.py          # Historical strategy simulation engine
│   ├── chart_generator.py     # Matplotlib technical and quarterly financial charts
│   ├── data_sync.py           # EOD price synchronization worker
│   ├── fund_data.py           # Fmarket mutual fund data parser
│   ├── fundamental_data.py    # Balance sheet, income statement, and financial ratios
│   ├── intraday_scanner.py    # VN100 volume breakout & moving average cross scanner
│   ├── macro_data.py          # Market index aggregates, market breadth, and commodities
│   ├── market_data.py         # Real-time quotes, order book depth, and OHLCV history
│   ├── ml_predictor.py        # Random Forest quantitative modeling & feature engineering
│   ├── news_events.py         # Corporate actions, dividend dates, and financial news
│   ├── paper_trading_logger.py# Audit trail for quantitative forward test lifecycle
│   ├── portfolio_handlers.py  # User portfolio management (Buy, Sell, DCA, Valuation)
│   ├── reference_data.py      # Company listing metadata, leadership, and ownership
│   ├── screener_handlers.py   # Stock screening logic
│   ├── smart_money.py         # Whale block order detector (tick-by-tick parsing)
│   ├── technical_analysis.py  # Technical indicators (SMA, RSI, MACD, BBands)
│   └── valuation_stats.py     # P/E, P/B, EPS, historical valuation analysis
│
├── scripts/                   # Operational and maintenance scripts
│   ├── check_db_health.py     # Data integrity validator for paper trading records
│   └── conditional_alpha_audit.py # Quantitative regime alpha auditor
│
├── data/                      # Local storage directory (SQLite databases, cache files)
└── logs/                      # Log output directory for background jobs and errors
```

---

## 🚀 Getting Started & Installation

### 1. Prerequisites
- **Python:** Version `3.10`, `3.11`, or `3.12`.
- **Telegram Bot Token:** Obtainable from [@BotFather](https://t.me/BotFather).
- **Google Gemini API Key:** Free key available at [Google AI Studio](https://aistudio.google.com/).
- **Vnstock API Key:** Register an account at [vnstocks.com](https://vnstocks.com).

### 2. Clone & Environment Setup

Clone this repository and create a clean Python virtual environment:

```bash
git clone https://github.com/ducnguyenn2901/vnstock-telegram-bot.git
cd vnstock-telegram-bot

# Create a virtual environment
python -m venv venv

# Activate on Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# Activate on Linux / macOS:
source venv/bin/activate
```

### 3. Install Dependencies

Install the required packages using the official Vnstock package index:

```bash
pip install -r requirements.txt
```

> [!NOTE]
> `requirements.txt` includes `--extra-index-url https://vnstocks.com/api/simple` at the top to ensure `vnstock` and `vnai` packages are downloaded from the official repository.

### 4. Environment Variables Configuration (.env)

Copy the example environment file:

```bash
cp .env.example .env
```

Open `.env` and fill in your credentials:

```ini
# Telegram Bot Token from @BotFather
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ

# Vnstock API Key
VNSTOCK_API_KEY=your_vnstock_key_here

# Google Gemini API Key
GEMINI_API_KEY=AIzaSyD...

# Admin Telegram Chat ID (obtain via @userinfobot)
ADMIN_CHAT_ID=1021481711

# Leave blank to use local SQLite (bot_database.db), or provide a Supabase/PostgreSQL URL:
DATABASE_URL=

# Port for cloud health check web server
PORT=8080
```

### 5. Run the Bot

Verify your installation with the automated test suite:

```bash
python test_modules.py
```

Launch the bot:

```bash
python bot.py
```

Expected startup logs:
```text
🌐 Đã mở cổng Health Check Server trên PORT: 8080
🚀 Đang khởi động Vnstock Telegram Bot...
✅ Bot đang hoạt động! Nhấn Ctrl+C để dừng bot.
```

Your bot is now live and listening for messages on Telegram!

---

## ☁️ 24/7 Cloud Deployment (Render / VPS)

The project includes a lightweight HTTP health check server bound to `PORT` (default `8080`). This satisfies cloud hosting keep-alive requirements (such as Render Free Web Services).

### Deploying to Render:
1. Push your code to your GitHub repository.
2. Navigate to [Render Dashboard](https://dashboard.render.com/) -> Click **New** -> **Web Service**.
3. Select and connect your repository.
4. Set the build and runtime parameters:
   - **Environment:** `Python`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
5. In **Advanced** -> **Environment Variables**, configure:
   - `TELEGRAM_BOT_TOKEN`
   - `VNSTOCK_API_KEY`
   - `GEMINI_API_KEY`
   - `ADMIN_CHAT_ID`
   - `DATABASE_URL` (optional, for Supabase)
6. Click **Create Web Service**. Your bot will remain online 24/7.

---

## 📊 Quantitative Validation & Model Audit

The repository contains automated tools to evaluate signal reliability and strategy expectancy:

1. **Benchmark Model Quality Across Representative VN30 Assets:**
   ```bash
   python run_validation.py
   ```
   *Computes Win Rate, Profit Factor, Brier Score, and Expectancy across HIGH, MEDIUM, and LOW conviction signals.*

2. **Verify Database & Forward Testing Integrity:**
   ```bash
   python scripts/check_db_health.py
   ```
   *Audits the completion lifecycle of T0 signals transitioning through T1 entry to T3 realization.*

3. **Audit Alpha Performance by Market Regime:**
   ```bash
   python scripts/conditional_alpha_audit.py
   ```

---

## ⚠️ Disclaimer

- All financial analysis, predictions, indicators, and algorithmic signals provided by this software are **strictly for educational, research, and informational purposes**.
- This project **does not constitute financial, investment, or trading advice**.
- The author accepts **no liability** for any direct or indirect financial loss incurred from using this bot.
- Investors must exercise due diligence and evaluate their personal risk tolerance before executing any market transactions.

---

## 👨‍💻 Author & License

- **Author:** [Duc Nguyen](https://github.com/ducnguyenn2901)
- **Repository:** [vnstock-telegram-bot](https://github.com/ducnguyenn2901/vnstock-telegram-bot)
- **License:** Released under the [MIT License](LICENSE).
- **Contributions:** Contributions, bug reports, and feature pull requests are welcome!

<p align="center">
  <sub>Built with ❤️ for the Vietnamese investment community</sub>
</p>
