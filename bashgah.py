# -*- coding: utf-8 -*-
"""
bashgah.py — Gym Scraper (Playwright + BeautifulSoup)

ویژگی‌ها:
- پیمایش صفحه‌به‌صفحه با ?page=N (حلقه عددی) و توقف زمانی که صفحه جدید، لینک جدید ندهد
- استخراج فیلدهای زیر:
  name, city, address, phones, instagram, website, hours,
  manager, has_male, has_female, male_session, female_session,
  description, thumbnail, cover_image, images, map_links, details_url, error
- نرمال‌سازی اعداد فارسی و شماره‌های ایران
- فیلتر عکس‌های پیش‌فرض/غیرمرتبط؛ انتخاب cover_image تمیز

پیش‌نیاز:
    python3 -m pip install playwright beautifulsoup4 lxml pandas
    python3 -m playwright install

اجرا (مثال: 2 صفحه اول):
    python3 bashgah.py \
      --start-url "https://www.gymcenter.ir/باشگاه-ها?page=1" \
      --max-pages 2 \
      --out gyms_first2.csv

اجرا (همه صفحات تا انتها):
    python3 bashgah.py \
      --start-url "https://www.gymcenter.ir/باشگاه-ها?page=1" \
      --max-pages 0 \
      --out gyms_all.csv
"""
import re, json, time, argparse
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qs, urlencode, unquote
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# --- تنظیمات پایه
PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
PHONE_RE = re.compile(r"(?:\+98|0098|0)?9\d{9}|0\d{2,3}\s?\d{6,8}")
CITY_LIST = [
    "تهران","کرج","مشهد","اصفهان","شیراز","تبریز","قم","رشت","اهواز","کرمان","یزد",
    "قزوین","ارومیه","همدان","کرمانشاه","بندرعباس","سنندج","زنجان","ساری","اراک",
    "گرگان","خرم آباد","بوشهر","نیشابور","اردبیل","کاشان"
]
BAD_IMG_PATTERNS = [
    "/img/", "sprite", "logo", "placeholder", "blank",
    "promote_icon", "default", "icon", ".svg", "map", "gallery_lazy_load", "gym-no-image"
]

def fa_to_en(s: str) -> str:
    return (s or "").translate(PERSIAN_DIGITS)

def normalize_phones(s):
    if not s: return ""
    s = fa_to_en(str(s))
    nums = sorted(set(re.findall(PHONE_RE, s)))
    out = []
    for n in nums:
        n = n.replace(" ","")
        if n.startswith("+98"):
            out.append(n)
        elif n.startswith("0098"):
            out.append("+98"+n[4:])
        elif n.startswith("0") and len(n)==11 and n[1]=="9":
            out.append("+98"+n[1:])
        else:
            out.append(n)
    return "|".join(out)

def guess_city(addr: str):
    addr = addr or ""
    for c in CITY_LIST:
        if c and c in addr:
            return c
    return ""

def is_placeholder(url: str) -> bool:
    if not url: return True
    u = url.lower()
    return any(p in u for p in BAD_IMG_PATTERNS)

# --- جمع‌آوری لینک‌ها + thumbnail (از <img> / data-bg / background-image)
BG_URL_RE = re.compile(r'url\(["\']?(?P<u>[^"\')]+)["\']?\)')
def collect_list_links(html, base_url, card_selectors):
    soup = BeautifulSoup(html, "lxml")
    cards = []
    for sel in card_selectors.split(","):
        sel = sel.strip()
        if not sel: continue
        cards += soup.select(sel)
    links = []
    for c in cards:
        a = c.find("a", href=True)
        if not a: 
            continue
        u = urljoin(base_url, a["href"])

        # thumbnail candidates
        thumb = ""
        # 1) <img>
        img = c.find("img")
        if img:
            cand = img.get("data-src") or img.get("src") or ""
            if not cand and img.get("srcset"):
                cand = (img["srcset"].split(",")[0] or "").split()[0]
            if cand:
                cand = urljoin(base_url, cand.strip())
                if not is_placeholder(cand):
                    thumb = cand
        # 2) data-bg / data-background-image
        if not thumb:
            data_bg = c.get("data-bg") or c.get("data-background-image")
            if data_bg:
                cand = urljoin(base_url, data_bg.strip())
                if not is_placeholder(cand):
                    thumb = cand
        # 3) style="background-image:url(...)"
        if not thumb and c.has_attr("style"):
            m = BG_URL_RE.search(c["style"])
            if m:
                cand = urljoin(base_url, m.group("u").strip())
                if not is_placeholder(cand):
                    thumb = cand

        links.append((u, thumb))

    # unique by url
    seen, out = set(), []
    for u, t in links:
        if u in seen: continue
        seen.add(u)
        out.append((u, t))
    return out

# --- JSON-LD
def parse_jsonld(soup):
    data = {}
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            obj = json.loads(s.get_text())
        except Exception:
            continue
        items = obj if isinstance(obj, list) else [obj]
        for it in items:
            if not isinstance(it, dict): continue
            t = it.get("@type") or it.get("type","")
            t = ",".join(t) if isinstance(t, list) else str(t)
            if any(k in t for k in ["LocalBusiness","Organization","SportsActivityLocation","Gym"]):
                data.setdefault("name", it.get("name"))
                addr = it.get("address")
                if isinstance(addr, dict):
                    parts = [addr.get(k,"") for k in ["addressRegion","addressLocality","streetAddress"]]
                    a = " ".join([p for p in parts if p]).strip()
                    if a: data.setdefault("address", a)
                elif isinstance(addr, str):
                    data.setdefault("address", addr)
                tel = it.get("telephone") or it.get("tel")
                if tel: data.setdefault("phones", tel)
                hrs = it.get("openingHours") or it.get("openingHoursSpecification")
                if hrs: data.setdefault("hours", hrs if isinstance(hrs, str) else json.dumps(hrs, ensure_ascii=False))
                same = it.get("sameAs")
                if isinstance(same, list):
                    for u in same:
                        u = str(u)
                        if "instagram" in u.lower():
                            data["instagram"] = u
                        elif u.startswith("http"):
                            data.setdefault("website", u)
                u = it.get("url")
                if isinstance(u, str) and u.startswith("http"):
                    data.setdefault("website", u)
    return data

# --- بر اساس برچسب‌ها/لیبل‌ها
def extract_by_labels(soup):
    data = {}
    txt_all = fa_to_en(soup.get_text(" ", strip=True))
    nums = sorted(set(re.findall(PHONE_RE, txt_all)))
    if nums:
        data["phones"] = "|".join(nums)

    labels = {
        "address": ["آدرس","نشانی","محل","نشانی باشگاه"],
        "phone":   ["تلفن","شماره","تماس","Phone","Tel"],
        "hours":   ["ساعت","ساعات کار","ساعت کاری","زمان فعالیت"],
        "website": ["سایت","وب سایت","website","وب‌سایت"],
        "instagram":["اینستاگرام","Instagram","IG"],
        "city":    ["شهر","استان","منطقه","محله"],
    }
    for key, keys in labels.items():
        for k in keys:
            node = soup.find(lambda tag: tag and tag.name in ["div","li","span","p","th","td","dt","strong","b"]
                                      and tag.get_text(strip=True).startswith(k))
            if node:
                sib = node.find_next_sibling()
                if sib:
                    val = sib.get_text(" ", strip=True)
                    if val: data.setdefault(key, val)
                par = node.parent
                if par and key not in data:
                    val = par.get_text(" ", strip=True).replace(k,"").strip()
                    if len(val) > 2:
                        data[key] = val
                break
    return data

# --- فیلدهای خاص
def extract_instagram(soup):
    a = soup.find("a", href=lambda u: u and "instagram.com" in u)
    return a["href"].strip() if a and a.has_attr("href") else ""

def extract_manager(soup):
    # ساختار نمونه: <div class="detail-contact-name"><span> نام : </span><span>...</span></div>
    box = soup.select_one(".detail-contact-name")
    if box:
        spans = box.find_all("span")
        if len(spans) >= 2:
            name = spans[-1].get_text(" ", strip=True)
            return name
    # fallback
    cand = soup.find(lambda tag: tag and tag.name in ["div","p","li","span"] and "مدیریت" in tag.get_text())
    if cand:
        txt = cand.get_text(" ", strip=True)
        txt = re.sub(r"(مدیریت|مدیر)\s*[:：]?\s*", "", txt)
        return txt.strip()
    return ""

def extract_gender_flags(soup):
    male = bool(soup.find(lambda t: t.has_attr("title") and "آقایان" in t.get("title","")))
    female = bool(soup.find(lambda t: t.has_attr("title") and "بانوان" in t.get("title","")))
    label = soup.find(string=lambda s: s and "سانس آقایان و سانس بانوان" in s)
    if label: male, female = True, True
    return male, female

def extract_sessions_from_description(soup):
    tab = soup.select_one("#gym-descriptions") or soup
    paras = [p.get_text(" ", strip=True) for p in tab.find_all(["p","h3","h2","h4","blockquote"])]
    paras = [p.replace("\xa0"," ").strip() for p in paras if p and p.strip()]
    male_lines, female_lines, desc_lines = [], [], []
    mode = None
    for line in paras:
        if "سانس آقایان" in line or (line.startswith("ساعت کاری") and "آقایان" in line):
            mode = "male"; continue
        if "سانس بانوان" in line or (line.startswith("ساعت کاری") and "بانوان" in line):
            mode = "female"; continue
        if mode == "male":
            male_lines.append(line)
        elif mode == "female":
            female_lines.append(line)
        else:
            desc_lines.append(line)
    desc_lines = [d for d in desc_lines if not any(k in d for k in ["آدرس", "تهران", "خیابان", "میدان", "کوچه", "پلاک"])]
    male_session = " | ".join(male_lines[:6]).strip()
    female_session = " | ".join(female_lines[:6]).strip()
    description_text = " ".join(desc_lines[:6]).strip()
    return male_session, female_session, description_text

MAP_PATTERNS = [
    r"google\.(?:com|co\.\w+)/maps", r"goo\.gl/maps", r"map\.ir", r"neshan\.org",
    r"balad\.ir", r"openstreetmap\.org", r"yandex\.(?:com|ru)/maps", r"maps\.apple\.com",
    r"/maps?/", r"map(?:s)?\.(?:png|jpg|jpeg|webp)$", r"(?:location|marker|pin)\.(?:png|jpg|jpeg|webp)$",
]
MAP_RE = re.compile("|".join(MAP_PATTERNS), re.I)

def extract_map_links(soup):
    links = set()
    for a in soup.find_all("a", href=True):
        if MAP_RE.search(a["href"]):
            links.add(a["href"].strip())
    for fr in soup.find_all("iframe", src=True):
        if MAP_RE.search(fr["src"]):
            links.add(fr["src"].strip())
    return list(links)[:5]

def extract_images(soup, base_url):
    urls = set()
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        u = urljoin(base_url, og["content"].strip())
        if not is_placeholder(u):
            urls.add(u)
    for img in soup.find_all("img"):
        cand = img.get("data-src") or img.get("src") or ""
        if not cand and img.get("srcset"):
            cand = (img["srcset"].split(",")[0] or "").split()[0]
        if not cand: continue
        u = urljoin(base_url, cand.strip())
        if not is_placeholder(u):
            urls.add(u)
    return list(urls)[:12]

# --- جزئیات یک باشگاه
def scrape_detail_html(html, base_url, title_selectors):
    soup = BeautifulSoup(html, "lxml")

    # عنوان
    name = ""
    for sel in title_selectors.split(","):
        el = soup.select_one(sel.strip())
        if el:
            name = el.get_text(" ", strip=True); break
    if not name:
        ogt = soup.find("meta", property="og:title")
        if ogt and ogt.get("content"): name = ogt["content"].strip()

    row = {"name": name}

    # JSON-LD → لیبل‌ها
    jd = parse_jsonld(soup); row.update({k:v for k,v in jd.items() if v})
    lab = extract_by_labels(soup)
    for k,v in lab.items():
        row.setdefault(k, v)

    # مدیریت
    manager = extract_manager(soup)
    if manager: row["manager"] = manager

    # سانس‌ها + توضیحات
    male_session, female_session, desc = extract_sessions_from_description(soup)
    if male_session: row["male_session"] = male_session
    if female_session: row["female_session"] = female_session
    if desc: row["description"] = desc

    # پرچم‌ها
    male_flag, female_flag = extract_gender_flags(soup)
    row["has_male"] = int(bool(male_flag))
    row["has_female"] = int(bool(female_flag))

    # اینستاگرام (اگر از JSON-LD نیامده)
    if not row.get("instagram"):
        ig = extract_instagram(soup)
        if ig: row["instagram"] = ig

    # تصاویر و نقشه
    imgs = extract_images(soup, base_url)
    if imgs: row["images"] = "|".join(imgs)
    maps = extract_map_links(soup)
    if maps: row["map_links"] = "|".join(maps)

    # نرمال‌سازی تلفن و شهر
    if row.get("phones"):
        row["phones"] = normalize_phones(row["phones"])
    if not row.get("city") and row.get("address"):
        row["city"] = guess_city(row["address"])

    # cover_image: اول عکس واقعی، سپس thumbnail واقعی
    cover = ""
    first_img = row.get("images","").split("|")[0].strip() if row.get("images") else ""
    thumb = (row.get("thumbnail") or "").strip()
    if first_img and not is_placeholder(first_img):
        cover = first_img
    elif thumb and not is_placeholder(thumb):
        cover = thumb
    row["cover_image"] = cover

    return row

# --- پیمایش عددی صفحه‌ها با ?page=N
def scrape_all_pages(page, start_url, card_selectors, title_selectors, wait_ms, max_pages):
    def set_page(u, n):
        sp = urlsplit(u)
        q = parse_qs(sp.query)
        q['page'] = [str(n)]
        new_q = urlencode({k: v[0] for k, v in q.items()})
        return urlunsplit((sp.scheme, sp.netloc, sp.path, new_q, sp.fragment))

    # شروع از page=1 اگر تعیین نشده
    cur_page = 1
    m = re.search(r'[?&]page=(\d+)', start_url)
    if m: 
        try: cur_page = int(m.group(1))
        except: cur_page = 1

    all_links = []
    visited_pages = 0

    while True:
        url = set_page(start_url, cur_page)
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(wait_ms/1000)

        html = page.content()
        base = page.url

        links = collect_list_links(html, base, card_selectors)
        # لینک‌های جدید نسبت به قبل
        old = {x[0] for x in all_links}
        new_links = [(u,t) for (u,t) in links if u not in old]
        print(f"[list] page {cur_page}: +{len(new_links)} new (total {len(all_links)+len(new_links)})")

        if not new_links:
            # هیچ لینک جدیدی اضافه نشد ⇒ انتهای صفحات
            break

        all_links.extend(new_links)
        visited_pages += 1

        # محدودیت صفحات (اگر 0 نیست)
        if max_pages and visited_pages >= max_pages:
            break

        cur_page += 1

    # یکتا سازی
    seen, uniq = set(), []
    for u, t in all_links:
        if u in seen: continue
        seen.add(u); uniq.append((u,t))

    # جزئیات هر لینک
    rows = []
    for i, (u, thumb) in enumerate(uniq, 1):
        rec = {"details_url": u, "thumbnail": thumb}
        try:
            page.goto(u, wait_until="domcontentloaded", timeout=30000)
            try:
                page.wait_for_selector("h1, h2, main, article, .content, .container", timeout=8000)
            except PWTimeout:
                pass
            time.sleep(wait_ms/1000)
            data = scrape_detail_html(page.content(), page.url, title_selectors)
            rec.update(data)
            rec["error"] = ""
        except Exception as e:
            rec["error"] = str(e)
        rows.append(rec)
        print(f"[{i}/{len(uniq)}] {rec.get('name','')} | err={bool(rec.get('error'))}")
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-url", required=True)
    ap.add_argument("--out", default="gyms.csv")
    ap.add_argument("--cards", default=".item-box-margin,.col-sm-6.col-md-4,article.gym-card,.card-simple")
    ap.add_argument("--titles", default="h1,h2,.title,.page-title")
    ap.add_argument("--wait", type=int, default=1200, help="ms to wait after navigation")
    ap.add_argument("--max-pages", type=int, default=0, help="0 = همه صفحات؛ n = حداکثر n صفحه")
    args = ap.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(locale="fa-IR")
        page = ctx.new_page()

        rows = scrape_all_pages(
            page=page,
            start_url=args.start_url,
            card_selectors=args.cards,
            title_selectors=args.titles,
            wait_ms=args.wait,
            max_pages=args.max_pages,
        )
        browser.close()

    cols = [
        "name","city","address","phones","instagram","website","hours",
        "manager","has_male","has_female","male_session","female_session",
        "description","thumbnail","cover_image","images","map_links","details_url","error"
    ]
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df.columns: df[c] = ""
    df = df[cols]
    df.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"Saved -> {args.out} ({len(df)})")

if __name__ == "__main__":
    main()

