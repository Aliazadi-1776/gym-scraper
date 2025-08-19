# Gym Scraper 🏋️‍♂️

A Python-based scraper for [gymcenter.ir](https://www.gymcenter.ir) using **Playwright** and **BeautifulSoup**.  
It collects detailed information about gyms in Iran including:

- Name
- City
- Address
- Phone numbers
- Instagram & Website
- Opening hours
- Manager
- Male/Female availability
- Sessions (Male/Female)
- Description
- Images (cover, gallery, thumbnail)
- Map links
- Original detail page URL

## 🚀 Features
- Crawls **all pages** with pagination (`--max-pages` option).
- Normalizes Persian numbers & Iranian phone formats.
- Exports results to **CSV (UTF-8)**.
- Filters out placeholder images.

## 📦 Requirements
```bash
python3 -m pip install playwright beautifulsoup4 lxml pandas
python3 -m playwright install
playwright install-deps   # Linux only
```

## 🛠 Usage
Run the scraper:

```bash
python3 bashgah.py   --start-url "https://www.gymcenter.ir/باشگاه-ها"   --max-pages 0   --out gyms_all.csv
```

### Options
- `--start-url` → The main gyms list page (required).
- `--max-pages` → `0 = all pages` or set a number for limit.
- `--out` → Output CSV filename.

## 📂 Output
Example CSV fields:

```
name,city,address,phones,instagram,website,hours,manager,
has_male,has_female,male_session,female_session,
description,thumbnail,cover_image,images,map_links,details_url,error
```

## 📄 License
This project is licensed under the [MIT License](LICENSE).
