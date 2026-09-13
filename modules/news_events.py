# -*- coding: utf-8 -*-
"""
Module 7: Tin tức & Sự kiện doanh nghiệp (News & Events).
Thu thập tin tức báo chí mới nhất và sự kiện doanh nghiệp.
"""

import logging
import vnstock

logger = logging.getLogger("NewsEvents")

def get_company_news(symbol: str) -> dict:
    """
    Lấy danh sách tin tức mới nhất của doanh nghiệp.
    """
    symbol = symbol.upper().strip()
    res = {
        "symbol": symbol,
        "success": False,
        "news": [],
        "events": [],
        "error": None
    }
    
    try:
        ref = vnstock.Reference()
        comp = ref.company(symbol)
        
        # 1. Tin tức
        try:
            df_n = comp.news()
            if df_n is not None and not df_n.empty:
                articles = []
                for _, row in df_n.head(5).iterrows():
                    title = row.get("title", "")
                    time_str = str(row.get("publish_time", ""))[:16]
                    url = row.get("url", "")
                    if url and url.startswith("/"):
                        url = f"https://vietstock.vn{url}"
                    articles.append({
                        "title": title,
                        "time": time_str,
                        "url": url,
                        "head": str(row.get("head", ""))[:120] + "..." if row.get("head") else ""
                    })
                res["news"] = articles
                res["success"] = True
        except Exception as e:
            logger.warning(f"Lỗi khi lấy tin tức cho {symbol}: {e}")
            
        # 2. Sự kiện
        try:
            df_e = comp.events()
            if df_e is not None and not df_e.empty:
                events = []
                for _, row in df_e.head(5).iterrows():
                    events.append({
                        "name": row.get("event_name") or row.get("name") or "Sự kiện",
                        "date": str(row.get("date") or row.get("event_date", ""))[:10],
                    })
                res["events"] = events
        except Exception as e:
            logger.debug(f"Không có sự kiện cho {symbol}: {e}")
            
    except Exception as e:
        logger.error(f"Lỗi khi truy vấn tin tức cho {symbol}: {e}")
        res["error"] = str(e)
        
    return res

def format_news_html(data: dict) -> str:
    """Định dạng tin tức & sự kiện thành thông điệp HTML cho Telegram."""
    symbol = data.get("symbol", "")
    news_list = data.get("news", [])
    events_list = data.get("events", [])
    
    if not news_list and not events_list:
        return f"📰 <b>Không có tin tức mới ghi nhận cho mã {symbol}.</b>"
        
    html = [
        f"📰 <b>TIN TỨC & SỰ KIỆN: {symbol}</b>",
        f"━━━━━━━━━━━━━━━━━━━━",
    ]
    
    if news_list:
        html.append(f"🔥 <b>Tin Tức Mới Nhất:</b>")
        for i, item in enumerate(news_list, 1):
            title = item.get("title", "")
            time_str = item.get("time", "")
            url = item.get("url", "")
            if url:
                html.append(f"{i}. <a href=\"{url}\"><b>{title}</b></a>\n   🕒 <i>{time_str}</i>")
            else:
                html.append(f"{i}. <b>{title}</b> (<i>{time_str}</i>)")
                
    if events_list:
        html.append(f"\n📅 <b>Lịch Sự Kiện Sắp Tới:</b>")
        for ev in events_list:
            html.append(f"• {ev.get('name')} (Ngày: {ev.get('date')})")
            
    return "\n".join(html)
