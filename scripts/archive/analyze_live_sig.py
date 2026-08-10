import re
import sys
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")

path = "docs/investigation/site_overall.html"
with open(path, "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

tables = soup.find_all("table", class_="caption-top")
print(f"Found {len(tables)} tables in site_overall.html")

sig_samples = []

for idx, t in enumerate(tables):
    cap = t.find("caption")
    cap_text = cap.get_text(strip=True) if cap else f"Table_{idx}"

    rows = t.find_all("tr")
    if not rows:
        continue

    headers = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
    base_row = [c.get_text(strip=True) for c in rows[1].find_all(["th", "td"])] if len(rows) > 1 else []

    all_col_val = ""
    all_col_n = base_row[1] if len(base_row) > 1 else ""

    for r in rows[2:]:
        cells = r.find_all(["th", "td"])
        if not cells:
            continue
        row_name = cells[0].get_text(strip=True)
        all_val = cells[1].get_text(strip=True) if len(cells) > 1 else ""

        for col_idx, cell in enumerate(cells[2:], start=2):
            title = cell.get("title", "")
            style = cell.get("style", "")
            bgcolor = cell.get("bgcolor", "")
            val_txt = cell.get_text(strip=True)
            col_name = headers[col_idx] if col_idx < len(headers) else f"Col_{col_idx}"
            month_n = base_row[col_idx] if col_idx < len(base_row) else ""

            if "z =" in title or bgcolor or "green" in style:
                sig_samples.append({
                    "table": cap_text,
                    "row": row_name,
                    "col": col_name,
                    "val": val_txt,
                    "all_val": all_val,
                    "month_n": month_n,
                    "all_n": all_col_n,
                    "title": title,
                    "style": style,
                    "bgcolor": bgcolor
                })

print(f"Found total highlighted significance cells: {len(sig_samples)}")
for s in sig_samples[:30]:
    print(f"Table: [{s['table'][:30]}] | Row: [{s['row'][:35]}] | Col: [{s['col']}] | Val: [{s['val']}] (All={s['all_val']}) | Month_N={s['month_n']}, All_N={s['all_n']} | Title: [{s['title']}] | BgColor: [{s['bgcolor']}] | Style: [{s['style']}]")
