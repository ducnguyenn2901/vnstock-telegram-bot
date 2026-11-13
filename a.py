import pandas as pd
import yfinance as yf

# FUESSVFL.VN: Quỹ ETF mô phỏng 100% rổ VNFINLEAD trên HOSE
# ^VNINDEX: Chỉ số VN-Index
ticker = "FUESSVFL.VN"
data = yf.download(ticker, start="2021-01-01", interval="1mo")

# Xử lý format
df = data[["Close"]].reset_index()
df.columns = ["Date", "VNINDEX_BANK"]
df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m")

# Tải thêm VN-Index cùng kỳ
vnindex = yf.download("^VNINDEX", start="2021-01-01", interval="1mo")[
    ["Close"]
].reset_index()
vnindex.columns = ["Date", "VNINDEX"]
vnindex["Date"] = pd.to_datetime(vnindex["Date"]).dt.strftime("%Y-%m")

# Ghép hai bảng
final_df = pd.merge(df, vnindex, on="Date", how="inner")
final_df.to_csv("Bank_Index_Real_Yahoo.csv", index=False)

print("Đã tải xong dữ liệu thực tế:")
print(final_df.head())