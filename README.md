# EmberTrace

NASA Space Apps project for **Harmonization of MODIS and VIIRS Hot Spots**.

This local Streamlit demo compares September–November FIRMS hotspot detections in a Punjab–Haryana study rectangle for 2023–2025. It preserves raw sensor views and reports an experimental VIIRS-to-MODIS reference-scale baseline. MODIS is a reference sensor here, **not ground truth**.

## Run locally

Python 3.11 or newer is required. From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python pipeline.py
python -m streamlit run app.py
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`, then run the same two `python` commands. Open the local URL printed by Streamlit, normally `http://localhost:8501`.

The six original FIRMS CSVs are included unchanged in `data/raw/`. Processing is local. Internet access is needed only to install packages and load map tiles.

## Implemented method

- Geography: 73.7–77.8° E and 27.5–32.7° N. This rectangle includes neighboring regions and is not clipped to state boundaries.
- Season: September 1–November 30, divided into 13 fixed seven-day bins anchored on September 1.
- Default filters: MODIS confidence >=30; VIIRS nominal/high confidence; FIRMS type 0 for both. These confidence rules are not equivalent between sensors, and type 0 does not prove crop-residue burning.
- Supported platforms: Aqua and Terra are explicitly assigned to MODIS; SNPP is explicitly assigned to VIIRS. Missing or unknown satellite labels stop processing instead of being silently classified.
- Baseline: a non-negative least-squares slope through the origin converts weekly VIIRS counts to an **Experimental MODIS-reference activity estimate**.
- Training: the 26 weekly pairs from 2023–2024 only.
- Holdout evaluation: the 13 weekly pairs from 2025 only. No model fitting or parameter tuning uses 2025.

With the default filters, the current fitted factor is approximately `0.2755`. The 2025 weekly MAE is approximately `506.46` for unadjusted VIIRS and `167.68` for the experimental reference-scale estimate. MAE measures numerical disagreement with MODIS-reference weekly counts; it does not measure accuracy against true fire occurrence.

## Sensor comparability diagnostics

The app reports satellite composition and detection-weighted daytime acquisition-time medians. These are **detection-based diagnostics, not observation coverage**.

The included MODIS records are overwhelmingly Aqua, with a small Terra contribution; the included VIIRS records are SNPP only. Aqua's detection-weighted daytime acquisition time shifts later across the three seasons, while SNPP is more stable. The changing separation can confound count comparisons because fire activity, clouds, and detectability can change between passes.

These hotspot exports do not provide observation opportunities, clear-sky masks, or reliable non-detection records. A missing or unmatched observation is therefore unknown and remains distinct from a confirmed observed zero. A zero in the weekly calendar means only that no retained detection was recorded in that bin.

## App views and exports

The app provides:

- Raw MODIS and raw VIIRS weekly calendars.
- The Experimental MODIS-reference activity estimate.
- Filtered hotspot maps by year, month, and sensor.
- Raw and experimental weekly comparison charts.
- 2025 holdout MAE comparisons against simple baselines.
- A selected-hotspot CSV export and a weekly-analytics CSV export.

## Limitations

- Hotspots are detections, not unique fires, and repeated passes may record the same event.
- There is no observation/clear-sky coverage mask, cloud correction, spatial-resolution correction, or matched-overpass model.
- Weekly aggregation mixes acquisition times and platforms; changing acquisition times confound sensor comparison.
- The experimental scale does not create sensor-independent fire counts and is not scientifically validated harmonization.
- Seasonal changes do not establish a causal pollution reduction. No AQI estimate, forecast, or statistical-significance claim is made.
- The study uses only three autumn seasons, predominantly Aqua MODIS detections and SNPP-only VIIRS detections.
- The prevention use case—timing preparation and outreach from historical seasonality—has not been validated with intended users. Historical fires alone do not predict future fires.

Data source: [NASA FIRMS Archive Download](https://firms.modaps.eosdis.nasa.gov/download/).
