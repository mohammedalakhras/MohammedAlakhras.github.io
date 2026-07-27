import os
import re
import time
import urllib.request
import json
from bs4 import BeautifulSoup

# === 1. الإعدادات العامة ===
CHANNEL_USERNAME = "MohammedAlakhras"  # اسم القناة
SITE_URL = "https://mohammedalakhras.github.io" # رابط موقعك
OUTPUT_DIR = "posts"
MAX_POSTS = 2500  # حد أقصى للبحث لجلب جميع المنشورات (2000+)

os.makedirs(OUTPUT_DIR, exist_ok=True)

# === 2. جلب كافة المنشورات عبر التكرار الخلفي (Pagination Loop) ===
def fetch_all_telegram_posts(channel, max_posts=MAX_POSTS):
    all_posts = {}
    before_id = None
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8'
    }

    print(f"🚀 بدء سحب كافة منشورات القناة: @{channel} ...")
    
    while len(all_posts) < max_posts:
        if before_id:
            url = f"https://t.me/s/{channel}?before={before_id}"
        else:
            url = f"https://t.me/s/{channel}"
            
        try:
            req = urllib.request.Request(url, headers=headers)
            html = urllib.request.urlopen(req).read().decode('utf-8')
        except Exception as e:
            print(f"⚠️ خطأ أثناء جلب الصفحة: {e}")
            break

        soup = BeautifulSoup(html, 'html.parser')
        messages = soup.find_all('div', class_='tgme_widget_message')
        
        if not messages:
            print("✅ تم الوصول إلى أول منشور في القناة!")
            break

        current_batch_ids = []

        for msg in messages:
            post_id_raw = msg.get('data-post')
            if not post_id_raw:
                continue
            
            post_id = int(post_id_raw.split('/')[-1])
            current_batch_ids.append(post_id)

            if post_id in all_posts:
                continue

            text_div = msg.find('div', class_='tgme_widget_message_text')
            text_content = text_div.get_text(separator="\n").strip() if text_div else ""
            html_content = text_div.decode_contents() if text_div else ""

            if not text_content and not html_content:
                continue # يتجاوز المنشورات الفارغة تماماً

            time_tag = msg.find('time')
            date_str = time_tag.get('datetime') if time_tag else ""

            all_posts[post_id] = {
                'id': post_id,
                'text': text_content,
                'html': html_content,
                'date': date_str[:10] if date_str else "غير متاح",
                'url': f"https://t.me/{channel}/{post_id}"
            }

        if not current_batch_ids:
            break

        min_id_in_batch = min(current_batch_ids)
        if before_id == min_id_in_batch:
            break
            
        before_id = min_id_in_batch
        print(f"📥 تم سحب {len(all_posts)} منشور حتى الآن... (جاري جلب المنشورات قبل #{before_id})")
        time.sleep(0.3) # مهلة بسيطة لتجنب الحظر

    # ترتيب المنشورات من الأحدث للأقدم
    sorted_posts = sorted(all_posts.values(), key=lambda x: x['id'], reverse=True)
    return sorted_posts

# === 3. إنتاج صفحات HTML المستقلة للمنشورات الفردية ===
def generate_single_post_html(post):
    first_line = post['text'].split('\n')[0] if post['text'] else f"منشور رقم {post['id']}"
    title = first_line[:70].replace('<', '&lt;').replace('>', '&gt;') or f"منشور رقم {post['id']}"
    file_path = os.path.join(OUTPUT_DIR, f"post-{post['id']}.html")
    
    page_html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | محمد بن عبد المنعم الأخرس</title>
  <meta name="description" content="{post['text'][:150].replace('"', '')}">
  <link rel="canonical" href="{SITE_URL}/posts/post-{post['id']}.html">
  <style>
    :root {{ --bg: #0f172a; --card-bg: #1e293b; --border: #334155; --text: #f8fafc; --accent: #38bdf8; --muted: #94a3b8; }}
    body {{ font-family: system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--text); padding: 20px; line-height: 1.8; margin: 0; }}
    .container {{ max-width: 800px; margin: 40px auto; background: var(--card-bg); padding: 30px; border-radius: 12px; border: 1px solid var(--border); box-shadow: 0 10px 25px rgba(0,0,0,0.3); }}
    .nav-back {{ color: var(--accent); text-decoration: none; font-weight: bold; display: inline-block; margin-bottom: 20px; }}
    .nav-back:hover {{ text-decoration: underline; }}
    h1 {{ font-size: 1.5rem; color: var(--accent); margin-top: 0; border-bottom: 1px solid var(--border); padding-bottom: 15px; }}
    .meta {{ font-size: 0.85rem; color: var(--muted); margin-bottom: 25px; display: flex; gap: 15px; flex-wrap: wrap; }}
    .badge {{ background: #0284c7; color: #fff; padding: 2px 8px; border-radius: 4px; font-weight: bold; }}
    .content {{ font-size: 1.1rem; color: #e2e8f0; white-space: pre-wrap; word-break: break-word; }}
    .actions {{ margin-top: 35px; padding-top: 20px; border-top: 1px solid var(--border); display: flex; gap: 15px; flex-wrap: wrap; }}
    .btn {{ background: var(--accent); color: #0f172a; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; transition: all 0.2s; }}
    .btn:hover {{ opacity: 0.9; transform: translateY(-2px); }}
  </style>
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    "headline": "{title}",
    "articleBody": "{post['text'][:300].replace('"', '')}",
    "datePublished": "{post['date']}",
    "author": {{
      "@type": "Person",
      "name": "محمد بن عبد المنعم الأخرس"
    }},
    "mainEntityOfPage": "{SITE_URL}/posts/post-{post['id']}.html"
  }}
  </script>
</head>
<body>
  <div class="container">
    <a href="../archive.html" class="nav-back">← العودة لأرشيف القناة</a>
    <h1>{title}</h1>
    <div class="meta">
      <span>تاريخ النشر: {post['date']}</span>
      <span class="badge">منشور #{post['id']}</span>
    </div>
    <div class="content">{post['html']}</div>
    <div class="actions">
      <a href="{post['url']}" target="_blank" class="btn">✈️ مشاهدة المنشور في تيليغرام</a>
    </div>
  </div>
</body>
</html>"""
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(page_html)

# === 4. إنتاج صفحة الأرشيف الشاملة والمعروضة بالكامل (archive.html) ===
def generate_archive_html(posts):
    items_html = ""
    for post in posts:
        first_line = post['text'].split('\n')[0] if post['text'] else f"منشور رقم {post['id']}"
        title = first_line[:80].replace('<', '&lt;').replace('>', '&gt;') or f"منشور رقم {post['id']}"
        
        items_html += f"""
        <article class="post-card">
          <div class="post-header">
            <h2><a href="posts/post-{post['id']}.html">{title}</a></h2>
            <span class="post-badge">#{post['id']}</span>
          </div>
          <div class="post-meta">تاريخ النشر: {post['date']}</div>
          <div class="post-body">{post['html']}</div>
          <div class="post-footer">
            <a href="{post['url']}" target="_blank" class="tg-btn">✈️ مشاهدة على تيليغرام</a>
            <a href="posts/post-{post['id']}.html" class="link-btn">رابط الصفحة الدائمة 🔗</a>
          </div>
        </article>
        """

    archive_page = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>أرشيف منشورات قناة التيليغرام | محمد بن عبد المنعم الأخرس</title>
  <meta name="description" content="أرشيف كامل لجميع منشورات ومقالات القناة الرسمية للكاتب والمهندس محمد بن عبد المنعم الأخرس على تلغرام.">
  <style>
    :root {{ --bg: #0f172a; --card-bg: #1e293b; --border: #334155; --text: #f8fafc; --accent: #38bdf8; --muted: #94a3b8; }}
    body {{ font-family: system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--text); padding: 20px; line-height: 1.8; margin: 0; }}
    .container {{ max-width: 850px; margin: 0 auto; }}
    header {{ text-align: center; padding: 40px 0; border-bottom: 1px solid var(--border); margin-bottom: 30px; }}
    h1 {{ color: var(--accent); margin-bottom: 10px; font-size: 2rem; }}
    p.subtitle {{ color: var(--muted); font-size: 1.1rem; margin-top: 0; }}
    .nav-home {{ display: inline-block; color: var(--accent); text-decoration: none; margin-bottom: 20px; font-weight: bold; }}
    
    .post-card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 25px; margin-bottom: 30px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
    .post-header {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 15px; margin-bottom: 10px; }}
    .post-header h2 {{ margin: 0; font-size: 1.3rem; line-height: 1.4; }}
    .post-header h2 a {{ color: var(--accent); text-decoration: none; }}
    .post-header h2 a:hover {{ text-decoration: underline; }}
    .post-badge {{ background: #0284c7; color: #fff; padding: 3px 10px; border-radius: 6px; font-size: 0.8rem; font-weight: bold; white-space: nowrap; }}
    .post-meta {{ font-size: 0.85rem; color: var(--muted); margin-bottom: 20px; }}
    .post-body {{ font-size: 1.05rem; color: #e2e8f0; white-space: pre-wrap; word-break: break-word; line-height: 1.8; }}
    
    .post-footer {{ margin-top: 20px; padding-top: 15px; border-top: 1px solid var(--border); display: flex; gap: 15px; flex-wrap: wrap; align-items: center; }}
    .tg-btn {{ background: #0284c7; color: #fff; padding: 8px 18px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 0.9rem; }}
    .tg-btn:hover {{ background: #0369a1; }}
    .link-btn {{ color: var(--accent); text-decoration: none; font-size: 0.9rem; }}
    .link-btn:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="container">
    <a href="index.html" class="nav-home">← العودة للموقع الرئيسي</a>
    <header>
      <h1>📚 أرشيف منشورات القناة كاملاً</h1>
      <p class="subtitle">تغطية وشاملة لجميع الفوائد والمنشورات من قناة التلغرام الرسمية</p>
    </header>
    
    <main>
      {items_html}
    </main>
  </div>
</body>
</html>"""

    with open("archive.html", 'w', encoding='utf-8') as f:
        f.write(archive_page)

# === 5. توليد Sitemap.xml للجوجل ===
def generate_sitemap(posts):
    xml_entries = [
        f"  <url>\n    <loc>{SITE_URL}/archive.html</loc>\n    <priority>1.0</priority>\n    <changefreq>daily</changefreq>\n  </url>"
    ]
    
    for p in posts:
        xml_entries.append(
            f"  <url>\n    <loc>{SITE_URL}/posts/post-{p['id']}.html</loc>\n    <priority>0.8</priority>\n    <changefreq>monthly</changefreq>\n  </url>"
        )
    
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(xml_entries) + '\n</urlset>'

    with open("sitemap.xml", 'w', encoding='utf-8') as f:
        f.write(xml_content)

# === 6. نقطة الانطلاق ===
if __name__ == "__main__":
    posts = fetch_all_telegram_posts(CHANNEL_USERNAME)
    print(f"⚙️ جاري توليد {len(posts)} صفحة HTML مع التنسيقات والخريطة...")
    
    for p in posts:
        generate_single_post_html(p)
        
    generate_archive_html(posts)
    generate_sitemap(posts)
    print("✨ تم كل شيء بنجاح!")