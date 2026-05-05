# 🌍 EcoTrace

> **AI-Powered Sustainability Traceability for Fashion Supply Chains**
> PAIBS Project — ESADE Business School · 2025

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen)]()

EcoTrace uses **Copernicus satellite data (Sentinel-1/2)** + **AI** to independently monitor environmental risks at fashion supplier locations — deforestation, water stress, and water pollution — and converts them into a single **0–100 EcoScore** per supplier. No supplier cooperation required.

---

## 📋 Table of Contents

- [Project Overview](#-project-overview)
- [Repository Structure](#-repository-structure)
- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Data](#-data)
- [Pipeline](#-pipeline)
- [Models](#-models)
- [Dashboard](#-dashboard)
- [API](#-api)
- [Results](#-results)
- [Environment Variables](#-environment-variables)
- [Contributing](#-contributing)
- [References](#-references)

---

## 🎯 Project Overview

| | |
|---|---|
| **Problem** | SMB fashion brands cannot verify supplier environmental impact — CSRD compliance is impossible without satellite-independent evidence |
| **Solution** | Automated Sentinel-2 + AI pipeline that scores every supplier on deforestation, water stress, and pollution — no supplier cooperation needed |
| **AOIs** | Indus Basin (Pakistan) · Yangtze Delta (China) · Dhaka Region (Bangladesh) |
| **EO Data** | Sentinel-2 L2A, Sentinel-1 GRD, MODIS MOD16A2, GRACE-FO |
| **Time Range** | January 2019 – December 2024 (monthly composites) |
| **Dashboard** | https://app.ecotrace.earth |
| **Report** | [PAIBS_Report.docx](docs/PAIBS_Report.docx) |

### EcoScore Formula

```
EcoScore = 100 − (0.40 × Deforestation_Risk + 0.35 × Water_Stress + 0.25 × Pollution_Proxy)
```

- **≥ 70** → ✅ COMPLIANT
- **40–69** → ⚠️ REVIEW REQUIRED  
- **< 40** → 🔴 CRITICAL RISK

---

## 📁 Repository Structure

```
ecotrace/
│
├── 📂 data/
│   ├── raw/                    # Raw downloaded EO data (gitignored, DVC tracked)
│   ├── processed/              # Cloud-masked, composited, indexed tiles
│   ├── suppliers/              # Supplier GPS coordinates (CSV)
│   │   └── suppliers_sample.csv
│   └── labels/                 # Manual annotation labels for model training
│
├── 📂 src/
│   ├── 📂 ingestion/           # Google Earth Engine data download scripts
│   │   ├── download_sentinel2.py
│   │   ├── download_sentinel1.py
│   │   ├── download_modis.py
│   │   └── gee_auth.py
│   │
│   ├── 📂 preprocessing/       # Cloud masking, compositing, index computation
│   │   ├── cloud_mask.py
│   │   ├── monthly_composite.py
│   │   ├── compute_indices.py  # NDVI, NDWI, NDBI, RE-ChlI
│   │   ├── patch_generator.py  # 64×64 tile extraction per supplier location
│   │   └── normalise.py
│   │
│   ├── 📂 models/              # PyTorch model definitions
│   │   ├── unet.py             # U-Net deforestation segmentation model
│   │   ├── xgboost_water.py    # XGBoost water stress classifier
│   │   ├── cnn_pollution.py    # CNN pollution proxy regressor
│   │   └── ecoscore.py         # EcoScore aggregation logic
│   │
│   ├── 📂 training/            # Training loops and experiment configs
│   │   ├── train_unet.py
│   │   ├── train_xgboost.py
│   │   ├── train_cnn.py
│   │   ├── config/
│   │   │   ├── unet_config.yaml
│   │   │   ├── xgboost_config.yaml
│   │   │   └── cnn_config.yaml
│   │   └── mlflow_tracking.py
│   │
│   ├── 📂 inference/           # Batch inference + EcoScore computation
│   │   ├── run_inference.py    # Main inference script
│   │   ├── batch_score.py      # Score 50 suppliers in parallel
│   │   └── evidence_pack.py    # Generate PDF Evidence Pack per supplier
│   │
│   └── 📂 api/                 # Flask REST API
│       ├── app.py              # Main Flask app
│       ├── routes/
│       │   ├── scores.py       # GET /suppliers/{id}/score
│       │   ├── alerts.py       # GET /alerts
│       │   └── export.py       # GET /export/csrd
│       └── Dockerfile
│
├── 📂 dashboard/               # React + Tailwind frontend (Lovable export)
│   ├── src/
│   │   ├── components/
│   │   │   ├── Sidebar.jsx
│   │   │   ├── SupplierTable.jsx
│   │   │   ├── EcoGauge.jsx
│   │   │   ├── AlertPanel.jsx
│   │   │   ├── TrendChart.jsx
│   │   │   ├── QRLabel.jsx
│   │   │   └── CSRDPanel.jsx
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Suppliers.jsx
│   │   │   └── Map.jsx
│   │   └── App.jsx
│   ├── package.json
│   └── tailwind.config.js
│
├── 📂 notebooks/               # Exploratory analysis and result visualisation
│   ├── 01_data_exploration.ipynb
│   ├── 02_cloud_masking_test.ipynb
│   ├── 03_index_analysis.ipynb
│   ├── 04_model_training_unet.ipynb
│   ├── 05_model_training_water.ipynb
│   ├── 06_results_analysis.ipynb
│   └── 07_ecoscore_validation.ipynb
│
├── 📂 models/                  # Saved model weights (DVC remote: GCS)
│   ├── unet_deforestation_v1.pt
│   ├── xgboost_water_stress_v1.pkl
│   └── cnn_pollution_v1.pt
│
├── 📂 tests/                   # Unit + integration tests
│   ├── test_preprocessing.py
│   ├── test_models.py
│   ├── test_ecoscore.py
│   └── test_api.py
│
├── 📂 docs/                    # Documentation and report
│   ├── PAIBS_Report.docx
│   ├── methodology_whitepaper.pdf
│   └── api_schema.json
│
├── .env.example                # Environment variable template
├── .gitignore
├── .dvcignore
├── dvc.yaml                    # DVC pipeline definition
├── environment.yml             # Conda environment
├── requirements.txt            # Pip dependencies
├── Dockerfile                  # Full project Docker container
└── README.md                   # This file
```

---

## ⚡ Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/irenecavalle/ecotrace-core.git
cd ecotrace-core

# 2. Create conda environment
conda env create -f environment.yml
conda activate ecotrace

# 3. Copy and fill environment variables
cp .env.example .env
# → Edit .env with your GEE credentials and GCS bucket name

# 4. Authenticate with Google Earth Engine
python src/ingestion/gee_auth.py

# 5. Pull processed data (DVC)
dvc pull

# 6. Run inference on sample suppliers
python src/inference/run_inference.py --input data/suppliers/suppliers_sample.csv

# 7. Start the API
cd src/api && flask run --port 5000

# 8. Start the dashboard
cd dashboard && npm install && npm run dev
```

---

## 🔧 Installation

### Prerequisites

- Python 3.10+
- Node.js 18+
- Google Earth Engine account (free academic)
- Conda or pip

### Option A — Conda (recommended)

```bash
conda env create -f environment.yml
conda activate ecotrace
```

### Option B — Pip

```bash
pip install -r requirements.txt
```

### Option C — Docker

```bash
docker build -t ecotrace .
docker run -p 5000:5000 --env-file .env ecotrace
```

---

## 📡 Data

### Satellite Sources

| Product | Resolution | Source | Use |
|---|---|---|---|
| Sentinel-2 L2A | 10m, 13 bands | Google Earth Engine | Deforestation, NDVI, NDWI, pollution |
| Sentinel-1 GRD IW | 10m, VV+VH | Google Earth Engine | Cloud-gap filling, water extent |
| MODIS MOD16A2 | 500m, 8-day | NASA / GEE | Evapotranspiration → Water Stress |
| GRACE-FO L3 | 0.5°, monthly | NASA PO.DAAC | Groundwater anomaly |

### Areas of Interest (AOIs)

| AOI | Bounding Box | Area | Key Risk |
|---|---|---|---|
| Indus Basin, Pakistan | 25°N–34.5°N, 66.5°E–74.5°E | ~198,000 km² | Water stress, dye pollution |
| Yangtze Delta, China | 29°N–32°N, 118°E–122°E | ~35,000 km² | Industrial effluent |
| Dhaka Region, Bangladesh | 23°N–24.5°N, 89.5°E–91.5°E | ~12,000 km² | Deforestation, water pollution |

### Supplier Input Format

Place your supplier CSV at `data/suppliers/suppliers.csv`:

```csv
supplier_id,name,country,latitude,longitude,category
SUP001,Mehran Textile Mills,PK,31.418,73.079,Cotton weaving
SUP002,Yangtze Fiber Co.,CN,32.061,118.796,Polyester
SUP003,Green Stitch Ltd.,BD,23.990,90.411,Garment assembly
```

### Downloading EO Data

```bash
# Download Sentinel-2 monthly composites for all AOIs
python src/ingestion/download_sentinel2.py \
  --aoi pakistan \
  --start 2019-01 \
  --end 2024-12 \
  --output data/raw/sentinel2/

# Download all AOIs at once
python src/ingestion/download_sentinel2.py --aoi all --start 2019-01 --end 2024-12
```

---

## 🔄 Pipeline

The full pipeline runs end-to-end via DVC:

```bash
dvc repro
```

Or step-by-step:

```bash
# Step 1 — Cloud masking (SCL band, >50% cloud scenes discarded)
python src/preprocessing/cloud_mask.py --input data/raw/sentinel2/ --output data/processed/masked/

# Step 2 — Monthly median compositing
python src/preprocessing/monthly_composite.py --input data/processed/masked/ --output data/processed/composites/

# Step 3 — Compute spectral indices (NDVI, NDWI, NDBI, RE-ChlI)
python src/preprocessing/compute_indices.py --input data/processed/composites/ --output data/processed/indices/

# Step 4 — Extract 64×64 patches per supplier location
python src/preprocessing/patch_generator.py \
  --suppliers data/suppliers/suppliers.csv \
  --imagery data/processed/indices/ \
  --output data/processed/patches/ \
  --radius 10  # km radius around GPS coordinate

# Step 5 — Run inference (all three models)
python src/inference/run_inference.py \
  --patches data/processed/patches/ \
  --output results/scores.json

# Step 6 — Generate Evidence Packs
python src/inference/evidence_pack.py --scores results/scores.json --output results/evidence_packs/
```

---

## 🤖 Models

### Model 1 — Deforestation Detection (U-Net)

| | |
|---|---|
| **Architecture** | U-Net with ResNet-50 encoder |
| **Pre-training** | ImageNet → fine-tuned on SEN12MS |
| **Input** | 64×64×12 (bi-temporal Sentinel-2 patch pair, 6 bands each) |
| **Output** | Binary segmentation mask (deforested / not) |
| **F1-Score** | 0.87 · IOU 0.81 |

```bash
# Train from scratch
python src/training/train_unet.py --config src/training/config/unet_config.yaml

# Or fine-tune from checkpoint
python src/training/train_unet.py --config src/training/config/unet_config.yaml \
  --checkpoint models/unet_deforestation_v1.pt
```

### Model 2 — Water Stress Classification (XGBoost)

| | |
|---|---|
| **Architecture** | XGBoost Gradient Boosting Classifier |
| **Input** | 96-feature vector (8 indices × 12 months) |
| **Output** | 4-class stress level: None / Low / Medium / High |
| **Accuracy** | 84% · F1-macro 0.79 |

```bash
python src/training/train_xgboost.py --config src/training/config/xgboost_config.yaml
```

### Model 3 — Pollution Proxy (CNN Regressor)

| | |
|---|---|
| **Architecture** | 5-layer CNN encoder + Global Average Pooling + MLP |
| **Input** | 64×64×4 (NDWI, RE-ChlI, turbidity, NIR) |
| **Output** | Continuous anomaly score 0–1 |
| **Pearson r** | 0.82 · RMSE 0.09 |

```bash
python src/training/train_cnn.py --config src/training/config/cnn_config.yaml
```

### Running Inference

```bash
# Score a single supplier
python src/inference/run_inference.py --supplier_id SUP001

# Score all suppliers in CSV
python src/inference/run_inference.py --input data/suppliers/suppliers.csv

# Output: results/scores.json
# {
#   "SUP001": {
#     "ecoscore": 28,
#     "deforestation_risk": 22,
#     "water_stress": 31,
#     "pollution_proxy": 35,
#     "status": "CRITICAL",
#     "updated": "2025-05-01"
#   }
# }
```

---

## 📊 Dashboard

The React dashboard (built with Lovable, Tailwind CSS, Recharts) runs separately:

```bash
cd dashboard
npm install
npm run dev         # Development → http://localhost:5173
npm run build       # Production build
```

**Key views:**
- `/` — Supply Chain Overview (KPI strip, supplier table, gauge panel)
- `/suppliers` — Full supplier list with filtering
- `/map` — Satellite risk map (Mapbox GL JS)
- `/alerts` — Active risk alerts feed
- `/export` — CSRD report generation
- `/qr/:supplier_id` — Public consumer QR landing page

---

## 🔌 API

The Flask API exposes EcoScore data for dashboard consumption and external integrations.

```bash
cd src/api
flask run --port 5000
```

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/suppliers` | List all suppliers with current EcoScore |
| `GET` | `/api/v1/suppliers/{id}` | Single supplier full detail |
| `GET` | `/api/v1/suppliers/{id}/score` | EcoScore + sub-scores JSON |
| `GET` | `/api/v1/alerts` | Active risk alerts |
| `GET` | `/api/v1/export/csrd` | CSRD-formatted JSON export |
| `GET` | `/api/v1/qr/{id}` | Public consumer page data |
| `POST` | `/api/v1/suppliers` | Add new supplier (with CSV upload) |

### Example Request

```bash
curl http://localhost:5000/api/v1/suppliers/SUP001/score
```

```json
{
  "supplier_id": "SUP001",
  "name": "Mehran Textile Mills",
  "country": "PK",
  "ecoscore": 28,
  "sub_scores": {
    "deforestation_risk": 22,
    "water_stress": 31,
    "pollution_proxy": 35
  },
  "status": "CRITICAL",
  "confidence": 0.91,
  "eo_date": "2025-05-01",
  "satellite": "Sentinel-2 L2A"
}
```

---

## 📈 Results

| Model | Metric | EcoTrace | Baseline |
|---|---|---|---|
| Deforestation Detection | F1 / IOU | **0.87 / 0.81** | 0.71 / 0.63 |
| Water Stress Classification | Accuracy / F1-macro | **84% / 0.79** | 61% / 0.54 |
| Pollution Proxy | RMSE / Pearson r | **0.09 / 0.82** | 0.19 / 0.61 |
| EcoScore vs Higg Index (n=42) | Pearson r | **0.79** (p<0.001) | — |

---

## 🔑 Environment Variables

Copy `.env.example` to `.env` and fill in:

```env
# Google Earth Engine
GEE_SERVICE_ACCOUNT=ecotrace@your-project.iam.gserviceaccount.com
GEE_KEY_FILE=secrets/gee_key.json

# Google Cloud Storage (for DVC remote)
GCS_BUCKET=ecotrace-data
GOOGLE_APPLICATION_CREDENTIALS=secrets/gcs_key.json

# Flask API
FLASK_ENV=development
DATABASE_URL=postgresql://localhost:5432/ecotrace
SECRET_KEY=your-secret-key-here

# Mapbox (dashboard map)
VITE_MAPBOX_TOKEN=pk.your_mapbox_token_here

# MLflow experiment tracking
MLFLOW_TRACKING_URI=http://localhost:5001
```

> ⚠️ **Never commit `.env` or `secrets/` to git.** Both are in `.gitignore`.

---

## 🧪 Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=src --cov-report=html

# Run specific module
pytest tests/test_ecoscore.py -v
```

Current coverage: **74%**

---

## 📦 Key Dependencies

```
# AI / ML
torch==2.1.0
torchvision==0.16.0
xgboost==1.7.6
scikit-learn==1.3.2
shap==0.44.0

# Earth Observation
earthengine-api==0.1.390
rasterio==1.3.9
geopandas==0.14.1
shapely==2.0.2

# Data
numpy==1.26.2
pandas==2.1.3
dvc[gs]==3.30.1

# API
flask==3.0.0
flask-cors==4.0.0

# Experiment tracking
mlflow==2.9.2

# PDF generation (Evidence Pack)
reportlab==4.0.7
```

---

## 🌿 Git Workflow

```bash
# Feature branches
git checkout -b feature/deforestation-model
git checkout -b feature/water-stress
git checkout -b feature/dashboard
git checkout -b feature/api

# Commit convention
git commit -m "feat: add U-Net bi-temporal change detection"
git commit -m "fix: cloud mask threshold for monsoon months"
git commit -m "data: add Dhaka AOI Sentinel-2 composites"
git commit -m "docs: update API endpoint documentation"
```

Branches: `main` · `develop` · `feature/*` · `hotfix/*`

---

## 👥 Team

| Name | Role | Focus Area |
|---|---|---|
| Irene Cavalle | ML Lead | U-Net deforestation model, GEE pipeline |
| Gabi | Data Engineer | Preprocessing, DVC, cloud masking |
| Adam | Full-Stack | Dashboard, API, deployment |
| Lucia Pursals | Business / PM | Stakeholder validation, CSRD alignment |
| Lucia Tortajada | Research & Data | Model validation, EcoScore methodology |

---

## 📚 References

1. Hansen, M.C. et al. (2013). High-resolution global maps of 21st-century forest cover change. *Science*, 342(6160), 850–853.
2. Schmitt, M. et al. (2019). SEN12MS — A Curated Dataset of Georeferenced Multi-Spectral Sentinel-1/2 Imagery. *ISPRS Annals*, IV-2/W7.
3. Ellen MacArthur Foundation (2023). *Redesigning Fashion's Future*.
4. EU CSRD — ESRS E2/E3/E4 Standards (2024). European Commission.
5. Open Apparel Registry (2024). Global Factory Database v4.2.
6. IWMI (2023). *Water Security in South Asia*. International Water Management Institute.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built at ESADE Business School · PAIBS 2025 · Do Good. Do Better.*