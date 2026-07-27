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
POSTS_PER_PAGE = 30  # عدد المنشورات في كل صفحة أرشيف (ممتاز للـ SEO وسرعة التحميل)
MAX_POSTS = 3000

os.makedirs(OUTPUT_DIR, exist_ok=True)

CHANNEL_METADATA = {
    "title": "محمد بن عبد المنعم الأخرس",
    "avatar": "https://telegram.org/img/t_logo.png",
    "description": "القناة الرسمية للكاتب والمهندس محمد بن عبد المنعم الأخرس على تلغرام.",
    "username": CHANNEL_USERNAME
}

# === 2. جلب وتفكيك كافة منشورات القناة ===
def fetch_all_telegram_posts(channel, max_posts=MAX_POSTS):
    all_posts = {}
    before_id = None
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8'
    }

    print(f"🚀 بدء سحب القناة ومعالجة الوسائط والرسائل المحولة: @{channel} ...")
    
    while len(all_posts) < max_posts:
        url = f"https://t.me/s/{channel}?before={before_id}" if before_id else f"https://t.me/s/{channel}"
            
        try:
            req = urllib.request.Request(url, headers=headers)
            html = urllib.request.urlopen(req).read().decode('utf-8')
        except Exception as e:
            print(f"⚠️ خطأ أثناء جلب الصفحة: {e}")
            break

        soup = BeautifulSoup(html, 'html.parser')

        # جلب بيانات القناة لأول مرة
        if before_id is None:
            header_title = soup.find('div', class_='tgme_header_title')
            header_img = soup.find('img', class_='tgme_page_photo_image')
            header_desc = soup.find('div', class_='tgme_channel_info_description')
            
            if header_title: CHANNEL_METADATA['title'] = header_title.get_text().strip()
            if header_img and header_img.get('src'): CHANNEL_METADATA['avatar'] = header_img['src']
            if header_desc: CHANNEL_METADATA['description'] = header_desc.get_text().strip()

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
                    forwarded_info = f'<div class="forwarded-badge">↪️ إعادة توجيه من: <a href="{fwd_link.get("href", "#")}" target="_blank">{fwd_link.get_text()}</a></div>'
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
                continue # تجديد المتجاوزات الفارغة

            time_tag = msg.find('time')
            date_str = time_tag.get('datetime')[:10] if time_tag and time_tag.get('datetime') else "غير متاح"

            # تركيب محتوى المنشور كاملاً
            full_post_html = f"{forwarded_info}{photos_html}{media_extra_html}<div class="post-text-body">{html_content}</div>"

            all_posts[post_id] = {
                'id': post_id,
                'text': text_content,
                'html': full_post_html,
                'date': date_str,
                'url': f"https://t.me/{channel}/{post_id}"
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

# === 3. إنشاء صفحات المنشورات الفردية ===
def generate_single_post_html(post):
    first_line = post['text'].split('\n')[0] if post['text'] else f"منشور رقم {post['id']}"
    title = first_line[:75].replace('<', '&lt;').replace('>', '&gt;') or f"منشور رقم {post['id']}"
    file_path = os.path.join(OUTPUT_DIR, f"post-{post['id']}.html")
    
    page_html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | {CHANNEL_METADATA['title']}</title>
  <meta name="description" content="{post['text'][:150].replace('"', '')}">
  <link rel="canonical" href="{SITE_URL}/posts/post-{post['id']}.html">
  <style>
    :root {{ --bg: #0f172a; --card-bg: #1e293b; --border: #334155; --text: #f8fafc; --accent: #38bdf8; --muted: #94a3b8; }}
    body {{ font-family: system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--text); padding: 20px; line-height: 1.8; margin: 0; }}
    .container {{ max-width: 800px; margin: 30px auto; background: var(--card-bg); padding: 30px; border-radius: 12px; border: 1px solid var(--border); box-shadow: 0 10px 25px rgba(0,0,0,0.3); }}
    .nav-back {{ color: var(--accent); text-decoration: none; font-weight: bold; display: inline-block; margin-bottom: 20px; }}
    .author-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid var(--border); }}
    .author-avatar {{ width: 48px; height: 48px; border-radius: 50%; object-fit: cover; border: 2px solid var(--accent); }}
    .author-name {{ font-weight: bold; font-size: 1.1rem; color: var(--text); }}
    .author-sub {{ font-size: 0.85rem; color: var(--muted); }}
    .forwarded-badge {{ background: #1e3a8a; color: #93c5fd; padding: 8px 12px; border-radius: 6px; font-size: 0.9rem; margin-bottom: 15px; border-right: 4px solid var(--accent); }}
    .forwarded-badge a {{ color: #ffffff; font-weight: bold; }}
    .post-media {{ margin: 15px 0; text-align: center; }}
    .post-media img, .post-media video {{ max-width: 100%; border-radius: 8px; max-height: 500px; border: 1px solid var(--border); }}
    .post-media audio {{ width: 100%; margin-top: 10px; }}
    .post-text-body {{ font-size: 1.1rem; color: #e2e8f0; white-space: pre-wrap; word-break: break-word; }}
    .actions {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid var(--border); display: flex; gap: 15px; }}
    .btn {{ background: var(--accent); color: #0f172a; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: bold; }}
  </style>
</head>
<body>
  <div class="container">
    <a href="../archive.html" class="nav-back">← العودة للأرشيف</a>
    <div class="author-header">
      <img src="{CHANNEL_METADATA['avatar']}" class="author-avatar" alt="Logo">
      <div>
        <div class="author-name">{CHANNEL_METADATA['title']}</div>
        <div class="author-sub">تاريخ النشر: {post['date']} • منشور #{post['id']}</div>
      </div>
    </div>
    <div class="content">{post['html']}</div>
    <div class="actions">
      <a href="{post['url']}" target="_blank" class="btn">✈️ فتح في تطبيق تيليغرام</a>
    </div>
  </div>
</body>
</html>"""
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(page_html)

# === 4. إنشاء صفحات الأرشيف المجزأة (Paginated Archive) ===
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
            title = first_line[:80].replace('<', '&lt;').replace('>', '&gt;') or f"منشور رقم {post['id']}"
            snippet = post['text'][:220].replace('<', '&lt;').replace('>', '&gt;') + "..." if len(post['text']) > 220 else post['text']

            items_html += f"""
            <article class="post-card">
              <div class="card-author">
                <img src="{CHANNEL_METADATA['avatar']}" class="card-avatar" alt="Avatar">
                <div>
                  <span class="card-channel">{CHANNEL_METADATA['title']}</span>
                  <span class="card-date">{post['date']} • #{post['id']}</span>
                </div>
              </div>
              <h2 class="card-title"><a href="posts/post-{post['id']}.html">{title}</a></h2>
              <p class="card-snippet">{snippet}</p>
              <div class="card-footer">
                <a href="posts/post-{post['id']}.html" class="read-btn">قراءة المقال كاملاً 📖</a>
                <a href="{post['url']}" target="_blank" class="tg-link">تيليغرام ✈️</a>
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
  <title>أرشيف المنشورات (صفحة {page_num}) | {CHANNEL_METADATA['title']}</title>
  <meta name="description" content="{CHANNEL_METADATA['description']}">
  <style>
    :root {{ --bg: #0f172a; --card-bg: #1e293b; --border: #334155; --text: #f8fafc; --accent: #38bdf8; --muted: #94a3b8; }}
    body {{ font-family: system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--text); padding: 20px; margin: 0; line-height: 1.6; }}
    .container {{ max-width: 850px; margin: 0 auto; }}
    
    /* Header Style */
    .channel-header {{ text-align: center; background: var(--card-bg); padding: 30px; border-radius: 12px; border: 1px solid var(--border); margin-bottom: 30px; margin-top: 20px; }}
    .channel-logo {{ width: 90px; height: 90px; border-radius: 50%; border: 3px solid var(--accent); margin-bottom: 15px; object-fit: cover; }}
    .channel-title {{ font-size: 1.8rem; margin: 0 0 10px 0; color: var(--text); }}
    .channel-desc {{ color: var(--muted); font-size: 1rem; max-width: 600px; margin: 0 auto 15px auto; }}
    .channel-badge {{ display: inline-block; background: #0284c7; color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: bold; text-decoration: none; }}

    /* Cards Style */
    .post-card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 20px; }}
    .card-author {{ display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }}
    .card-avatar {{ width: 36px; height: 36px; border-radius: 50%; object-fit: cover; }}
    .card-channel {{ font-weight: bold; font-size: 0.95rem; color: var(--accent); display: block; }}
    .card-date {{ font-size: 0.75rem; color: var(--muted); display: block; }}
    .card-title {{ margin: 0 0 10px 0; font-size: 1.2rem; }}
    .card-title a {{ color: var(--text); text-decoration: none; }}
    .card-title a:hover {{ color: var(--accent); }}
    .card-snippet {{ color: #cbd5e1; font-size: 0.95rem; line-height: 1.6; margin-bottom: 15px; white-space: pre-wrap; }}
    
    .card-footer {{ display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 12px; }}
    .read-btn {{ color: var(--accent); text-decoration: none; font-weight: bold; font-size: 0.9rem; }}
    .tg-link {{ color: var(--muted); text-decoration: none; font-size: 0.85rem; }}

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
      <a href="https://t.me/{CHANNEL_USERNAME}" target="_blank" class="channel-badge">متابعة القناة على تيليغرام ✈️</a>
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

# === 5. خريطة الموقع Sitemap ===
def generate_sitemap(posts):
    xml_entries = [
        f"  <url>\n    <loc>{SITE_URL}/archive.html</loc>\n    <priority>1.0</priority>\n    <changefreq>daily</changefreq>\n  </url>"
    ]
    for p in posts:
        xml_entries.append(f"  <url>\n    <loc>{SITE_URL}/posts/post-{p['id']}.html</loc>\n    <priority>0.8</priority>\n  </url>")
    
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(xml_entries) + '\n</urlset>'
    with open("sitemap.xml", 'w', encoding='utf-8') as f:
        f.write(xml_content)

# === 6. التشغيل الرئيسي ===
if __name__ == "__main__":
    posts = fetch_all_telegram_posts(CHANNEL_USERNAME)
    print(f"⚙️ جاري توليد {len(posts)} صفحة منشورات وصفحات الأرشيف المجزأة...")
    
    for p in posts:
        generate_single_post_html(p)
        
    generate_archive_pages(posts)
    generate_sitemap(posts)
    print("✨ تم رفع الأرشيف وتحديث الموقع بنجاح أقصى وسرعة قياسية!")