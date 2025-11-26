"""
Download cell population data from HRA API
"""
import requests
import os
import sys

# Import our config
import config

def download_csv():
    """Download the anatomical structure CSV from HRA API"""
    
    print("=" * 60)
    print("📥 DOWNLOADING CELL POPULATION DATA")
    print("=" * 60)
    
    # Create input directory if it doesn't exist
    os.makedirs(config.INPUT_DIR, exist_ok=True)
    
    # Output file path
    output_file = os.path.join(config.INPUT_DIR, "as-cell-populations.csv")
    
    print(f"\n🔗 Source: {config.DATA_URL}")
    print(f"💾 Saving to: {output_file}\n")
    
    try:
        # Make the request
        print("⏳ Downloading... ", end="", flush=True)
        response = requests.get(config.DATA_URL, timeout=30)
        response.raise_for_status()
        
        # Save the file
        with open(output_file, 'wb') as f:
            f.write(response.content)
        
        # Get file size
        file_size = os.path.getsize(output_file) / 1024
        
        print("✅ Done!")
        print(f"\n📊 Downloaded: {file_size:.2f} KB")
        print(f"📁 Location: {output_file}")
        
        # Quick preview of first few lines
        print("\n📋 Preview (first 3 lines):")
        print("-" * 60)
        with open(output_file, 'r') as f:
            for i, line in enumerate(f):
                if i < 3:
                    print(line.strip())
                else:
                    break
        print("-" * 60)
        
        return output_file
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error downloading data: {e}")
        sys.exit(1)

if __name__ == "__main__":
    download_csv()
    print("\n✅ Download complete!")