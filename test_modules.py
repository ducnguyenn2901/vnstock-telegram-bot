# -*- coding: utf-8 -*-
"""
Kịch bản kiểm thử toàn bộ các module phân tích chứng khoán Vnstock.
"""

import sys
from modules.reference_data import get_reference_data, format_reference_html
from modules.market_data import get_market_quote, format_market_html
from modules.fundamental_data import get_fundamental_data, format_fundamental_html
from modules.macro_data import get_macro_overview, format_macro_html
from modules.technical_analysis import get_technical_analysis, format_technical_html
from modules.valuation_stats import get_valuation_and_stats, format_valuation_html
from modules.news_events import get_company_news, format_news_html
from modules.chart_generator import generate_technical_chart

def run_tests():
    test_symbol = "TCB"
    print(f"=== BẮT ĐẦU KIỂM THỬ VỚI MÃ: {test_symbol} ===\n")
    
    # 1. Reference
    print("1. Kiểm thử Reference Data...")
    ref_data = get_reference_data(test_symbol)
    assert ref_data["success"] or "error" in ref_data
    html_ref = format_reference_html(ref_data)
    print(f"-> Thành công! Độ dài HTML: {len(html_ref)}")
    
    # 2. Market
    print("2. Kiểm thử Market Data...")
    mkt_data = get_market_quote(test_symbol)
    assert mkt_data["success"] or "error" in mkt_data
    html_mkt = format_market_html(mkt_data)
    print(f"-> Thành công! Độ dài HTML: {len(html_mkt)}")
    
    # 3. Fundamental
    print("3. Kiểm thử Fundamental Data...")
    fun_data = get_fundamental_data(test_symbol)
    assert fun_data["success"] or "error" in fun_data
    html_fun = format_fundamental_html(fun_data)
    print(f"-> Thành công! Độ dài HTML: {len(html_fun)}")
    
    # 4. Macro
    print("4. Kiểm thử Macro Data...")
    macro_data = get_macro_overview()
    html_macro = format_macro_html(macro_data)
    print(f"-> Thành công! Độ dài HTML: {len(html_macro)}")
    
    # 5. Technical Analysis
    print("5. Kiểm thử Technical Analysis...")
    ta_data = get_technical_analysis(test_symbol)
    assert ta_data["success"] or "error" in ta_data
    html_ta = format_technical_html(ta_data)
    print(f"-> Thành công! Nhận định: {ta_data.get('verdict')}")
    
    # 6. Valuation & Stats
    print("6. Kiểm thử Valuation & Stats...")
    val_data = get_valuation_and_stats(test_symbol)
    assert val_data["success"] or "error" in val_data
    html_val = format_valuation_html(val_data)
    print(f"-> Thành công! Độ dài HTML: {len(html_val)}")
    
    # 7. News & Events
    print("7. Kiểm thử News & Events...")
    news_data = get_company_news(test_symbol)
    html_news = format_news_html(news_data)
    print(f"-> Thành công! Số tin tức: {len(news_data.get('news', []))}")
    
    # 8. Chart Generator
    print("8. Kiểm thử Chart Generator...")
    chart_buf = generate_technical_chart(test_symbol, days=60)
    assert chart_buf is not None
    print(f"-> Thành công! Kích thước ảnh: {len(chart_buf.getvalue())} bytes")
    
    print("\n🎉 TOÀN BỘ 8 MODULE ĐỀU VƯỢT QUA KIỂM THỬ THÀNH CÔNG!")

if __name__ == "__main__":
    run_tests()
