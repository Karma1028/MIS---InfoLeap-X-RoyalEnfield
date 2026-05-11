import pandas as pd
import json
import numpy as np

class DataTransformer:
    def __init__(self):
        self.month_map = {
            "August'2025": "Aug_25",
            "September'2025": "Sep_25",
            "October'2025": "Oct_25",
            "November'2025": "Nov_25",
            "December'2025": "Dec_25",
            "January'2026": "Jan_26",
            "February'2026": "Feb_26",
            "March'2026": "Mar_26",
            "April'2026": "Apr_26"
        }
        self.expected_cols = [
            "Platform", "Model", "Section", "Table_Name", "Metric", 
            "All_Avg", "Aug_25", "Sep_25", "Oct_25", "Nov_25", "Dec_25", 
            "Jan_26", "Feb_26", "Mar_26", "Apr_26", "JAS_25", "OND_25", "JFM_26"
        ]

    def _clean_value(self, val):
        if val == "-" or val is None:
            return 0.0
        if isinstance(val, str):
            val = val.replace("%", "").replace(",", "")
            try:
                return float(val)
            except ValueError:
                return 0.0
        return float(val)

    def transform(self, json_path):
        with open(json_path, 'r') as f:
            data = json.load(f)

        all_rows = []

        for combo_key, tables in data.items():
            # Parse Platform and Model
            if " | " in combo_key:
                platform, model = combo_key.split(" | ", 1)
            else:
                platform = "Unknown"
                model = combo_key

            for table_name, rows in tables.items():
                section = "General" # Default section
                
                for row in rows:
                    metric = row.get("Unnamed: 0", "Unknown")
                    # No longer skipping Base rows to allow KPI extraction
                    
                    processed_row = {
                        "Platform": platform,
                        "Model": model,
                        "Section": section,
                        "Table_Name": table_name,
                        "Metric": metric,
                        "All_Avg": self._clean_value(row.get("All"))
                    }

                    # Map months
                    for raw_month, standard_month in self.month_map.items():
                        processed_row[standard_month] = self._clean_value(row.get(raw_month))

                    # Calculate Quarters (JAS, OND, JFM)
                    # JAS: July, August, September
                    jas_vals = [processed_row.get("Aug_25", 0.0), processed_row.get("Sep_25", 0.0)]
                    processed_row["JAS_25"] = round(np.mean(jas_vals), 2) if jas_vals else 0.0

                    # OND: October, November, December
                    ond_vals = [processed_row.get("Oct_25", 0.0), processed_row.get("Nov_25", 0.0), processed_row.get("Dec_25", 0.0)]
                    processed_row["OND_25"] = round(np.mean(ond_vals), 2) if ond_vals else 0.0

                    # JFM: January, February, March
                    jfm_vals = [processed_row.get("Jan_26", 0.0), processed_row.get("Feb_26", 0.0), processed_row.get("Mar_26", 0.0)]
                    processed_row["JFM_26"] = round(np.mean(jfm_vals), 2) if jfm_vals else 0.0

                    all_rows.append(processed_row)

        df = pd.DataFrame(all_rows)
        
        # Ensure all expected columns exist
        for col in self.expected_cols:
            if col not in df.columns:
                df[col] = 0.0
                
        return df[self.expected_cols]
