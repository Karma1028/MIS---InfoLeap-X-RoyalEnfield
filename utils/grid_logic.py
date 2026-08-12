# DEAD MODULE — safe to remove next cleanup (no imports found outside this file as of 2026-08-10)
import pandas as pd

class GridMapper:
    """Maps questionnaire logic to dashboard grids."""
    
    def __init__(self, dm_path='data/MIS_datamap.xlsx'):
        self.dm = pd.read_excel(dm_path, skiprows=2)
        
    def get_grid_definition(self, prefix):
        """Extracts variables for a specific grid family (e.g., 'aq5')."""
        vars = self.dm[self.dm['Variable'].str.startswith(prefix, na=False)]
        return vars[['Variable', 'Label', 'Measurement Level']].to_dict(orient='records')

if __name__ == "__main__":
    mapper = GridMapper()
    print("--- Mapping AQ5 (Brand Consideration Grid) ---")
    aq5_grid = mapper.get_grid_definition('aq5a')
    print(f"Found {len(aq5_grid)} variables in this grid family.")
    print("Sample:", aq5_grid[:3])
