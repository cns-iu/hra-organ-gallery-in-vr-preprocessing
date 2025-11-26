"""
Filter and process cell population data for heart only
"""
import pandas as pd
import os
import sys

# Import our config
import config

def load_and_filter_data():
    """Load CSV and filter for heart, azimuth/celltypist, male/female"""
    
    print("=" * 60)
    print("🔬 PROCESSING CELL POPULATION DATA")
    print("=" * 60)
    
    # Input file path
    input_file = os.path.join(config.INPUT_DIR, "as-cell-populations.csv")
    
    print(f"\n📂 Loading: {input_file}")
    
    # Load CSV
    df = pd.read_csv(input_file)
    print(f"📊 Total rows loaded: {len(df):,}")
    
    # Show unique organs (just for info)
    print(f"\n🫀 Unique organs in dataset: {df['organ'].nunique()}")
    print(f"   Organs: {sorted(df['organ'].unique())[:10]}...")  # Show first 10
    
    # Filter for heart
    print(f"\n🔍 Filtering for:")
    print(f"   Organ: {config.ORGAN_FILTER}")
    print(f"   Tools: {config.TOOLS_FILTER}")
    print(f"   Sex: {config.SEX_FILTER}")
    
    # Apply filters
    df_filtered = df[
        (df['organ'].str.lower() == config.ORGAN_FILTER.lower()) &
        (df['tool'].str.lower().isin([t.lower() for t in config.TOOLS_FILTER])) &
        (df['sex'].str.lower().isin([s.lower() for s in config.SEX_FILTER]))
    ]
    
    print(f"\n✅ Filtered rows: {len(df_filtered):,}")
    
    # Show summary of filtered data
    print(f"\n📋 Filtered Data Summary:")
    print(f"   Anatomical structures: {df_filtered['as_label'].nunique()}")
    print(f"   Cell types: {df_filtered['cell_label'].nunique()}")
    print(f"   Tools: {df_filtered['tool'].unique().tolist()}")
    print(f"   Sex: {df_filtered['sex'].unique().tolist()}")
    
    # Save filtered data
    os.makedirs(os.path.dirname(config.FILTERED_CSV), exist_ok=True)
    df_filtered.to_csv(config.FILTERED_CSV, index=False)
    print(f"\n💾 Saved filtered data to: {config.FILTERED_CSV}")
    
    # Preview
    print(f"\n📋 Preview (first 5 rows):")
    print("-" * 60)
    print(df_filtered[['as_label', 'sex', 'tool', 'cell_label', 'cell_count']].head())
    print("-" * 60)
    
    return df_filtered

if __name__ == "__main__":
    df = load_and_filter_data()
    print("\n✅ Processing complete!")