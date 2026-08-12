import re
import sys
from bs4 import BeautifulSoup
from utils.stat_engine import calculate_significance, Z_95, Z_90_LOW

sys.stdout.reconfigure(encoding="utf-8")

path = "docs/investigation/site_overall.html"
with open(path, "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

tables = soup.find_all("table", class_="caption-top")

matches = 0
total_checked = 0

for t in tables:
    cap = t.find("caption")
    cap_txt = cap.get_text(strip=True) if cap else ""
    if "reasons" in cap_txt.lower() or "buying" in cap_txt.lower() or "kbf" in cap_txt.lower() or "cancelling" in cap_txt.lower() or "rejection" in cap_txt.lower():
        rows = t.find_all("tr")
        if len(rows) < 3:
            continue
        headers = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
        base_row = [c.get_text(strip=True) for c in rows[1].find_all(["th", "td"])]

        all_b = int(re.sub(r"\D", "", base_row[1])) if len(base_row) > 1 and re.sub(r"\D", "", base_row[1]) else 0
        if all_b == 0:
            continue

        for r in rows[2:10]:
            cells = r.find_all(["th", "td"])
            if len(cells) < 3:
                continue
            row_name = cells[0].get_text(strip=True)
            all_val_str = cells[1].get_text(strip=True).replace("%", "").strip()
            p2 = float(all_val_str) / 100.0 if all_val_str and all_val_str != "-" else 0.0

            for col_idx in range(2, min(len(cells), 6)):
                col_name = headers[col_idx]
                month_b_str = re.sub(r"\D", "", base_row[col_idx]) if col_idx < len(base_row) else "0"
                b = int(month_b_str) if month_b_str else 0
                val_str = cells[col_idx].get_text(strip=True).replace("%", "").strip()
                p1 = float(val_str) / 100.0 if val_str and val_str != "-" else 0.0

                cell = cells[col_idx]
                title = cell.get("title", "")
                style = cell.get("style", "")
                bgcolor = cell.get("bgcolor", "")

                web_highlight = ""
                if "green" in style:
                    web_highlight = "95"
                elif bgcolor == "lightgreen":
                    web_highlight = "90"

                if b >= 30 and all_b >= 30:
                    res = calculate_significance(p1, b, p2, all_b)
                    calc_tier = res["tier"]

                    m = re.search(r"z = ([\d\.]+)", title) if title else None
                    web_z = float(m.group(1)) if m else None

                    total_checked += 1
                    if web_highlight == calc_tier:
                        matches += 1

                    print(f"Table: {cap_txt[:25]} | Row: {row_name[:20]} | Col: {col_name} | Calc Z: {res['z_score']:.3f} (Tier={calc_tier}) | Web Z: {web_z} (WebTier={web_highlight})")

print(f"\nSignificance calculation match rate against live website: {matches}/{total_checked} ({matches/total_checked*100:.1f}%)" if total_checked > 0 else "No cells checked.")
