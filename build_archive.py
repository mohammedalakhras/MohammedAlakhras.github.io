import os
import re
import sys
import time
import json
import html as html_lib
import urllib.request
import math
from datetime import datetime
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

# === 1. الإعدادات العامة ===
CHANNEL_USERNAME = "MohammedAlakhras"
SITE_URL = "https://mohammedalakhras.github.io"
OUTPUT_DIR = "posts"
POSTS_PER_PAGE = 30          # عدد المنشورات لكل صفحة أرشيف
MAX_POSTS = 3000             # الحد الأقصى للمنشورات المسحوبة
MIN_INDEXABLE_TEXT_LEN = 80  # الحد الأدنى لطول النص (بالأحرف) لاعتبار المنشور صالحاً للفهرسة في محركات البحث
EXCERPT_MAX_LEN = 320        # طول المقتطف المعروض في بطاقات الأرشيف لمنع تكرار المحتوى (Duplicate Content)
PERMANENT_AVATAR = "https://avatars.githubusercontent.com/u/31374510"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# بيانات القناة (يتم استخدام الصورة الدائمة كاحتياطي أساسي لتجنب انتهاء صلاحية روابط CDN المؤقتة لتيليغرام)
CHANNEL_METADATA = {
    "title": "محمد بن عبد المنعم الأخرس",
    "avatar": PERMANENT_AVATAR,
    "description": "الأرشيف الرسمي لخواطر ومنشورات المهندس والباحث محمد عبد المنعم الأخرس على تيليغرام.",
    "username": CHANNEL_USERNAME
}


def get_page_filename(page_num):
    """تحديد اسم ملف صفحة الأرشيف بناءً على رقم الصفحة (الصفحة 1 تكون archive.html)"""
    return "archive.html" if page_num == 1 else f"archive-page-{page_num}.html"


def get_file_lastmod(filepath, fallback_date):
    """قراءة تاريخ التعديل الفعلي للملف بدلاً من تزوير تاريخ اليوم في خريطة الموقع"""
    try:
        if os.path.exists(filepath):
            mtime = os.path.getmtime(filepath)
            return datetime.utcfromtimestamp(mtime).strftime('%Y-%m-%d')
    except Exception:
        pass
    return fallback_date


def clean_whitespace(text):
    """تنظيف المسافات والأسطر الزائدة لاستخراج نصوص وعناوين سليمة"""
    return re.sub(r'\s+', ' ', text or '').strip()


def safe_json_ld(data_obj):
    """تحويل كائن البيانات المهيكلة إلى JSON-LD صالح 100% ومحصّن ضد كسر وسم script"""
    raw_json = json.dumps(data_obj, ensure_ascii=False, indent=2)
    return raw_json.replace("</", "<\\/")


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
            raw_html = urllib.request.urlopen(req, timeout=20).read().decode('utf-8')
        except Exception as e:
            print(f"⚠️ خطأ أثناء جلب الصفحة ({url}): {e}")
            break

        soup = BeautifulSoup(raw_html, 'html.parser')

        # استخراج عنوان القناة ووصفها عند أول طلب
        if before_id is None:
            header_title = (
                soup.find('div', class_='tgme_channel_info_header_title')
                or soup.find('div', class_='tgme_header_title')
                or soup.find('span', class_='tgme_channel_info_header_title')
            )
            header_desc = soup.find('div', class_='tgme_channel_info_description')

            if header_title and header_title.get_text().strip():
                CHANNEL_METADATA['title'] = clean_whitespace(header_title.get_text())
            if header_desc and header_desc.get_text().strip():
                CHANNEL_METADATA['description'] = clean_whitespace(header_desc.get_text())

            print("✅ تم جلب بيانات القناة بنجاح:")
            print(f"   - العنوان: {CHANNEL_METADATA['title']}")
            print(f"   - الشعار الدائم: {CHANNEL_METADATA['avatar']}")

        messages = soup.find_all('div', class_='tgme_widget_message')
        if not messages:
            break

        current_batch_ids = []

        for msg in messages:
            post_id_raw = msg.get('data-post')
            if not post_id_raw:
                continue

            try:
                post_id = int(post_id_raw.split('/')[-1])
            except ValueError:
                continue

            current_batch_ids.append(post_id)

            if post_id in all_posts:
                continue

            # 1. الرسائل المحولة (Forwarded)
            fwd_div = msg.find('div', class_='tgme_widget_message_forwarded_from')
            forwarded_info = ""
            if fwd_div:
                fwd_link = fwd_div.find('a')
                if fwd_link:
                    fwd_href = fwd_link.get("href", "#")
                    if fwd_href.startswith('/'):
                        fwd_href = f"https://t.me{fwd_href}"
                    fwd_name = html_lib.escape(clean_whitespace(fwd_link.get_text()))
                    forwarded_info = (
                        f'<div class="forwarded-badge">↪️ إعادة توجيه من: '
                        f'<a href="{html_lib.escape(fwd_href, quote=True)}" target="_blank" rel="noopener">{fwd_name}</a></div>'
                    )
                else:
                    fwd_text = html_lib.escape(clean_whitespace(fwd_div.get_text()))
                    forwarded_info = f'<div class="forwarded-badge">↪️ {fwd_text}</div>'

            # 2. استخراج النص وإصلاح الروابط النسبية (مثل الهاشتاغات ?q=%23...)
            text_div = msg.find('div', class_='tgme_widget_message_text')
            text_content = text_div.get_text(separator="\n").strip() if text_div else ""
            if text_div:
                for a_tag in text_div.find_all('a'):
                    href = a_tag.get('href', '')
                    if href.startswith('?'):
                        a_tag['href'] = f"https://t.me/s/{channel}{href}"
                    elif href.startswith('/'):
                        a_tag['href'] = f"https://t.me{href}"
                    a_tag['target'] = '_blank'
                    a_tag['rel'] = 'noopener noreferrer'
            html_content = text_div.decode_contents() if text_div else ""

            # 3. استخراج الصور المرفقة (مع معالجة انتهاء صلاحية روابط CDN المؤقتة عبر onerror)
            photos_html = ""
            seen_photos = set()

            def is_valid_photo_url(u):
                if not u:
                    return False
                u_lower = u.lower()
                invalid_keywords = ['t_logo', 'emoji', 'reaction', 'sticker', 'avatar', 'user_photo', 'icon']
                return not any(kw in u_lower for kw in invalid_keywords)

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
                        safe_img_url = html_lib.escape(img_url, quote=True)
                        photos_html += (
                            f'<div class="post-media">'
                            f'<img src="{safe_img_url}" alt="صورة المنشور #{post_id}" loading="lazy" '
                            f'onerror="this.parentElement.style.display=\'none\'" /></div>'
                        )

                for img_tag in p.find_all('img'):
                    img_classes = ' '.join(img_tag.get('class', []))
                    if 'emoji' in img_classes or 'reaction' in img_classes:
                        continue
                    src = img_tag.get('src') or img_tag.get('data-src')
                    if src and src not in seen_photos and is_valid_photo_url(src):
                        seen_photos.add(src)
                        safe_src = html_lib.escape(src, quote=True)
                        photos_html += (
                            f'<div class="post-media">'
                            f'<img src="{safe_src}" alt="صورة المنشور #{post_id}" loading="lazy" '
                            f'onerror="this.parentElement.style.display=\'none\'" /></div>'
                        )

            # 4. استخراج الفيديوهات والتسجيلات الصوتية
            media_extra_html = ""
            seen_videos = set()

            video_tags = msg.find_all('video')
            for v in video_tags:
                v_src = v.get('src') or (v.find('source').get('src') if v.find('source') else None)
                v_poster = v.get('poster', '')
                if v_src and v_src not in seen_videos:
                    seen_videos.add(v_src)
                    safe_v_src = html_lib.escape(v_src, quote=True)
                    poster_attr = f' poster="{html_lib.escape(v_poster, quote=True)}"' if v_poster else ''
                    media_extra_html += f'<div class="post-media"><video controls preload="metadata"{poster_attr} src="{safe_v_src}"></video></div>'

            if not seen_videos:
                video_players = msg.find_all(class_=re.compile(r'tgme_widget_message_video|tgme_widget_message_roundvideo'))
                for vp in video_players:
                    v_src = vp.get('src') or vp.get('data-src')
                    if v_src and v_src not in seen_videos:
                        seen_videos.add(v_src)
                        safe_v_src = html_lib.escape(v_src, quote=True)
                        media_extra_html += f'<div class="post-media"><video controls preload="metadata" src="{safe_v_src}"></video></div>'

            seen_audios = set()
            audio_tags = msg.find_all('audio')
            for a in audio_tags:
                a_src = a.get('src') or (a.find('source').get('src') if a.find('source') else None) or a.get('data-src')
                if a_src and a_src not in seen_audios:
                    seen_audios.add(a_src)
                    safe_a_src = html_lib.escape(a_src, quote=True)
                    media_extra_html += f'<div class="post-media"><audio controls src="{safe_a_src}"></audio></div>'

            if not seen_audios:
                voice_elems = msg.find_all(class_=re.compile(r'tgme_widget_message_voice|tgme_widget_message_audio'))
                for ve in voice_elems:
                    a_src = ve.get('src') or ve.get('data-src') or ve.get('href')
                    if a_src and a_src not in seen_audios and ('.ogg' in a_src or '.mp3' in a_src or 'voice' in a_src):
                        seen_audios.add(a_src)
                        safe_a_src = html_lib.escape(a_src, quote=True)
                        media_extra_html += f'<div class="post-media"><audio controls src="{safe_a_src}"></audio></div>'

            if not text_content and not photos_html and not media_extra_html:
                continue

            time_tag = msg.find('time')
            date_str = (
                time_tag.get('datetime')[:10]
                if time_tag and time_tag.get('datetime')
                else time.strftime('%Y-%m-%d')
            )

            text_body_div = f'<div class="post-text-body">{html_content}</div>' if html_content else ''
            full_post_html = f'{forwarded_info}{photos_html}{media_extra_html}{text_body_div}'

            clean_text = clean_whitespace(text_content)
            is_indexable = len(clean_text) >= MIN_INDEXABLE_TEXT_LEN

            all_posts[post_id] = {
                'id': post_id,
                'text': text_content,
                'clean_text': clean_text,
                'html': full_post_html,
                'media_html': f'{forwarded_info}{photos_html}{media_extra_html}',
                'date': date_str,
                'is_indexable': is_indexable,
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


def extract_post_title_and_desc(post):
    """استخراج عنوان ووصف نظيفين للمنشور مع ضمان عدم تطابقهما حرفياً"""
    lines = [clean_whitespace(line) for line in post['text'].split('\n') if clean_whitespace(line)]
    raw_first_line = lines[0] if lines else f"منشور رقم {post['id']} - {CHANNEL_METADATA['title']}"
    raw_title = raw_first_line[:75].strip() or f"منشور رقم {post['id']}"

    if post['clean_text'] and len(post['clean_text']) > len(raw_title):
        raw_desc = post['clean_text'][:160].strip()
    elif post['clean_text']:
        raw_desc = f"{post['clean_text']} — من أرشيف {CHANNEL_METADATA['title']} (منشور #{post['id']})."
    else:
        raw_desc = f"منشور وسائط رقم #{post['id']} بتاريخ {post['date']} من قناة {CHANNEL_METADATA['title']}."

    return raw_title, raw_desc


# === 3. إنتاج صفحات المنشورات الفردية ===
def generate_single_post_html(post):
    raw_title, raw_desc = extract_post_title_and_desc(post)
    safe_title = html_lib.escape(raw_title, quote=True)
    safe_desc = html_lib.escape(raw_desc, quote=True)
    safe_channel_title = html_lib.escape(CHANNEL_METADATA['title'], quote=True)
    safe_channel_desc = html_lib.escape(CHANNEL_METADATA['description'], quote=True)
    safe_avatar = html_lib.escape(CHANNEL_METADATA['avatar'], quote=True)

    # حماية الـ SEO: فهرسة المنشورات النصية الغنية فقط، واستثناء المنشورات القصيرة جداً من الفهرسة
    robots_directive = "index, follow" if post['is_indexable'] else "noindex, follow"
    post_url = f"{SITE_URL}/posts/post-{post['id']}.html"

    json_ld_obj = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": raw_title,
        "description": raw_desc,
        "datePublished": post['date'],
        "dateModified": post['date'],
        "inLanguage": "ar",
        "author": {
            "@type": "Person",
            "name": "محمد عبد المنعم الأخرس",
            "url": f"{SITE_URL}/ar.html"
        },
        "publisher": {
            "@type": "Person",
            "name": CHANNEL_METADATA['title'],
            "image": CHANNEL_METADATA['avatar']
        },
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": post_url
        }
    }
    json_ld_str = safe_json_ld(json_ld_obj)

    file_path = os.path.join(OUTPUT_DIR, f"post-{post['id']}.html")

    page_html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_title} | {safe_channel_title}</title>
  <meta name="description" content="{safe_desc}">
  <meta name="robots" content="{robots_directive}">
  <link rel="canonical" href="{post_url}">

  <!-- Google Fonts: Cairo -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">

  <!-- Open Graph & Social SEO -->
  <meta property="og:site_name" content="{safe_channel_title}">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{safe_title}">
  <meta property="og:description" content="{safe_desc}">
  <meta property="og:image" content="{safe_avatar}">
  <meta property="og:url" content="{post_url}">
  <meta property="og:locale" content="ar_SA">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{safe_title}">
  <meta name="twitter:description" content="{safe_desc}">
  <meta name="twitter:image" content="{safe_avatar}">

  <style>
    :root {{ --bg: #0f172a; --card-bg: #1e293b; --border: #334155; --text: #f8fafc; --accent: #38bdf8; --muted: #94a3b8; }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: 'Cairo', system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); padding: 20px; line-height: 1.85; margin: 0; }}
    .container {{ max-width: 820px; margin: 15px auto 40px; }}

    /* Top Navigation Bar */
    .top-nav {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; padding-bottom: 14px; border-bottom: 1px solid var(--border); }}
    .nav-link {{ color: var(--accent); text-decoration: none; font-weight: 700; font-size: 0.95rem; display: inline-flex; align-items: center; gap: 6px; }}
    .nav-link:hover {{ text-decoration: underline; }}

    /* Channel Header */
    .channel-header {{ text-align: center; background: var(--card-bg); padding: 25px; border-radius: 12px; border: 1px solid var(--border); margin-bottom: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }}
    .channel-logo {{ width: 88px; height: 88px; border-radius: 50%; border: 3px solid var(--accent); margin-bottom: 10px; object-fit: cover; }}
    .channel-title {{ font-size: 1.5rem; margin: 0 0 8px 0; color: var(--text); }}
    .channel-desc {{ color: var(--muted); font-size: 0.95rem; max-width: 650px; margin: 0 auto 15px auto; line-height: 1.6; }}
    .channel-actions {{ display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; }}

    /* Post Box */
    .post-box {{ background: var(--card-bg); padding: 30px; border-radius: 12px; border: 1px solid var(--border); box-shadow: 0 10px 25px rgba(0,0,0,0.3); }}
    .post-title {{ font-size: 1.35rem; color: var(--text); margin: 0 0 18px 0; line-height: 1.5; }}
    .post-meta-bar {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; padding-bottom: 15px; margin-bottom: 20px; border-bottom: 1px solid var(--border); font-size: 0.88rem; color: var(--muted); }}
    .badge {{ background: #0284c7; color: #fff; padding: 3px 10px; border-radius: 6px; font-weight: 700; }}

    .forwarded-badge {{ background: #1e3a8a; color: #93c5fd; padding: 8px 12px; border-radius: 6px; font-size: 0.9rem; margin-bottom: 20px; border-right: 4px solid var(--accent); }}
    .forwarded-badge a {{ color: #ffffff; font-weight: 700; text-decoration: underline; }}

    .post-media {{ margin: 20px 0; text-align: center; }}
    .post-media img, .post-media video {{ max-width: 100%; border-radius: 8px; max-height: 550px; border: 1px solid var(--border); object-fit: contain; }}
    .post-media audio {{ width: 100%; margin-top: 10px; }}

    .post-text-body {{ font-size: 1.1rem; color: #e2e8f0; white-space: pre-wrap; word-break: break-word; line-height: 1.9; }}
    .post-text-body a {{ color: var(--accent); text-decoration: underline; }}

    .post-actions {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid var(--border); display: flex; gap: 12px; flex-wrap: wrap; }}
    .btn {{ padding: 9px 18px; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 0.9rem; transition: all 0.2s; display: inline-flex; align-items: center; gap: 6px; }}
    .btn-primary {{ background: var(--accent); color: #0f172a; }}
    .btn-secondary {{ background: #334155; color: var(--text); border: 1px solid var(--border); }}
    .btn:hover {{ opacity: 0.92; transform: translateY(-1px); }}

    @media (max-width: 600px) {{
      body {{ padding: 12px; }}
      .post-box {{ padding: 20px; }}
      .post-title {{ font-size: 1.15rem; }}
      .post-text-body {{ font-size: 1rem; }}
    }}
  </style>

  <!-- Structured Data JSON-LD -->
  <script type="application/ld+json">
{json_ld_str}
  </script>
</head>
<body>
  <div class="container">
    <nav class="top-nav" aria-label="التنقل العلوي">
      <a href="../archive.html" class="nav-link">→ العودة إلى أرشيف المنشورات</a>
      <a href="../ar.html" class="nav-link">🏠 الصفحة الرئيسية (محمد الأخرس)</a>
    </nav>

    <header class="channel-header">
      <img src="{safe_avatar}" class="channel-logo" alt="{safe_channel_title}" onerror="this.onerror=null;this.src='{PERMANENT_AVATAR}';">
      <p class="channel-title"><strong>{safe_channel_title}</strong></p>
      <p class="channel-desc">{safe_channel_desc}</p>
      <div class="channel-actions">
        <a href="https://t.me/{CHANNEL_USERNAME}" target="_blank" rel="noopener" class="btn btn-primary">✈️ فتح القناة في تيليغرام</a>
        <a href="../archive.html" class="btn btn-secondary">📚 تصفح جميع المنشورات</a>
      </div>
    </header>

    <article class="post-box">
      <div class="post-meta-bar">
        <span>تاريخ النشر: <time datetime="{post['date']}">{post['date']}</time></span>
        <span class="badge">منشور #{post['id']}</span>
      </div>

      <h1 class="post-title">{safe_title}</h1>

      <div class="content">{post['html']}</div>

      <div class="post-actions">
        <a href="{post['app_url']}" target="_blank" rel="noopener" class="btn btn-primary">✈️ فتح في تطبيق تيليغرام</a>
        <a href="{post['web_url']}" target="_blank" rel="noopener" class="btn btn-secondary">👁️ المصدر على تيليغرام ويب</a>
      </div>
    </article>
  </div>
</body>
</html>"""

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(page_html)


def build_smart_pagination(page_num, total_pages):
    """إنشاء شريط ترقيم ذكي ومختصر بدلاً من طباعة 56 زراً متراصاً في كل صفحة"""
    pagination_html = '<nav class="pagination" aria-label="صفحات الأرشيف">'

    if page_num > 1:
        prev_file = get_page_filename(page_num - 1)
        pagination_html += f'<a href="{prev_file}" class="page-link" rel="prev">→ السابقة</a>'

    # تحديد أرقام الصفحات المعروضة: الأولى، الأخيرة، ونافذة حول الصفحة الحالية
    pages_to_show = sorted(set(
        [1, total_pages] +
        [p for p in range(max(1, page_num - 2), min(total_pages, page_num + 2) + 1)]
    ))

    last_p = 0
    for p in pages_to_show:
        if last_p and p - last_p > 1:
            pagination_html += '<span class="page-ellipsis">…</span>'
        p_file = get_page_filename(p)
        active_class = "active" if p == page_num else ""
        aria_current = ' aria-current="page"' if p == page_num else ''
        pagination_html += f'<a href="{p_file}" class="page-link {active_class}"{aria_current}>{p}</a>'
        last_p = p

    if page_num < total_pages:
        next_file = get_page_filename(page_num + 1)
        pagination_html += f'<a href="{next_file}" class="page-link" rel="next">التالية ←</a>'

    pagination_html += '</nav>'
    return pagination_html


# === 4. إنتاج صفحات الأرشيف المجزأة (archive.html و archive-page-X.html) ===
def generate_archive_pages(posts):
    total_posts = len(posts)
    total_pages = math.ceil(total_posts / POSTS_PER_PAGE) or 1
    safe_channel_title = html_lib.escape(CHANNEL_METADATA['title'], quote=True)
    safe_channel_desc = html_lib.escape(CHANNEL_METADATA['description'], quote=True)
    safe_avatar = html_lib.escape(CHANNEL_METADATA['avatar'], quote=True)

    for page_num in range(1, total_pages + 1):
        start_idx = (page_num - 1) * POSTS_PER_PAGE
        end_idx = start_idx + POSTS_PER_PAGE
        page_posts = posts[start_idx:end_idx]

        items_html = ""
        item_list_elements = []

        for idx, post in enumerate(page_posts):
            raw_title, _ = extract_post_title_and_desc(post)
            safe_title = html_lib.escape(raw_title, quote=True)
            post_rel_url = f"posts/post-{post['id']}.html"
            post_full_url = f"{SITE_URL}/{post_rel_url}"

            item_list_elements.append({
                "@type": "ListItem",
                "position": idx + 1,
                "url": post_full_url,
                "name": raw_title
            })

            # عرض مقتطف ذكي للمنشورات الطويلة في الأرشيف لمنع تطابق المحتوى 100% مع صفحات المنشورات الفردية
            if len(post['clean_text']) > EXCERPT_MAX_LEN:
                excerpt_text = html_lib.escape(post['clean_text'][:EXCERPT_MAX_LEN].rsplit(' ', 1)[0]) + " …"
                card_body_html = (
                    f'{post["media_html"]}'
                    f'<div class="post-text-body">{excerpt_text}</div>'
                    f'<div class="read-more-wrap"><a href="{post_rel_url}" class="read-more-inline">قراءة النص الكامل ←</a></div>'
                )
            else:
                card_body_html = post['html']

            items_html += f"""
            <article class="post-card">
              <div class="card-author">
                <img src="{safe_avatar}" class="card-avatar" alt="{safe_channel_title}" loading="lazy" onerror="this.onerror=null;this.src='{PERMANENT_AVATAR}';">
                <div>
                  <span class="card-channel">{safe_channel_title}</span>
                  <time datetime="{post['date']}" class="card-date">{post['date']} • منشور #{post['id']}</time>
                </div>
              </div>

              <h2 class="card-title"><a href="{post_rel_url}">{safe_title}</a></h2>

              <div class="card-full-content">
                {card_body_html}
              </div>

              <div class="card-footer">
                <a href="{post_rel_url}" class="read-btn">صفحة المنشور المستقلة 🔗</a>
                <div class="card-links">
                  <a href="{post['app_url']}" target="_blank" rel="noopener" class="tg-link">✈️ تيليغرام</a>
                  <a href="{post['web_url']}" target="_blank" rel="noopener" class="tg-link">👁️ المصدر</a>
                </div>
              </div>
            </article>
            """

        pagination_html = build_smart_pagination(page_num, total_pages)
        file_name = get_page_filename(page_num)

        # إشارات العلاقة بين الصفحات المترابطة
        rel_links = ""
        if page_num > 1:
            prev_href = get_page_filename(page_num - 1)
            rel_links += f'\n  <link rel="prev" href="{SITE_URL}/{prev_href}">'
        if page_num < total_pages:
            next_href = get_page_filename(page_num + 1)
            rel_links += f'\n  <link rel="next" href="{SITE_URL}/{next_href}">'

        # فهرسة الصفحة الأولى للأرشيف، واستثناء صفحات الترقيم الفرعية من الفهرسة المباشرة لمنع إهدار ميزانية الزحف
        archive_robots = "index, follow" if page_num == 1 else "noindex, follow"
        page_title = (
            f"الخواطر والمنشورات | {CHANNEL_METADATA['title']}"
            if page_num == 1
            else f"أرشيف المنشورات (صفحة {page_num} من {total_pages}) | {CHANNEL_METADATA['title']}"
        )
        page_desc = (
            f"{CHANNEL_METADATA['description']} — تصفح أحدث المقالات والخواطر والمنشورات."
            if page_num == 1
            else f"صفحة {page_num} من أرشيف منشورات وخواطر {CHANNEL_METADATA['title']}."
        )

        safe_page_title = html_lib.escape(page_title, quote=True)
        safe_page_desc = html_lib.escape(page_desc, quote=True)

        archive_json_ld = safe_json_ld({
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": page_title,
            "itemListElement": item_list_elements
        })

        archive_html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_page_title}</title>
  <meta name="description" content="{safe_page_desc}">
  <meta name="robots" content="{archive_robots}">
  <link rel="canonical" href="{SITE_URL}/{file_name}">{rel_links}

  <!-- Google Fonts: Cairo -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">

  <!-- Open Graph & Social SEO -->
  <meta property="og:site_name" content="{safe_channel_title}">
  <meta property="og:type" content="website">
  <meta property="og:title" content="{safe_page_title}">
  <meta property="og:description" content="{safe_page_desc}">
  <meta property="og:image" content="{safe_avatar}">
  <meta property="og:url" content="{SITE_URL}/{file_name}">
  <meta property="og:locale" content="ar_SA">

  <style>
    :root {{ --bg: #0f172a; --card-bg: #1e293b; --border: #334155; --text: #f8fafc; --accent: #38bdf8; --muted: #94a3b8; }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: 'Cairo', system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); padding: 20px; margin: 0; line-height: 1.75; }}
    .container {{ max-width: 850px; margin: 0 auto 40px; }}

    /* Top Navigation Bar */
    .top-nav {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; padding: 12px 0 16px; margin-bottom: 20px; border-bottom: 1px solid var(--border); }}
    .nav-link {{ color: var(--accent); text-decoration: none; font-weight: 700; font-size: 0.95rem; }}
    .nav-link:hover {{ text-decoration: underline; }}

    /* Channel Header */
    .channel-header {{ text-align: center; background: var(--card-bg); padding: 30px 24px; border-radius: 12px; border: 1px solid var(--border); margin-bottom: 30px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }}
    .channel-logo {{ width: 92px; height: 92px; border-radius: 50%; border: 3px solid var(--accent); margin-bottom: 12px; object-fit: cover; }}
    .channel-title {{ font-size: 1.75rem; margin: 0 0 10px 0; color: var(--text); }}
    .channel-desc {{ color: var(--muted); font-size: 1rem; max-width: 650px; margin: 0 auto 18px auto; line-height: 1.65; }}
    .channel-actions {{ display: flex; justify-content: center; gap: 12px; flex-wrap: wrap; }}

    .btn {{ padding: 9px 20px; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 0.9rem; transition: all 0.2s; display: inline-flex; align-items: center; gap: 6px; }}
    .btn-primary {{ background: var(--accent); color: #0f172a; }}
    .btn-secondary {{ background: #334155; color: var(--text); border: 1px solid var(--border); }}
    .btn:hover {{ opacity: 0.92; transform: translateY(-1px); }}

    /* Cards Style */
    .post-card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 24px; margin-bottom: 22px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.12); transition: border-color 0.2s; }}
    .post-card:hover {{ border-color: rgba(56, 189, 248, 0.45); }}
    .card-author {{ display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }}
    .card-avatar {{ width: 42px; height: 42px; border-radius: 50%; object-fit: cover; border: 1px solid var(--accent); }}
    .card-channel {{ font-weight: 700; font-size: 0.95rem; color: var(--accent); display: block; }}
    .card-date {{ font-size: 0.8rem; color: var(--muted); display: block; }}
    .card-title {{ margin: 0 0 12px 0; font-size: 1.25rem; line-height: 1.45; }}
    .card-title a {{ color: var(--text); text-decoration: none; }}
    .card-title a:hover {{ color: var(--accent); text-decoration: underline; }}

    .card-full-content {{ font-size: 1.03rem; color: #e2e8f0; line-height: 1.85; margin-bottom: 18px; word-break: break-word; }}
    .card-full-content a {{ color: var(--accent); text-decoration: underline; }}
    .forwarded-badge {{ background: #1e3a8a; color: #93c5fd; padding: 8px 12px; border-radius: 6px; font-size: 0.9rem; margin-bottom: 15px; border-right: 4px solid var(--accent); }}
    .forwarded-badge a {{ color: #ffffff; font-weight: 700; text-decoration: underline; }}

    .post-media {{ margin: 15px 0; text-align: center; }}
    .post-media img, .post-media video {{ max-width: 100%; border-radius: 8px; max-height: 500px; border: 1px solid var(--border); object-fit: contain; }}
    .post-media audio {{ width: 100%; margin-top: 10px; }}
    .post-text-body {{ white-space: pre-wrap; }}
    .read-more-wrap {{ margin-top: 10px; }}
    .read-more-inline {{ color: var(--accent); font-weight: 700; text-decoration: none; font-size: 0.92rem; }}
    .read-more-inline:hover {{ text-decoration: underline; }}

    .card-footer {{ display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 14px; flex-wrap: wrap; gap: 10px; }}
    .read-btn {{ color: var(--accent); text-decoration: none; font-weight: 700; font-size: 0.92rem; }}
    .read-btn:hover {{ text-decoration: underline; }}
    .card-links {{ display: flex; gap: 12px; }}
    .tg-link {{ color: var(--muted); text-decoration: none; font-size: 0.85rem; }}
    .tg-link:hover {{ color: var(--text); }}

    /* Smart Pagination */
    .pagination {{ display: flex; justify-content: center; align-items: center; gap: 8px; margin: 36px 0; flex-wrap: wrap; }}
    .page-link {{ background: var(--card-bg); color: var(--text); padding: 8px 14px; border-radius: 8px; text-decoration: none; border: 1px solid var(--border); font-size: 0.9rem; transition: all 0.2s; }}
    .page-link:hover {{ border-color: var(--accent); color: var(--accent); }}
    .page-link.active {{ background: var(--accent); color: #0f172a; font-weight: 700; border-color: var(--accent); }}
    .page-ellipsis {{ color: var(--muted); padding: 0 6px; font-weight: 700; }}

    @media (max-width: 600px) {{
      body {{ padding: 12px; }}
      .post-card {{ padding: 18px; }}
      .channel-title {{ font-size: 1.4rem; }}
    }}
  </style>

  <!-- Structured Data JSON-LD -->
  <script type="application/ld+json">
{archive_json_ld}
  </script>
</head>
<body>
  <div class="container">
    <nav class="top-nav" aria-label="التنقل العلوي">
      <a href="ar.html" class="nav-link">→ الصفحة الرئيسية (محمد الأخرس)</a>
      <a href="index.html" class="nav-link" hreflang="en">English Portfolio</a>
    </nav>

    <header class="channel-header">
      <img src="{safe_avatar}" class="channel-logo" alt="{safe_channel_title}" onerror="this.onerror=null;this.src='{PERMANENT_AVATAR}';">
      <h1 class="channel-title">{safe_channel_title}</h1>
      <p class="channel-desc">{safe_channel_desc}</p>
      <div class="channel-actions">
        <a href="https://t.me/{CHANNEL_USERNAME}" target="_blank" rel="noopener" class="btn btn-primary">✈️ متابعة القناة على تيليغرام</a>
        <a href="ar.html" class="btn btn-secondary">👤 السيرة الذاتية والمشاريع</a>
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


# === 5. إنشاء خرائط الموقع (sitemap-main.xml + sitemap.xml + sitemap.txt) وملف robots.txt ===
def generate_sitemap_and_robots(posts, total_pages):
    today = time.strftime('%Y-%m-%d')
    latest_post_date = posts[0]['date'] if posts else today

    # قراءة تاريخ التعديل الحقيقي لصفحتي الـ Portfolio بدلاً من تزوير تاريخ اليوم
    index_lastmod = get_file_lastmod("index.html", today)
    ar_lastmod = get_file_lastmod("ar.html", today)

    # تصفية المنشورات لتضمين المنشورات الغنية القابلة للفهرسة فقط في خريطة الموقع
    indexable_posts = [p for p in posts if p['is_indexable']]

    SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
    XHTML_NS = "http://www.w3.org/1999/xhtml"
    ET.register_namespace('', SITEMAP_NS)
    ET.register_namespace('xhtml', XHTML_NS)

    def add_url_entry(parent_elem, loc_url, lastmod_date, hreflang_dict=None):
        url_elem = ET.SubElement(parent_elem, f"{{{SITEMAP_NS}}}url")
        loc_elem = ET.SubElement(url_elem, f"{{{SITEMAP_NS}}}loc")
        loc_elem.text = loc_url
        lastmod_elem = ET.SubElement(url_elem, f"{{{SITEMAP_NS}}}lastmod")
        lastmod_elem.text = lastmod_date
        if hreflang_dict:
            for lang_code, target_url in hreflang_dict.items():
                ET.SubElement(url_elem, f"{{{XHTML_NS}}}link", {
                    "rel": "alternate", "hreflang": lang_code, "href": target_url
                })

    hreflangs_main = {
        "en": f"{SITE_URL}/",
        "ar": f"{SITE_URL}/ar.html",
        "x-default": f"{SITE_URL}/"
    }

    # 1) توليد sitemap-main.xml (خريطة مصغرة وسريعة لصفحات الـ Portfolio الأساسية فقط)
    main_urlset = ET.Element(f"{{{SITEMAP_NS}}}urlset")
    add_url_entry(main_urlset, f"{SITE_URL}/", index_lastmod, hreflang_dict=hreflangs_main)
    add_url_entry(main_urlset, f"{SITE_URL}/ar.html", ar_lastmod, hreflang_dict=hreflangs_main)
    add_url_entry(main_urlset, f"{SITE_URL}/archive.html", latest_post_date)

    main_tree = ET.ElementTree(main_urlset)
    if hasattr(ET, 'indent'):
        ET.indent(main_tree, space="  ")
    with open("sitemap-main.xml", "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        main_tree.write(f, encoding="utf-8", xml_declaration=False)
        f.write(b'\n')

    # 2) توليد sitemap.xml (الخريطة الشاملة للصفحات الأساسية + المنشورات الغنية القابلة للفهرسة فقط)
    full_urlset = ET.Element(f"{{{SITEMAP_NS}}}urlset")
    add_url_entry(full_urlset, f"{SITE_URL}/", index_lastmod, hreflang_dict=hreflangs_main)
    add_url_entry(full_urlset, f"{SITE_URL}/ar.html", ar_lastmod, hreflang_dict=hreflangs_main)
    add_url_entry(full_urlset, f"{SITE_URL}/archive.html", latest_post_date)
    for p in indexable_posts:
        add_url_entry(full_urlset, f"{SITE_URL}/posts/post-{p['id']}.html", p['date'])

    full_tree = ET.ElementTree(full_urlset)
    if hasattr(ET, 'indent'):
        ET.indent(full_tree, space="  ")
    with open("sitemap.xml", "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        full_tree.write(f, encoding="utf-8", xml_declaration=False)
        f.write(b'\n')

    # 3) توليد sitemap.txt (نسخة نصية متوافقة مع المنشورات القابلة للفهرسة)
    txt_urls = [
        f"{SITE_URL}/",
        f"{SITE_URL}/ar.html",
        f"{SITE_URL}/archive.html"
    ] + [f"{SITE_URL}/posts/post-{p['id']}.html" for p in indexable_posts]

    with open("sitemap.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(txt_urls) + "\n")

    # 4) توليد robots.txt مع الإشارة إلى الخريطة المصغرة والكاملة
    robots_content = (
        "User-agent: *\n"
        "Allow: /\n\n"
        f"Sitemap: {SITE_URL}/sitemap-main.xml\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n"
        f"Sitemap: {SITE_URL}/sitemap.txt\n"
    )
    with open("robots.txt", "w", encoding="utf-8") as f:
        f.write(robots_content)

    print(
        f"✅ تم إنشاء sitemap-main.xml (3 صفحات أساسية) و sitemap.xml / sitemap.txt "
        f"({len(txt_urls)} صفحة غنية من أصل {len(posts)} منشور) و robots.txt بنجاح."
    )


# === 6. التشغيل التنفيذي ===
if __name__ == "__main__":
    posts = fetch_all_telegram_posts(CHANNEL_USERNAME)
    if not posts:
        print("❌ لم يتم استرجاع أي منشورات من تيليغرام! تم إيقاف التحديث لحماية الملفات الحالية من المسح.")
        sys.exit(1)

    print(f"⚙️ جاري توليد {len(posts)} صفحة منشورات وصفحات الأرشيف المتكاملة...")

    for p in posts:
        generate_single_post_html(p)

    total_pages = generate_archive_pages(posts)
    generate_sitemap_and_robots(posts, total_pages)
    print(f"✨ اكتمل البناء وتحديث كافة الصفحات بنجاح ({total_pages} صفحة أرشيف)!")