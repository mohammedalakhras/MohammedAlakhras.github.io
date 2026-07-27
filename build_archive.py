import os
import re
import time
import urllib.request
import math
from bs4 import BeautifulSoup

# === 1. الإعدادات العامة ===
CHANNEL_USERNAME = "MohammedAlakhras"
SITE_URL = "https://mohammedalakhras.github.io"
OUTPUT_DIR = "posts"
POSTS_PER_PAGE = 30  # عدد المنشورات لكل صفحة أرشيف (ممتاز لسعة الـ SEO والسرعة)
MAX_POSTS = 3000

os.makedirs(OUTPUT_DIR, exist_ok=True)

# بيانات افتراضية سيتم تحديثها تلقائياً من صفحة تلغرام الحقيقية
CHANNEL_METADATA = {
    "title": "محمد بن عبد المنعم الأخرس",
    "avatar": "https://telegram.org/img/t_logo.png",
    "description": "القناة الرسمية للكاتب والمهندس محمد بن عبد المنعم الأخرس على تلغرام.",
    "username": CHANNEL_USERNAME
}

# === 2. جلب القناة واستخراج البيانات والوسائط والرسائل المحولة ===
def fetch_all_telegram_posts(channel, max_posts=MAX_POSTS):
    all_posts = {}
    before_id = None
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8'
    }

    print(f"🚀 بدء سحب القناة وتحديث البيانات من تيليغرام: @{channel} ...")
    
    while len(all_posts) < max_posts:
        url = f"https://t.me/s/{channel}?before={before_id}" if before_id else f"https://t.me/s/{channel}"
            
        try:
            req = urllib.request.Request(url, headers=headers)
            html = urllib.request.urlopen(req).read().decode('utf-8')
        except Exception as e:
            print(f"⚠️ خطأ أثناء جلب الصفحة: {e}")
            break

        soup = BeautifulSoup(html, 'html.parser')

        # جلب شارة القناة، اسمها، وصورتها تلقائياً عند أول طلب
        if before_id is None:
            header_title = soup.find('div', class_='tgme_channel_info_header_title') or soup.find('div', class_='tgme_header_title')
            header_img = soup.find('img', class_='tgme_page_photo_image')
            header_desc = soup.find('div', class_='tgme_channel_info_description')
            
            if header_title and header_title.get_text().strip(): 
                CHANNEL_METADATA['title'] = header_title.get_text().strip()
            if header_img and header_img.get('src'): 
                CHANNEL_METADATA['avatar'] = header_img['src']
            if header_desc and header_desc.get_text().strip(): 
                CHANNEL_METADATA['description'] = header_desc.get_text().strip()
                
            print(f"✅ تم جلب بيانات القناة بنجاح:")
            print(f"   - العنوان: {CHANNEL_METADATA['title']}")
            print(f"   - الشعار: {CHANNEL_METADATA['avatar']}")

        messages = soup.find_all('div', class_='tgme_widget_message')
        if not messages:
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

            # 1. الرسائل المحولة (Forwarded)
            fwd_div = msg.find('div', class_='tgme_widget_message_forwarded_from')
            forwarded_info = ""
            if fwd_div:
                fwd_link = fwd_div.find('a')
                if fwd_link:
                    forwarded_info = f'<div class="forwarded-badge">↪️ إعادة توجيه من: <a href="{fwd_link.get("href", "#")}" target="_blank" rel="noopener">{fwd_link.get_text()}</a></div>'
                else:
                    forwarded_info = f'<div class="forwarded-badge">↪️ {fwd_div.get_text()}</div>'

            # 2. استخراج النص
            text_div = msg.find('div', class_='tgme_widget_message_text')
            text_content = text_div.get_text(separator="\n").strip() if text_div else ""
            html_content = text_div.decode_contents() if text_div else ""

            # 3. استخراج الصور
            photos_html = ""
            photo_wraps = msg.find_all(['a', 'div'], class_='tgme_widget_message_photo_wrap')
            for p in photo_wraps:
                style = p.get('style', '')
                img_url_match = re.search(r'background-image:\s*url\(([\'"]?)(.*?)\1\)', style)
                if img_url_match:
                    img_url = img_url_match.group(2)
                    photos_html += f'<div class="post-media"><img src="{img_url}" alt="صورة المنشور #{post_id}" loading="lazy" /></div>'

            # 4. استخراج الفيديوهات والصوتيات
            media_extra_html = ""
            video_tags = msg.find_all('video')
            for v in video_tags:
                v_src = v.get('src')
                if v_src:
                    media_extra_html += f'<div class="post-media"><video controls preload="metadata" src="{v_src}"></video></div>'

            audio_tags = msg.find_all('audio')
            for a in audio_tags:
                a_src = a.get('src')
                if a_src:
                    media_extra_html += f'<div class="post-media"><audio controls src="{a_src}"></audio></div>'

            if not text_content and not photos_html and not media_extra_html:
                continue

            time_tag = msg.find('time')
            date_str = time_tag.get('datetime')[:10] if time_tag and time_tag.get('datetime') else "غير متاح"

            # تركيب محتوى المنشور كاملاً مع تجنب أخطاء بناء النص
            full_post_html = f'{forwarded_info}{photos_html}{media_extra_html}<div class="post-text-body">{html_content}</div>'

            all_posts[post_id] = {
                'id': post_id,
                'text': text_content,
                'html': full_post_html,
                'date': date_str,
                'app_url': f"https://t.me/{channel}/{post_id}",
                'web_url': f"https://t.me/s/{channel}/{post_id}"
            }

        if not current_batch_ids:
            break

        min_id = min(current_batch_ids)
        if before_id == min_id:
            break
        before_id = min_id
        print(f"📥 تم سحب {len(all_posts)} منشور...")
        time.sleep(0.2)

    return sorted(all_posts.values(), key=lambda x: x['id'], reverse=True)

# === 3. إنتاج صفحات المنشورات الفردية ===
def generate_single_post_html(post):
    first_line = post['text'].split('\n')[0] if post['text'] else f"منشور رقم {post['id']}"
    title = first_line[:75].replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;') or f"منشور رقم {post['id']}"
    description_snippet = post['text'][:160].replace('"', '&quot;').replace('\n', ' ') if post['text'] else title
    file_path = os.path.join(OUTPUT_DIR, f"post-{post['id']}.html")
    
    page_html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | {CHANNEL_METADATA['title']}</title>
  <meta name="description" content="{description_snippet}">
  <link rel="canonical" href="{SITE_URL}/posts/post-{post['id']}.html">
  
  <!-- Open Graph & Social SEO -->
  <meta property="og:type" content="article">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description_snippet}">
  <meta property="og:image" content="{CHANNEL_METADATA['avatar']}">
  <meta property="og:url" content="{SITE_URL}/posts/post-{post['id']}.html">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{description_snippet}">
  <meta name="twitter:image" content="{CHANNEL_METADATA['avatar']}">

  <style>
    :root {{ --bg: #0f172a; --card-bg: #1e293b; --border: #334155; --text: #f8fafc; --accent: #38bdf8; --muted: #94a3b8; }}
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); padding: 20px; line-height: 1.8; margin: 0; }}
    .container {{ max-width: 820px; margin: 20px auto; }}
    
    /* Dynamic Channel Header */
    .channel-header {{ text-align: center; background: var(--card-bg); padding: 25px; border-radius: 12px; border: 1px solid var(--border); margin-bottom: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }}
    .channel-logo {{ width: 85px; height: 85px; border-radius: 50%; border: 3px solid var(--accent); margin-bottom: 12px; object-fit: cover; }}
    .channel-title {{ font-size: 1.6rem; margin: 0 0 8px 0; color: var(--text); }}
    .channel-desc {{ color: var(--muted); font-size: 0.95rem; max-width: 650px; margin: 0 auto 15px auto; line-height: 1.6; }}
    .channel-actions {{ display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; }}
    
    /* Post Box */
    .post-box {{ background: var(--card-bg); padding: 30px; border-radius: 12px; border: 1px solid var(--border); box-shadow: 0 10px 25px rgba(0,0,0,0.3); }}
    .nav-back {{ color: var(--accent); text-decoration: none; font-weight: bold; display: inline-block; margin-bottom: 20px; }}
    .nav-back:hover {{ text-decoration: underline; }}
    
    .post-meta-bar {{ display: flex; justify-content: space-between; align-items: center; padding-bottom: 15px; margin-bottom: 20px; border-bottom: 1px solid var(--border); font-size: 0.88rem; color: var(--muted); }}
    .badge {{ background: #0284c7; color: #fff; padding: 2px 8px; border-radius: 4px; font-weight: bold; }}
    
    .forwarded-badge {{ background: #1e3a8a; color: #93c5fd; padding: 8px 12px; border-radius: 6px; font-size: 0.9rem; margin-bottom: 20px; border-right: 4px solid var(--accent); }}
    .forwarded-badge a {{ color: #ffffff; font-weight: bold; text-decoration: underline; }}
    
    .post-media {{ margin: 20px 0; text-align: center; }}
    .post-media img, .post-media video {{ max-width: 100%; border-radius: 8px; max-height: 500px; border: 1px solid var(--border); }}
    .post-media audio {{ width: 100%; margin-top: 10px; }}
    
    .post-text-body {{ font-size: 1.1rem; color: #e2e8f0; white-space: pre-wrap; word-break: break-word; line-height: 1.8; }}
    
    .post-actions {{ margin-top: 35px; padding-top: 20px; border-top: 1px solid var(--border); display: flex; gap: 12px; flex-wrap: wrap; }}
    .btn {{ padding: 10px 18px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 0.9rem; transition: all 0.2s; display: inline-flex; align-items: center; gap: 6px; }}
    .btn-primary {{ background: var(--accent); color: #0f172a; }}
    .btn-secondary {{ background: #334155; color: var(--text); border: 1px solid var(--border); }}
    .btn:hover {{ opacity: 0.9; transform: translateY(-1px); }}
  </style>

  <!-- Structured Data JSON-LD for Google -->
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    "headline": "{title}",
    "description": "{description_snippet}",
    "datePublished": "{post['date']}",
    "author": {{
      "@type": "Person",
      "name": "{CHANNEL_METADATA['title']}"
    }},
    "publisher": {{
      "@type": "Organization",
      "name": "{CHANNEL_METADATA['title']}",
      "logo": {{
        "@type": "ImageObject",
        "url": "{CHANNEL_METADATA['avatar']}"
      }}
    }},
    "mainEntityOfPage": "{SITE_URL}/posts/post-{post['id']}.html"
  }}
  </script>
</head>
<body>
  <div class="container">
    <a href="../archive.html" class="nav-back">← العودة للأرشيف الرئيسي</a>
    
    <!-- Dynamic Header -->
    <header class="channel-header">
      <img src="{CHANNEL_METADATA['avatar']}" class="channel-logo" alt="{CHANNEL_METADATA['title']}">
      <h1 class="channel-title">{CHANNEL_METADATA['title']}</h1>
      <p class="channel-desc">{CHANNEL_METADATA['description']}</p>
      <div class="channel-actions">
        <a href="https://t.me/{CHANNEL_USERNAME}" target="_blank" rel="noopener" class="btn btn-primary">✈️ فتح القناة في تيليغرام</a>
        <a href="https://t.me/s/{CHANNEL_USERNAME}" target="_blank" rel="noopener" class="btn btn-secondary">👁️ معاينة القناة في الويب</a>
      </div>
    </header>

    <!-- Post Article -->
    <article class="post-box">
      <div class="post-meta-bar">
        <span>تاريخ النشر: {post['date']}</span>
        <span class="badge">منشور #{post['id']}</span>
      </div>
      
      <div class="content">{post['html']}</div>
      
      <div class="post-actions">
        <a href="{post['app_url']}" target="_blank" rel="noopener" class="btn btn-primary">✈️ مشاهدة على تيليغرام</a>
        <a href="{post['web_url']}" target="_blank" rel="noopener" class="btn btn-secondary">👁️ معاينة المنشور</a>
      </div>
    </article>
  </div>
</body>
</html>"""

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(page_html)

# === 4. إنتاج صفحات الأرشيف المجزأة (Archive Pages) ===
def generate_archive_pages(posts):
    total_posts = len(posts)
    total_pages = math.ceil(total_posts / POSTS_PER_PAGE) or 1

    for page_num in range(1, total_pages + 1):
        start_idx = (page_num - 1) * POSTS_PER_PAGE
        end_idx = start_idx + POSTS_PER_PAGE
        page_posts = posts[start_idx:end_idx]

        items_html = ""
        for post in page_posts:
            first_line = post['text'].split('\n')[0] if post['text'] else f"منشور رقم {post['id']}"
            title = first_line[:85].replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;') or f"منشور رقم {post['id']}"
            snippet = post['text'][:220].replace('<', '&lt;').replace('>', '&gt;') + "..." if len(post['text']) > 220 else post['text']

            items_html += f"""
            <article class="post-card">
              <div class="card-author">
                <img src="{CHANNEL_METADATA['avatar']}" class="card-avatar" alt="Logo">
                <div>
                  <span class="card-channel">{CHANNEL_METADATA['title']}</span>
                  <span class="card-date">{post['date']} • منشور #{post['id']}</span>
                </div>
              </div>
              <h2 class="card-title"><a href="posts/post-{post['id']}.html">{title}</a></h2>
              <p class="card-snippet">{snippet}</p>
              <div class="card-footer">
                <a href="posts/post-{post['id']}.html" class="read-btn">قراءة المقال كاملاً 📖</a>
                <div class="card-links">
                  <a href="{post['app_url']}" target="_blank" rel="noopener" class="tg-link">✈️ تيليغرام</a>
                  <a href="{post['web_url']}" target="_blank" rel="noopener" class="tg-link">👁️ معاينة</a>
                </div>
              </div>
            </article>
            """

        # روابط التصفح بين صفحات الأرشيف (Pagination)
        pagination_html = '<div class="pagination">'
        if page_num > 1:
            prev_file = "archive.html" if page_num == 2 else f"archive-page-{page_num - 1}.html"
            pagination_html += f'<a href="{prev_file}" class="page-link">السابقة ←</a>'
        
        for p in range(1, total_pages + 1):
            p_file = "archive.html" if p == 1 else f"archive-page-{p}.html"
            active_class = "active" if p == page_num else ""
            pagination_html += f'<a href="{p_file}" class="page-link {active_class}">{p}</a>'

        if page_num < total_pages:
            next_file = f"archive-page-{page_num + 1}.html"
            pagination_html += f'<a href="{next_file}" class="page-link">التالية →</a>'
        pagination_html += '</div>'

        file_name = "archive.html" if page_num == 1 else f"archive-page-{page_num}.html"

        archive_html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>أرشيف منشورات القناة (صفحة {page_num}) | {CHANNEL_METADATA['title']}</title>
  <meta name="description" content="{CHANNEL_METADATA['description']}">
  <link rel="canonical" href="{SITE_URL}/{file_name}">
  
  <meta property="og:title" content="{CHANNEL_METADATA['title']} - الأرشيف الرسمي">
  <meta property="og:description" content="{CHANNEL_METADATA['description']}">
  <meta property="og:image" content="{CHANNEL_METADATA['avatar']}">
  <meta property="og:url" content="{SITE_URL}/{file_name}">

  <style>
    :root {{ --bg: #0f172a; --card-bg: #1e293b; --border: #334155; --text: #f8fafc; --accent: #38bdf8; --muted: #94a3b8; }}
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); padding: 20px; margin: 0; line-height: 1.6; }}
    .container {{ max-width: 850px; margin: 0 auto; }}
    
    /* Channel Header */
    .channel-header {{ text-align: center; background: var(--card-bg); padding: 30px; border-radius: 12px; border: 1px solid var(--border); margin-bottom: 30px; margin-top: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }}
    .channel-logo {{ width: 95px; height: 95px; border-radius: 50%; border: 3px solid var(--accent); margin-bottom: 12px; object-fit: cover; }}
    .channel-title {{ font-size: 1.8rem; margin: 0 0 10px 0; color: var(--text); }}
    .channel-desc {{ color: var(--muted); font-size: 1rem; max-width: 650px; margin: 0 auto 18px auto; line-height: 1.6; }}
    .channel-actions {{ display: flex; justify-content: center; gap: 12px; flex-wrap: wrap; }}
    
    .btn {{ padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 0.9rem; transition: all 0.2s; display: inline-flex; align-items: center; gap: 6px; }}
    .btn-primary {{ background: var(--accent); color: #0f172a; }}
    .btn-secondary {{ background: #334155; color: var(--text); border: 1px solid var(--border); }}
    .btn:hover {{ opacity: 0.9; transform: translateY(-1px); }}

    /* Cards Style */
    .post-card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 22px; margin-bottom: 22px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
    .card-author {{ display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }}
    .card-avatar {{ width: 38px; height: 38px; border-radius: 50%; object-fit: cover; border: 1px solid var(--accent); }}
    .card-channel {{ font-weight: bold; font-size: 0.95rem; color: var(--accent); display: block; }}
    .card-date {{ font-size: 0.78rem; color: var(--muted); display: block; }}
    .card-title {{ margin: 0 0 10px 0; font-size: 1.25rem; line-height: 1.4; }}
    .card-title a {{ color: var(--text); text-decoration: none; }}
    .card-title a:hover {{ color: var(--accent); text-decoration: underline; }}
    .card-snippet {{ color: #cbd5e1; font-size: 0.95rem; line-height: 1.6; margin-bottom: 15px; white-space: pre-wrap; }}
    
    .card-footer {{ display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 14px; flex-wrap: wrap; gap: 10px; }}
    .read-btn {{ color: var(--accent); text-decoration: none; font-weight: bold; font-size: 0.92rem; }}
    .read-btn:hover {{ text-decoration: underline; }}
    .card-links {{ display: flex; gap: 12px; }}
    .tg-link {{ color: var(--muted); text-decoration: none; font-size: 0.85rem; }}
    .tg-link:hover {{ color: var(--text); }}

    /* Pagination */
    .pagination {{ display: flex; justify-content: center; gap: 8px; margin: 40px 0; flex-wrap: wrap; }}
    .page-link {{ background: var(--card-bg); color: var(--text); padding: 8px 14px; border-radius: 6px; text-decoration: none; border: 1px solid var(--border); font-size: 0.9rem; }}
    .page-link.active {{ background: var(--accent); color: #0f172a; font-weight: bold; border-color: var(--accent); }}
  </style>
</head>
<body>
  <div class="container">
    <a href="index.html" style="color: var(--accent); text-decoration: none; font-weight: bold;">← العودة للموقع الرئيسي</a>
    
    <header class="channel-header">
      <img src="{CHANNEL_METADATA['avatar']}" class="channel-logo" alt="{CHANNEL_METADATA['title']}">
      <h1 class="channel-title">{CHANNEL_METADATA['title']}</h1>
      <p class="channel-desc">{CHANNEL_METADATA['description']}</p>
      <div class="channel-actions">
        <a href="https://t.me/{CHANNEL_USERNAME}" target="_blank" rel="noopener" class="btn btn-primary">✈️ فتح القناة في تيليغرام</a>
        <a href="https://t.me/s/{CHANNEL_USERNAME}" target="_blank" rel="noopener" class="btn btn-secondary">👁️ معاينة القناة في الويب</a>
      </div>
    </header>

    <main>
      {items_html}
    </main>

    {pagination_html}
  </div>
</body>
</html>"""

        with open(file_name, 'w', encoding='utf-8') as f:
            f.write(archive_html)

# === 5. إنشاء خريطة الموقع Sitemap ===
def generate_sitemap(posts):
    xml_entries = [
        f"  <url>\n    <loc>{SITE_URL}/archive.html</loc>\n    <priority>1.0</priority>\n    <changefreq>daily</changefreq>\n  </url>"
    ]
    for p in posts:
        xml_entries.append(f"  <url>\n    <loc>{SITE_URL}/posts/post-{p['id']}.html</loc>\n    <priority>0.8</priority>\n  </url>")
    
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(xml_entries) + '\n</urlset>'
    with open("sitemap.xml", 'w', encoding='utf-8') as f:
        f.write(xml_content)

# === 6. التشغيل التنفيذي ===
if __name__ == "__main__":
    posts = fetch_all_telegram_posts(CHANNEL_USERNAME)
    print(f"⚙️ جاري توليد {len(posts)} صفحة منشورات وصفحات الأرشيف المتكاملة...")
    
    for p in posts:
        generate_single_post_html(p)
        
    generate_archive_pages(posts)
    generate_sitemap(posts)
    print("✨ اكتمل البناء وتحديث كافة الصفحات بنجاح وبأعلى معايير الـ SEO!")