# Data Documentation

## Addis Ababa, Ethiopia: Rapid Urbanization Sustainability Challenges

## 1. Overview
This directory documents the geospatial, environmental, transportation, and socioeconomic datasets used to construct a composite Environmental Sustainability Risk Index for Addis Ababa.

The analysis combines raster processing, spatial joins, indicator normalization, spatial autocorrelation, and statistical modeling to examine geographic patterns of environmental sustainability risk.

The original research datasets exceed 1 GB and are not included in this public repository. Selected aggregated research outputs are provided in the public/ directory.

## 2. Data Sources
| Dataset | Research purpose | Local folder |
|---|---|---|
| Addis Ababa woreda boundaries | Define 116 geographic analysis units | `aa_worda_boundary/` |
| WorldPop 2020 population raster | Calculate population and population density | `eth_general_2020_geotiff/` |
| Global Human Settlement Layer (GHSL) | Estimate built-up area and urban development | `GHS_BUILT_S_E2020_GLOBE_R2023A_54009_100_V1_0_R8_C22/` |
| OpenStreetMap road network | Calculate road length and density | `ethiopia-260306-free.shp/` |
| Anbessa City Bus GTFS | Identify public transportation stops | `anbessacitybusserviceenterprise_gtfs/` |
| Sheger City Bus GTFS | Identify public transportation stops | `shegercitybus_gtfs/` |
| Minibus Taxi GTFS | Identify public transportation stops | `minibustaxi_gtfs/` |
| Addis Ababa NDVI raster (2020) | Measure vegetation conditions | `addisNdvi/` |
| Ethiopia health facilities | Calculate health facility density | `Ethiopia_HealthFacility/` |
| OpenStreetMap education facilities | Calculate education facility density | `hotosm_eth_education_facilities_polygons_shp/` |
| Ethiopia household socioeconomic survey | Estimate household consumption and reported health concerns | `ETH_2021_ESPS-W5_v02_M_CSV/` |

**Source references:** The project uses data associated with WorldPop, GHSL, OpenStreetMap, GTFS transport feeds, and Ethiopian socioeconomic surveys. Original dataset download pages, versions, dates, and redistribution licenses should be verified against the research report and original download records before this is treated as a complete source manifest.

## 3. Environmental Sustainability Indicators

Five indicators contribute to the composite risk index:

1. **Population density:** Estimated population per square kilometer.
2. **Road density:** Total road length per square kilometer.
3. **Built-up percentage:** Estimated built-up area relative to woreda area.
4. **Transportation stop density:** Number of public transportation stops per square kilometer.
5. **Vegetation (NDVI):** Mean vegetation index, inverted to represent vegetation-related risk.

Selected skewed indicators undergo logarithmic transformation, and the analysis applies min-max scaling to specified variables. The composite index uses equal weights across its five components.

Higher index scores indicate greater estimated environmental sustainability risk under the study's operational definition.

## 4. Additional Socioeconomic Variables

The research also examines variables external to the composite index:

- Average annual household consumption per adult equivalent, used as an economic proxy.
- Education facility density.
- Health center density.
- Reported health concerns.

These variables support Ordinary Least Squares (OLS) and Spatial Lag Model (SLM) analysis. Their estimated relationships with sustainability risk are interpreted as statistical associations, not causal effects.

## 5. Public Research Data

The `public/` directory contains:

### `addis_ababa_woreda_public.geojson`

A simplified geographic dataset designed for interactive visualization on the research website.

It contains woreda boundaries and selected aggregated environmental and spatial analysis results.

The dataset supports:

- Interactive sustainability risk mapping.
- Woreda-level comparisons.
- Visualization of environmental indicators.
- Exploration of spatial clustering patterns.

The public GeoJSON excludes original household-level survey records and large source rasters.

**Important:** Published risk scores represent the original research results. The GeoJSON does not independently recompute or validate the index.

## 6. Reproducing the Analysis

The main research program is located at `Code/spatialAnalysis.py`, and Python dependencies are listed in `requirements.txt`.

The program expects the following project structure:

```text
addis-ababa-sustainability/
├── Code/
│   └── spatialAnalysis.py
├── Data/
│   ├── aa_worda_boundary/
│   ├── eth_general_2020_geotiff/
│   ├── addisNdvi/
│   ├── [other original dataset folders]/
│   ├── public/
│   │   └── addis_ababa_woreda_public.geojson
│   └── README.md
├── Results/
└── requirements.txt
```

To reproduce the analysis:

1. Obtain the original datasets from their respective providers, subject to access and licensing conditions.
2. Organize the input files according to the paths specified in `spatialAnalysis.py`.
3. Install the Python dependencies using `pip install -r requirements.txt` from the repository root.
4. Confirm that input filenames, coordinate reference systems, and data versions match the research configuration.
5. Execute the main analysis workflow to generate indicator calculations, statistical outputs, and visualizations.

**Note:** The current script may require its main execution entry point to be enabled before running directly.

## 7. Data Management and Limitations

Original datasets are excluded from the public repository to reduce storage requirements and avoid redistribution of potentially restricted data.

The analysis combines sources with different spatial resolutions, collection dates, and geographic coverage. These differences may affect comparability and interpretation.

Household survey data may not represent every woreda equally. Aggregated estimates should therefore be interpreted with appropriate caution.

The composite index is intended as an exploratory planning and research tool rather than a definitive measure of environmental conditions or policy effectiveness.

## 8. Research Documentation

The complete research report and presentation are available in the repository's `docs/` directory. They provide additional details on the methodology, exploratory analysis, spatial statistics, regression models, findings, and limitations.
