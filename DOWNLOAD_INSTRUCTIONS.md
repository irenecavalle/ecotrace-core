# Sentinel-2 L2A Download Instructions

Complete guide for downloading Sentinel-2 L2A data via Google Earth Engine.

## Prerequisites

### 1. Google Earth Engine Access
- [ ] Have Google Cloud Project with Earth Engine enabled
- [ ] Created service account with Editor role
- [ ] Downloaded private key JSON file

### 2. Environment Setup

```bash
# Set environment variables
export GEE_KEY_FILE=path/to/service-account-key.json
export GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key.json

# Verify authentication is working
python src/ingestion/gee_auth.py
```

Expected output:
```
✅ GEE authentication successful
   Service account: xxx@yyy.iam.gserviceaccount.com
   Project: ecotrace-xxxxx
```

### 3. Install Dependencies

```bash
# Create conda environment
conda env create -f environment.yml
conda activate ecotrace

# Or install with pip
pip install earthengine-api rasterio geopandas numpy pandas
```

## Download Data - Test Run (1 Year)

### Step 1: Download Pakistan (January - December 2023)

```bash
python src/ingestion/download_sentinel2.py \
  --aoi pakistan \
  --start 2023-01 \
  --end 2023-12 \
  --output data/raw/sentinel2/
```

**Expected output:**
```
======================================================================
EcoTrace Sentinel-2 L2A Download
======================================================================
Step 1: Authenticating with Google Earth Engine...
✓ Connection successful

Step 2: Testing connection...
✓ Connection successful

Step 3: Downloading 1 AOI(s) for 2023-01 to 2023-12

📍 Processing: Indus Basin, Pakistan
Downloading Sentinel-2 L2A for Indus Basin, Pakistan
Date range: 2023-01 to 2023-12
Output directory: data/raw/sentinel2/

Processing 2023-01-01 to 2023-01-31...
✓ Export queued: S2L2A_pakistan_202301
  Region: [...]
  Scale: 10m | Bands: ['B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B8A', 'B11', 'B12']

Processing 2023-02-01 to 2023-02-28...
✓ Export queued: S2L2A_pakistan_202302
...

Completed download for pakistan: 12 monthly composites

======================================================================
SUMMARY
======================================================================
✓ Successful: 1/1 AOI(s)
Output directory: data/raw/sentinel2/
Note: Files queued to Google Drive. Check Earth Engine Code Editor:
      https://code.earthengine.google.com/
======================================================================
```

### Step 2: Download All 3 AOIs (Parallel Processing)

```bash
# Download all three AOIs for 1 year
python src/ingestion/download_sentinel2.py \
  --aoi all \
  --start 2023-01 \
  --end 2023-12 \
  --output data/raw/sentinel2/
```

This queues **36 export tasks** to Google Drive:
- Pakistan: 12 months
- China: 12 months
- Bangladesh: 12 months

### Step 3: Monitor Exports

After running the download script, files are queued to your Google Drive.

1. Go to **Google Earth Engine Code Editor**: https://code.earthengine.google.com/
2. Click **⚙️ Run tasks** (top right)
3. Monitor progress of all export tasks
4. Download completed files manually, or:

**Option A: Download from Drive**
```bash
# Manually download from Google Drive
# File path: My Drive/ecotrace-exports/S2L2A_*.tif

# Move to local directory
mv ~/Downloads/S2L2A_*.tif data/raw/sentinel2/
```

**Option B: Automatic Download (if GCS configured)**
Configure Google Cloud Storage bucket and Earth Engine will auto-save files:
```bash
export GCS_BUCKET=your-bucket-name

python src/ingestion/download_sentinel2.py \
  --aoi all \
  --start 2023-01 \
  --end 2023-12 \
  --output gs://your-bucket-name/sentinel2/
```

Then download from GCS:
```bash
gsutil -m cp gs://your-bucket-name/sentinel2/S2L2A_*.tif data/raw/sentinel2/
```

## Data Specifications

### Output Files

Each file is a monthly median composite:
- **Filename**: `S2L2A_{aoi}_{YYYYMM}.tif`
- **Format**: GeoTIFF (Cloud Optimized)
- **Resolution**: 10 meters
- **Projection**: EPSG:4326 (WGS84)
- **Bands**: 10 Sentinel-2 bands
  - B2: Blue (490nm)
  - B3: Green (560nm)
  - B4: Red (665nm)
  - B5-B7: Red Edge (705-783nm)
  - B8: NIR (842nm)
  - B8A: Red Edge (865nm)
  - B11-B12: SWIR (1610-2190nm)

### Processing

For each month:
1. ✓ Filters all Sentinel-2 L2A scenes for AOI
2. ✓ Applies cloud masking using QA60 band
3. ✓ Computes **pixel-wise median** across all valid observations
4. ✓ Clips to AOI bounds
5. ✓ Exports as GeoTIFF at 10m resolution

### AOI Definitions

| Region | Bounds | Area |
|--------|--------|------|
| Pakistan (Indus) | 25°N–34.5°N, 66.5°E–74.5°E | ~198,000 km² |
| China (Yangtze) | 29°N–32°N, 118°E–122°E | ~35,000 km² |
| Bangladesh (Dhaka) | 23°N–24.5°N, 89.5°E–91.5°E | ~12,000 km² |

## Troubleshooting

### Issue: `GEE_KEY_FILE environment variable not set`

**Solution:**
```bash
export GEE_KEY_FILE=path/to/service-account-key.json
python src/ingestion/download_sentinel2.py --aoi pakistan --start 2023-01 --end 2023-12 --output data/raw/sentinel2/
```

### Issue: `GEE key file not found`

**Solution:**
- Verify path is correct: `ls -la /path/to/key.json`
- Use absolute path: `export GEE_KEY_FILE=/absolute/path/to/key.json`
- Use home expansion: `export GEE_KEY_FILE=~/secrets/gee_key.json`

### Issue: `Failed to connect to Google Earth Engine`

**Check:**
1. Service account has **Editor** role in Google Cloud Project
2. **Earth Engine API** is enabled in project
3. **Quota** not exceeded
4. **Network connection** is working

**Test connection:**
```bash
python src/ingestion/gee_auth.py
```

### Issue: No data returned for AOI

**Check:**
- Date range is valid (has Sentinel-2 coverage)
- AOI coordinates are correct
- No cloud cover (entire month cloudy)

**Verify:**
```python
# Quick check in Python
import ee
from src.ingestion.gee_auth import authenticate, initialize
from src.ingestion.download_sentinel2 import create_geometry, create_monthly_composite

authenticate()
initialize()

# Check Pakistan Jan 2023
geom = create_geometry('pakistan')
composite = create_monthly_composite(geom, '2023-01-01', '2023-01-31')
print(composite.getInfo())  # Should show bands and metadata
```

## Full Year Download (2019-2024)

After successful 1-year test, download full historical archive:

```bash
python src/ingestion/download_sentinel2.py \
  --aoi all \
  --start 2019-01 \
  --end 2024-12 \
  --output data/raw/sentinel2/
```

This queues **216 export tasks** (3 AOIs × 72 months):
- Total data: ~500 GB (before compression)
- Processing time: ~2-4 hours (Earth Engine queued processing)
- Download time: ~2-4 hours (depending on connection)

## Next Steps

After downloading, process with preprocessing pipeline:

```bash
# 1. Apply cloud masking
python src/preprocessing/cloud_mask.py \
  --input data/raw/sentinel2/ \
  --output data/processed/masked/ \
  --threshold 0.5

# 2. Generate monthly composites
python src/preprocessing/monthly_composite.py \
  --input data/processed/masked/ \
  --output data/processed/composites/ \
  --method median

# 3. Compute spectral indices
python src/preprocessing/compute_indices.py \
  --input data/processed/composites/ \
  --output data/processed/indices/
```

## References

- [Google Earth Engine Documentation](https://developers.google.com/earth-engine)
- [Sentinel-2 Data Product](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED)
- [Earth Engine Python API](https://github.com/google/earthengine-api)
