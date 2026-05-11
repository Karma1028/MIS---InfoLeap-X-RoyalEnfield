import unittest
import pandas as pd
import json
import os
from utils.data_engine import DataTransformer

class TestDataTransformer(unittest.TestCase):
    def setUp(self):
        self.mock_data = {
            "All | Classic 650": {
                "Age": [
                    {
                        "Unnamed: 0": "Base : All_Classic 650",
                        "All": "204",
                        "August'2025": "22",
                        "September'2025": "44",
                        "October'2025": "19",
                        "November'2025": "20",
                        "December'2025": "22",
                        "January'2026": "21",
                        "February'2026": "26",
                        "March'2026": "13",
                        "April'2026": "17"
                    },
                    {
                        "Unnamed: 0": "18 to 25 Years",
                        "All": "16%",
                        "August'2025": "23%",
                        "September'2025": "16%",
                        "October'2025": "26%",
                        "November'2025": "20%",
                        "December'2025": "14%",
                        "January'2026": "5%",
                        "February'2026": "15%",
                        "March'2026": "23%",
                        "April'2026": "6%"
                    },
                    {
                        "Unnamed: 0": "46 or more",
                        "All": "2%",
                        "August'2025": "-",
                        "September'2025": "-",
                        "October'2025": "-",
                        "November'2025": "5%",
                        "December'2025": "5%",
                        "January'2026": "5%",
                        "February'2026": "8%",
                        "March'2026": "-",
                        "April'2026": "-"
                    }
                ]
            }
        }
        self.temp_json = "temp_mock_data.json"
        with open(self.temp_json, "w") as f:
            json.dump(self.mock_data, f)
        self.transformer = DataTransformer()

    def tearDown(self):
        if os.path.exists(self.temp_json):
            os.remove(self.temp_json)

    def test_flatten_data(self):
        df = self.transformer.transform(self.temp_json)
        
        # Verify structure
        expected_columns = [
            "Platform", "Model", "Section", "Table_Name", "Metric", 
            "All_Avg", "Aug_25", "Sep_25", "Oct_25", "Nov_25", "Dec_25", 
            "Jan_26", "Feb_26", "Mar_26", "Apr_26", "JAS_25", "OND_25", "JFM_26"
        ]
        for col in expected_columns:
            self.assertIn(col, df.columns)
            
        # Verify content for "18 to 25 Years"
        row = df[df["Metric"] == "18 to 25 Years"].iloc[0]
        self.assertEqual(row["Platform"], "All")
        self.assertEqual(row["Model"], "Classic 650")
        self.assertEqual(row["Table_Name"], "Age")
        self.assertEqual(row["All_Avg"], 16.0)
        self.assertEqual(row["Aug_25"], 23.0)
        self.assertEqual(row["Apr_26"], 6.0)
        
        # Verify filtering of "Base :" metrics
        base_rows = df[df["Metric"].str.contains("Base :")]
        self.assertEqual(len(base_rows), 0)

        # Verify cleaning (dash to 0 or NaN, choosing 0 for this use case if appropriate, or NaN)
        # Let's check "46 or more" for August'2025 which was "-"
        row_dash = df[df["Metric"] == "46 or more"].iloc[0]
        self.assertEqual(row_dash["Aug_25"], 0.0)

    def test_quarterly_calculations(self):
        df = self.transformer.transform(self.temp_json)
        row = df[df["Metric"] == "18 to 25 Years"].iloc[0]
        
        # JAS_25 = (Aug_25 + Sep_25) / 2 (since July is missing in mock) 
        # Actually standard definition JAS is Jul-Aug-Sep.
        # Let's see how transformer handles it.
        # If I use simple mean of available months in that quarter:
        # JAS: Aug=23, Sep=16 -> Avg = 19.5
        self.assertAlmostEqual(row["JAS_25"], 19.5)

if __name__ == "__main__":
    unittest.main()
