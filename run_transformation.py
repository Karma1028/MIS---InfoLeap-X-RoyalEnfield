import os
from utils.data_engine import DataTransformer

def main():
    json_path = "docs/investigation/full_scraped_data.json"
    output_path = "data/processed_data.csv"
    
    print(f"Loading {json_path}...")
    transformer = DataTransformer()
    df = transformer.transform(json_path)
    
    print(f"Transformation complete. Shape: {df.shape}")
    print(f"Saving to {output_path}...")
    df.to_csv(output_path, index=False)
    print("Done.")

if __name__ == "__main__":
    main()
