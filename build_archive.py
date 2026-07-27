import os
import re
import urllib.request
from bs4 import BeautifulSoup

CHANNEL_USERNAME = "mohammedalakhras"  
SITE_URL = "https://mohammedalakhras.github.io" 
POSTS_PER_PAGE = 20
OUTPUT_DIR = "posts"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# === 2. جلب المنشورات من Telegram Web ===
def fetch_telegram_posts(channel, limit=100):
    url = f"https://t.me/s/{channel}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        html = urllib.request.urlopen(req).read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching channel: {e}")
        return []

    soup = BeautifulSoup(html, 'html.parser')
    messages = soup.find_all('div', class_='tgme_widget_message')
    
    posts = []
    for msg in messages:
        post_id_raw = msg.get('data-post')
        if not post_id_raw:
            continue
        post_id = post_id_raw.split('/')[-1]
        
        text_div = msg.find('div', class_='tgme_widget_message_text')
        text_content = text_div.get_text(separator="\n").strip() if text_div else "منشور بدون نص"
        html_content = text_div.decode_contents() if text_div else ""
        
        # وقت المنشور
        time_tag = msg.find('time')
        date_str = time_tag.get('datetime') if time_tag else None

        posts.append({
            'id': post_id,
            'text': text_content,
            'html': html_content,
            'date': date_str,
            'url': f"https://t.me/{channel}/{post_id}"
        })
    return posts

# === 3. إنتاج صفحات HTML للمنشورات الفردية ===
def generate_single_post_html(post):
    title = post['text'].split('\n')[0][:70] or f"منشور رقم {post['id']}"
    file_path = os.path.join(OUTPUT_DIR, f"post-{post['id']}.html")
    
    # التعامل الآمن مع التاريخ
    date_display = post['date'][:10] if post['date'] else 'غير متاح'
    
    page_html = f"""


  
  
  {title} | قناة التلغرام
  
  


  
    ← العودة للأرشيف
    {title}
    تاريخ النشر: {date_display} | منشور #{post['id']}
    {post['html']}
    عرض المنشور في تلغرام الأصلي ���
  

"""
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(page_html)

# === 4. إنتاج صفحة الأرشيف الخفيفة (archive.html) ===
def generate_archive_html(posts):
    items_html = ""
    for post in posts:
        snippet = post['text'][:200] + "..." if len(post['text']) > 200 else post['text']
        items_html += f"""
        
          منشور #{post['id']}
          {snippet}
          قراءة المزيد →
        
        """

    archive_page = f"""


  
  
  أرشيف منشورات القناة
  

  
    ← العودة للموقع الرئيسي
    📚 أرشيف القناة كاملًا
    {items_html}
  

"""

    with open("archive.html", 'w', encoding='utf-8') as f:
        f.write(archive_page)

# === 5. توليد Sitemap.xml للجوجل ===
def generate_sitemap(posts):
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{}</loc>
    <priority>0.9</priority>
    <changefreq>weekly</changefreq>
  </url>
""".format(f"{SITE_URL}/archive.html")
    
    for p in posts:
        xml_content += f"""  <url>
    <loc>{SITE_URL}/posts/post-{p['id']}.html</loc>
    <priority>0.7</priority>
    <changefreq>monthly</changefreq>
  </url>
"""
    
    xml_content += "</urlset>"

    with open("sitemap.xml", 'w', encoding='utf-8') as f:
        f.write(xml_content)

# Execution
if __name__ == "__main__":
    posts = fetch_telegram_posts(CHANNEL_USERNAME)
    for p in posts:
        generate_single_post_html(p)
    generate_archive_html(posts)
    generate_sitemap(posts)
    print(f"Done! Processed {len(posts)} posts.")
