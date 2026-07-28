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
POSTS_PER_PAGE = 30  # عدد المنشورات لكل صفحة أرشيف
MAX_POSTS = 3000

os.makedirs(OUTPUT_DIR, exist_ok=True)

# بيانات افتراضية سيتم تحديثها تلقائياً من صفحة تلغرام الحقيقية
CHANNEL_METADATA = {
    "title": "محمد بن عبد المنعم الأخرس",
    "avatar": "https://telegram.org/img/t_logo.png",
    "description": "القناة الرسمية للكاتب والمهندس محمد بن عبد المنعم الأخرس على تلغرام.",
    "username": CHANNEL_USERNAME
}

def get_page_filename(page_num):
    """دالة لحديد اسم الملف بناءً على رقم الصفحة (الصفحة 1 تكون index.html)"""
    return "index.html" if page_num == 1 else f"archive-page-{page_num}.html"

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

        # استخراج صورة القناة الحقيقية وعنوانها ووصفها عند أول طلب
        if before_id is None:
            meta_og_img = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'twitter:image'})
            if meta_og_img and meta_og_img.get('content') and 't_logo' not in meta_og_img['content']:
                CHANNEL_METADATA['avatar'] = meta_og_img['content']
            else:
                photo_elem = soup.find(class_=re.compile(r'tgme_page_photo_image|tgme_page_photo'))
                if photo_elem:
                    img_tag = photo_elem.find('img')
                    if img_tag and img_tag.get('src'):
                        CHANNEL_METADATA['avatar'] = img_tag['src']
                    else:
                        style_str = photo_elem.get('style', '')
                        bg_match = re.search(r'background-image:\s*url\s*\(\s*[\'"]?([^\'")]+)[\'"]?\s*\)', style_str, re.IGNORECASE)
                        if bg_match:
                            CHANNEL_METADATA['avatar'] = bg_match.group(1)

            header_title = soup.find('div', class_='tgme_channel_info_header_title') or soup.find('div', class_='tgme_header_title') or soup.find('span', class_='tgme_channel_info_header_title')
            header_desc = soup.find('div', class_='tgme_channel_info_description')
            
            if header_title and header_title.get_text().strip(): 
                CHANNEL_METADATA['title'] = header_title.get_text().strip()
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

            # 3. استخراج الصور المرفقة
            photos_html = ""
            seen_photos = set()

            def is_valid_photo_url(url):
                if not url:
                    return False
                url_lower = url.lower()
                invalid_keywords = ['t_logo', 'emoji', 'reaction', 'sticker', 'avatar', 'user_photo', 'icon']
                return not any(kw in url_lower for kw in invalid_keywords)

            photo_wraps = msg.find_all(class_=re.compile(r'tgme_widget_message_photo'))
            for p in photo_wraps:
                if p.find_parent(class_=re.compile(r'tgme_widget_message_reactions|tgme_widget_message_text|tgme_widget_message_user_photo|tgme_widget_message_author')):
                    continue

                style = p.get('style', '')
                img_match = re.search(r'background-image:\s*url\s*\(\s*[\'"]?([^\'")]+)[\'"]?\s*\)', style, re.IGNORECASE)
                if img_match:
                    img_url = img_match.group(1)
                    if img_url not in seen_photos and is_valid_photo_url(img_url):
                        seen_photos.add(img_url)
                        photos_html += f'<div class="post-media"><img src="{img_url}" alt="صورة المنشور #{post_id}" loading="lazy" /></div>'

                for img_tag in p.find_all('img'):
                    img_classes = ' '.join(img_tag.get('class', []))
                    if 'emoji' in img_classes or 'reaction' in img_classes:
                        continue
                    src = img_tag.get('src') or img_tag.get('data-src')
                    if src and src not in seen_photos and is_valid_photo_url(src):
                        seen_photos.add(src)
                        photos_html += f'<div class="post-media"><img src="{src}" alt="صورة المنشور #{post_id}" loading="lazy" /></div>'

            # 4. استخراج الفيديوهات والتسجيلات الصوتية
            media_extra_html = ""
            seen_videos = set()
            
            video_tags = msg.find_all('video')
            for v in video_tags:
                v_src = v.get('src') or (v.find('source').get('src') if v.find('source') else None)
                v_poster = v.get('poster', '')
                if v_src and v_src not in seen_videos:
                    seen_videos.add(v_src)
                    poster_attr = f' poster="{v_poster}"' if v_poster else ''
                    media_extra_html += f'<div class="post-media"><video controls preload="metadata"{poster_attr} src="{v_src}"></video></div>'

            if not seen_videos:
                video_players = msg.find_all(class_=re.compile(r'tgme_widget_message_video|tgme_widget_message_roundvideo'))
                for vp in video_players:
                    v_src = vp.get('src') or vp.get('data-src')
                    if v_src and v_src not in seen_videos:
                        seen_videos.add(v_src)
                        media_extra_html += f'<div class="post-media"><video controls preload="metadata" src="{v_src}"></video></div>'

            seen_audios = set()
            audio_tags = msg.find_all('audio')
            for a in audio_tags:
                a_src = a.get('src') or (a.find('source').get('src') if a.find('source') else None) or a.get('data-src')
                if a_src and a_src not in seen_audios:
                    seen_audios.add(a_src)
                    media_extra_html += f'<div class="post-media"><audio controls src="{a_src}"></audio></div>'

            if not seen_audios:
                voice_elems = msg.find_all(class_=re.compile(r'tgme_widget_message_voice|tgme_widget_message_audio'))
                for ve in voice_elems:
                    a_src = ve.get('src') or ve.get('data-src') or ve.get('href')
                    if a_src and a_src not in seen_audios and ('.ogg' in a_src or '.mp3' in a_src or 'voice' in a_src):
                        seen_audios.add(a_src)
                        media_extra_html += f'<div class="post-media"><audio controls src="{a_src}"></audio></div>'

            if not text_content and not photos_html and not media_extra_html:
                continue

            time_tag = msg.find('time')
            date_str = time_tag.get('datetime')[:10] if time_tag and time_tag.get('datetime') else "غير متاح"

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
  <meta property="og:site_name" content="{CHANNEL_METADATA['title']}">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description_snippet}">
  <meta property="og:image" content="{CHANNEL_METADATA['avatar']}">
  <meta property="og:url" content="{SITE_URL}/posts/post-{post['id']}.html">
  <meta property="og:locale" content="ar_SA">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{description_snippet}">
  <meta name="twitter:image" content="{CHANNEL_METADATA['avatar']}">

  <style>
    :root {{ --bg: #0f172a; --card-bg: #1e293b; --border: #334155; --text: #f8fafc; --accent: #38bdf8; --muted: #94a3b8; }}
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); padding: 20px; line-height: 1.8; margin: 0; }}
    .container {{ max-width: 820px; margin: 20px auto; }}
    
    /* Channel Header */
    .channel-header {{ text-align: center; background: var(--card-bg); padding: 25px; border-radius: 12px; border: 1px solid var(--border); margin-bottom: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }}
    .channel-logo {{ width: 90px; height: 90px; border-radius: 50%; border: 3px solid var(--accent); margin-bottom: 12px; object-fit: cover; }}
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
    .post-media img, .post-media video {{ max-width: 100%; border-radius: 8px; max-height: 550px; border: 1px solid var(--border); object-fit: contain; }}
    .post-media audio {{ width: 100%; margin-top: 10px; }}
    
    .post-text-body {{ font-size: 1.1rem; color: #e2e8f0; white-space: pre-wrap; word-break: break-word; line-height: 1.8; }}
    .post-text-body a {{ color: var(--accent); text-decoration: underline; }}
    
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
    <a href="../index.html" class="nav-back">← العودة للصفحة الرئيسية</a>
    
    <header class="channel-header">
      <img src="{CHANNEL_METADATA['avatar']}" class="channel-logo" alt="{CHANNEL_METADATA['title']}">
      <h1 class="channel-title">{CHANNEL_METADATA['title']}</h1>
      <p class="channel-desc">{CHANNEL_METADATA['description']}</p>
      <div class="channel-actions">
        <a href="https://t.me/{CHANNEL_USERNAME}" target="_blank" rel="noopener" class="btn btn-primary">✈️ فتح القناة في تيليغرام</a>
        <a href="https://t.me/s/{CHANNEL_USERNAME}" target="_blank" rel="noopener" class="btn btn-secondary">👁️ معاينة القناة في الويب</a>
      </div>
    </header>

    <article class="post-box">
      <div class="post-meta-bar">
        <span>تاريخ النشر: <time datetime="{post['date']}">{post['date']}</time></span>
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

# === 4. إنتاج صفحات الأرشيف المجزأة (index.html و archive-page-X.html) ===
def generate_archive_pages(posts):
    total_posts = len(posts)
    total_pages = math.ceil(total_posts / POSTS_PER_PAGE) or 1

    for page_num in range(1, total_pages + 1):
        start_idx = (page_num - 1) * POSTS_PER_PAGE
        end_idx = start_idx + POSTS_PER_PAGE
        page_posts = posts[start_idx:end_idx]

        items_html = ""
        items_json_ld = []

        for idx, post in enumerate(page_posts):
            first_line = post['text'].split('\n')[0] if post['text'] else f"منشور رقم {post['id']}"
            title = first_line[:85].replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;') or f"منشور رقم {post['id']}"

            items_json_ld.append(f"""
            {{
              "@type": "ListItem",
              "position": {idx + 1},
              "url": "{SITE_URL}/posts/post-{post['id']}.html",
              "name": "{title}"
            }}""")

            items_html += f"""
            <article class="post-card">
              <div class="card-author">
                <img src="{CHANNEL_METADATA['avatar']}" class="card-avatar" alt="{CHANNEL_METADATA['title']}" loading="lazy">
                <div>
                  <span class="card-channel">{CHANNEL_METADATA['title']}</span>
                  <time datetime="{post['date']}" class="card-date">{post['date']} • منشور #{post['id']}</time>
                </div>
              </div>
              
              <h2 class="card-title"><a href="posts/post-{post['id']}.html">{title}</a></h2>
              
              <div class="card-full-content">
                {post['html']}
              </div>
              
              <div class="card-footer">
                <a href="posts/post-{post['id']}.html" class="read-btn">رابط المقال المستقل 🔗</a>
                <div class="card-links">
                  <a href="{post['app_url']}" target="_blank" rel="noopener" class="tg-link">✈️ تيليغرام</a>
                  <a href="{post['web_url']}" target="_blank" rel="noopener" class="tg-link">👁️ معاينة</a>
                </div>
              </div>
            </article>
            """

        # روابط التصفح بين صفحات الأرشيف (Pagination)
        pagination_html = '<nav class="pagination" aria-label="صفحات الأرشيف">'
        if page_num > 1:
            prev_file = get_page_filename(page_num - 1)
            pagination_html += f'<a href="{prev_file}" class="page-link" rel="prev">السابقة ←</a>'
        
        for p in range(1, total_pages + 1):
            p_file = get_page_filename(p)
            active_class = "active" if p == page_num else ""
            pagination_html += f'<a href="{p_file}" class="page-link {active_class}">{p}</a>'

        if page_num < total_pages:
            next_file = get_page_filename(page_num + 1)
            pagination_html += f'<a href="{next_file}" class="page-link" rel="next">التالية →</a>'
        pagination_html += '</nav>'

        file_name = get_page_filename(page_num)

        # إشارات العلاقة بين الصفحات المترابطة للـ SEO
        rel_links = ""
        if page_num > 1:
            prev_href = get_page_filename(page_num - 1)
            rel_links += f'\n  <link rel="prev" href="{SITE_URL}/{prev_href}">'
        if page_num < total_pages:
            next_href = get_page_filename(page_num + 1)
            rel_links += f'\n  <link rel="next" href="{SITE_URL}/{next_href}">'

        json_ld_elements_str = ",".join(items_json_ld)

        archive_html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{CHANNEL_METADATA['title']} - الصفحة الرئيسية (صفحة {page_num})</title>
  <meta name="description" content="{CHANNEL_METADATA['description']}">
  <link rel="canonical" href="{SITE_URL}/{file_name}">{rel_links}
  
  <!-- Open Graph & Social SEO -->
  <meta property="og:site_name" content="{CHANNEL_METADATA['title']}">
  <meta property="og:type" content="website">
  <meta property="og:title" content="{CHANNEL_METADATA['title']} - الأرشيف الرسمي (صفحة {page_num})">
  <meta property="og:description" content="{CHANNEL_METADATA['description']}">
  <meta property="og:image" content="{CHANNEL_METADATA['avatar']}">
  <meta property="og:url" content="{SITE_URL}/{file_name}">
  <meta property="og:locale" content="ar_SA">

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
    .post-card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 25px; margin-bottom: 25px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
    .card-author {{ display: flex; align-items: center; gap: 12px; margin-bottom: 15px; }}
    .card-avatar {{ width: 42px; height: 42px; border-radius: 50%; object-fit: cover; border: 1px solid var(--accent); }}
    .card-channel {{ font-weight: bold; font-size: 0.95rem; color: var(--accent); display: block; }}
    .card-date {{ font-size: 0.8rem; color: var(--muted); display: block; }}
    .card-title {{ margin: 0 0 15px 0; font-size: 1.3rem; line-height: 1.4; }}
    .card-title a {{ color: var(--text); text-decoration: none; }}
    .card-title a:hover {{ color: var(--accent); text-decoration: underline; }}
    
    /* Full Content Inside Card */
    .card-full-content {{ font-size: 1.05rem; color: #e2e8f0; line-height: 1.8; margin-bottom: 20px; word-break: break-word; }}
    .card-full-content a {{ color: var(--accent); text-decoration: underline; }}
    .forwarded-badge {{ background: #1e3a8a; color: #93c5fd; padding: 8px 12px; border-radius: 6px; font-size: 0.9rem; margin-bottom: 15px; border-right: 4px solid var(--accent); }}
    .forwarded-badge a {{ color: #ffffff; font-weight: bold; text-decoration: underline; }}
    
    .post-media {{ margin: 15px 0; text-align: center; }}
    .post-media img, .post-media video {{ max-width: 100%; border-radius: 8px; max-height: 500px; border: 1px solid var(--border); object-fit: contain; }}
    .post-media audio {{ width: 100%; margin-top: 10px; }}
    .post-text-body {{ white-space: pre-wrap; }}

    .card-footer {{ display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 15px; flex-wrap: wrap; gap: 10px; }}
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

  <!-- Structured Data JSON-LD for Google Archive -->
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "ItemList",
    "itemListElement": [{json_ld_elements_str}]
  }}
  </script>
</head>
<body>
  <div class="container">
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
            
    return total_pages

# === 5. إنشاء خريطة الموقع Sitemap وملف Robots.txt ===
def generate_sitemap_and_robots(posts, total_pages):
    xml_entries = [
        f"  <url>\n    <loc>{SITE_URL}/</loc>\n    <priority>1.0</priority>\n    <changefreq>daily</changefreq>\n  </url>"
    ]
    
    # إضافة صفحات الأرشيف المجزأة في Sitemap
    for p in range(2, total_pages + 1):
        xml_entries.append(f"  <url>\n    <loc>{SITE_URL}/archive-page-{p}.html</loc>\n    <priority>0.8</priority>\n    <changefreq>weekly</changefreq>\n  </url>")

    # إضافة صفحات المنشورات
    for p in posts:
        xml_entries.append(f"  <url>\n    <loc>{SITE_URL}/posts/post-{p['id']}.html</loc>\n    <lastmod>{p['date']}</lastmod>\n    <priority>0.7</priority>\n  </url>")
    
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(xml_entries) + '\n</urlset>'
    with open("sitemap.xml", 'w', encoding='utf-8') as f:
        f.write(xml_content)

    robots_content = f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n"
    with open("robots.txt", 'w', encoding='utf-8') as f:
        f.write(robots_content)

# === 6. التشغيل التنفيذي ===
if __name__ == "__main__":
    posts = fetch_all_telegram_posts(CHANNEL_USERNAME)
    print(f"⚙️ جاري توليد {len(posts)} صفحة منشورات وصفحات الأرشيف المتكاملة...")
    
    for p in posts:
        generate_single_post_html(p)
        
    total_pages = generate_archive_pages(posts)
    generate_sitemap_and_robots(posts, total_pages)
    print(f"✨ اكتمل البناء وتحديث كافة الصفحات بنجاح ({total_pages} صفحة رئيسية وأرشيف)!")