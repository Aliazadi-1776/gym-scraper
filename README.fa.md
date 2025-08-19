# 🏋️‍♀️ اسکریپر باشگاه‌ها (Gym Scraper)

یک اسکریپر پایتونی برای [gymcenter.ir](https://www.gymcenter.ir) با استفاده از **Playwright** و **BeautifulSoup**.  
این اسکریپت اطلاعات کامل باشگاه‌های ایران را جمع‌آوری می‌کند:

- نام
- شهر
- آدرس
- شماره تماس
- اینستاگرام و وب‌سایت
- ساعت کاری
- مدیریت
- مخصوص آقایان / بانوان
- سانس آقایان و بانوان
- توضیحات
- تصاویر (کاور، گالری، thumbnail)
- لینک نقشه
- لینک صفحه جزئیات

## ✨ امکانات
- پشتیبانی از صفحه به صفحه (pagination)  
- نرمال‌سازی اعداد فارسی و شماره‌های ایران  
- خروجی CSV با **UTF-8**  
- حذف عکس‌های پیش‌فرض و بی‌استفاده  

## 📦 پیش‌نیازها
```bash
python3 -m pip install playwright beautifulsoup4 lxml pandas
python3 -m playwright install
playwright install-deps   # برای لینوکس
```

## 🛠 نحوه استفاده
برای اجرای اسکریپر:

```bash
python3 bashgah.py   --start-url "https://www.gymcenter.ir/باشگاه-ها"   --max-pages 0   --out gyms_all.csv
```

### پارامترها
- `--start-url` → لینک صفحه لیست باشگاه‌ها (الزامی)  
- `--max-pages` → مقدار `0` = همه صفحات، یا هر عدد دلخواه برای محدودیت  
- `--out` → نام فایل خروجی CSV  

## 📂 خروجی
ستون‌های فایل CSV به این صورت خواهند بود:

```
name,city,address,phones,instagram,website,hours,manager,
has_male,has_female,male_session,female_session,
description,thumbnail,cover_image,images,map_links,details_url,error
```

## 📄 لایسنس
این پروژه تحت [لایسنس MIT](LICENSE) منتشر شده است.
