# -*- coding: utf-8 -*-
"""
Description: This code reads .shp, .tif, & .csv files reprojects polygons and
spatially joins geo dataframes. Calculations are then conducted on key 
variables; 
    population density, road density, transportation denstiy, built 
    percentage, average NDVI, count of education facilities, count of health 
    centers, count of flagged health concerns, & average income
Plots produced for variables: scatter plot, box plot, heat map, LISA map
choropleth map, normal distribution histogram.
Normalization methods: log transform & min-max
Spatial autocorrelation methods: Global Moran's I & LISA
Models: Ordinary Least Squares (OLS) & Spatial Lag Model (SLM)

main() function runs the main program
Output:
    print outs of coordinate reference systems (CRS) of spatial data,
    results of Global Moran's I index,
    results of OLS & SLM
    saves plots & final dataframe excel file
    
Required folder structure:
    Code - store the main code
    Data - data files
    Results - results output

Author: Tegist Worku
Course: DA 790 Data Analytics Capstone
Date: May 8 2026
"""

import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path
import geopandas as gpd
import rasterio
from rasterstats import zonal_stats
from shapely.geometry import Point
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from esda.moran import Moran, Moran_Local
from splot.esda import plot_local_autocorrelation
from libpysal.weights import Queen
import statsmodels.api as sm
from spreg import ML_Lag
import warnings
warnings.filterwarnings("ignore")


# ------------------------------------------
# Paths
# ------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent/"Data"
RESULTS_DIR = BASE_DIR.parent/"Results"

# ------------------------------------------
# File loading functions
# ------------------------------------------

# Used to load spatial data files .shp


def loadVector(folder, filename):
    file_path = DATA_DIR / folder / filename
    return gpd.read_file(file_path)

# Used to load .tif files (tagged image file format),
# high quality image files


def loadRaster(folder, filename):
    file_path = DATA_DIR / folder / filename
    with rasterio.open(file_path) as src:
        raster_crs = src.crs
        nodata = src.nodata
    return raster_crs, nodata, file_path

# CSV files with geo location data


def loadCsv(folder, filename):
    file_path = DATA_DIR / folder / filename
    df = pd.read_csv(file_path)
    return df

# ------------------------------------------
# Helper functions
# ------------------------------------------

# Converts stops lat/lon to GeoDataFrame


def gtfsStopsToGdf(stops_df):
    stops_df = stops_df.dropna(subset=["stop_lat", "stop_lon"])
    geometry = [
        Point(lon, lat)
        for lon, lat in zip(stops_df["stop_lon"], stops_df["stop_lat"])]

    stops_gdf = gpd.GeoDataFrame(
        stops_df,
        geometry=geometry,
        crs="EPSG:4326")

    return stops_gdf
# ------------------------------------------
# Compute indicators
# ------------------------------------------


def computePopDensity(aa_woreda):
    pop_crs, pop_nodata, pop_path = loadRaster(
        "eth_general_2020_geotiff",
        "eth_general_2020.tif")

    print('Population CRS:', pop_crs)

    # Reproject polygons to match raster CRS
    aa_woreda = aa_woreda.to_crs(pop_crs)

    # Run zonal statistics, 'sum adds all population pixels inside each woreda
    stats = zonal_stats(aa_woreda,
                        pop_path,
                        stats=["sum"],
                        nodata=-99999)

    # Apply totals to new population column
    aa_woreda['population'] = [s["sum"] for s in stats]
    aa_woreda['population'] = aa_woreda['population'].round().astype(int)

    # Use UTM for area calculation
    aa_woreda = aa_woreda.to_crs(epsg=32637)

    # Calculate area directly from geometry in sq km
    aa_woreda['area_km2'] = aa_woreda.geometry.area / 1000000

    # (3) Calculate population density, people per km^2
    aa_woreda['pop_density'] = aa_woreda['population'] / aa_woreda['area_km2']

    # Inspect result
    # print(aa_woreda[['Sub_City', 'Woreda', 'population',
    #       'area_km2', 'pop_density']].head())
    # print(aa_woreda[["population", "area_km2", "pop_density"]].describe())

    return aa_woreda


def computeRoadDensity(aa_woreda):
    # (4) Load road .shp file
    roads_df = loadVector("ethiopia-260306-free.shp",
                          "gis_osm_roads_free_1.shp")

    print('Roads CRS:', roads_df.crs)
    # print(roads_df.columns)

    # Limiting to vehicle specific road types
    roads_df = roads_df[roads_df["fclass"].isin([
        "motorway",
        "primary",
        "secondary",
        "tertiary",
        "residential",
        "unclassified",
        "service",
        "trunk",
        "trunk_link",
        "primary_link",
        "secondary_link",
        "tertiary_link",
        "motorway_link"
    ])].copy()

    # Reproject both layers to UTM zone 37N for accurate length/area
    roads_utm = roads_df.to_crs(epsg=32637)
    aa_woreda_utm = aa_woreda.to_crs(epsg=32637)

    # Intersect roads with woreda polygons
    road_segments = gpd.overlay(roads_utm, aa_woreda_utm[['Sub_City', 'Woreda',
                                                          'geometry']],
                                how='intersection')

    # Calculate road segement length in km
    road_segments['road_km'] = road_segments.geometry.length/1000

    # Sum road length by woreda
    road_length_by_woreda = (road_segments
                             .groupby(['Sub_City', 'Woreda'],
                                      as_index=False)['road_km']
                             .sum())

    # Merge to woreda table
    aa_woreda = aa_woreda.merge(road_length_by_woreda,
                                on=['Sub_City', 'Woreda'],
                                how='left')

    # Fill woredas with no roads as 0
    aa_woreda["road_km"] = aa_woreda["road_km"].fillna(0)

    # (5) Road density = total road km / area km²
    aa_woreda["road_density"] = aa_woreda["road_km"] / aa_woreda["area_km2"]

    # Inspect
    # print(aa_woreda[["Sub_City", "Woreda", "road_km",
    #       "area_km2", "road_density"]].head())
    # print(aa_woreda[["road_km", "road_density"]].describe())

    return aa_woreda


def computeUrbanDensity(aa_woreda):
    # (6) Load urbanization .tif file
    urban_crs, urban_nodata, urban_path = loadRaster(
        "GHS_BUILT_S_E2020_GLOBE_R2023A_54009_100_V1_0_R8_C22",
        "GHS_BUILT_S_E2020_GLOBE_R2023A_54009_100_V1_0_R8_C22.tif")

    print('Built-up CRS:', urban_crs)
    # Reproject woreda polygons to match urban raster CRS
    aa_woreda_built = aa_woreda.to_crs(urban_crs)

    # Zonal statistics for built-up raster
    built_stats = zonal_stats(aa_woreda_built,
                              urban_path,
                              stats=['mean', 'sum'],
                              nodata=65535)

    # New columns for built-up mean and sum by woreda
    aa_woreda['built_mean'] = [s['mean'] for s in built_stats]
    aa_woreda['built_sum'] = [s['sum'] for s in built_stats]

    aa_woreda['built_area_km2'] = aa_woreda['built_sum'] / 1000000
    aa_woreda['built_pct'] = ((aa_woreda['built_area_km2'] /
                               aa_woreda['area_km2']) * 100).round()

    return aa_woreda


def computeTransportDensity(aa_woreda):
    # Load GTFS stops from 3 Addis transport feeds
    anbessa_stops = loadCsv('anbessacitybusserviceenterprise_gtfs',
                            'stops.txt')
    sheger_stops = loadCsv('shegercitybus_gtfs', 'stops.txt')
    minibus_stops = loadCsv('minibustaxi_gtfs', 'stops.txt')

    # Add source labels
    anbessa_stops['operators'] = 'Anbessa'
    sheger_stops['operators'] = 'Sheger'
    minibus_stops['operators'] = 'Minibus'

    # Combine
    all_stops = pd.concat(
        [anbessa_stops, sheger_stops, minibus_stops],
        ignore_index=True)

    # Convert to GeoDataFrame
    stops_gdf = gtfsStopsToGdf(all_stops)

    print('Stops CRS:', stops_gdf.crs)
    aa_woreda = aa_woreda.to_crs(stops_gdf.crs)

    stops_gdf = stops_gdf.drop_duplicates(subset=['stop_lat', 'stop_lon'])

    # Spatial join: assign each stop to a woreda
    stops_join = gpd.sjoin(stops_gdf,
                           aa_woreda[['Sub_City', 'Woreda', 'geometry']],
                           how='left',
                           predicate='within')

    # Count stops per woreda
    stop_counts = (stops_join.groupby(['Sub_City', 'Woreda'], as_index=False)
                   .size()
                   .rename(columns={'size': 'stop_count'}))

    # Merge back
    aa_woreda = aa_woreda.merge(
        stop_counts,
        on=['Sub_City', 'Woreda'],
        how='left')

    aa_woreda['stop_count'] = aa_woreda['stop_count'].fillna(0).astype(int)

    # Calculate transport density
    aa_woreda['transport_density'] = aa_woreda['stop_count'] / \
        aa_woreda['area_km2']

    return aa_woreda


def computeNdvi(aa_woreda):
    ndvi_crs, ndvi_nodata, ndvi_path = loadRaster("addisNdvi",
                                                  "Addis_NDVI_2020.tif")
    print("NDVI CRS:", ndvi_crs)

    # Reproject woreda polygons to match NDVI CRS
    aa_woreda_ndvi = aa_woreda.to_crs(ndvi_crs)

    # Run zonal stats
    ndvi_stats = zonal_stats(aa_woreda_ndvi,
                             ndvi_path,
                             stats=['mean', 'sum'],
                             nodata=99999)

    # Apply stats to new NDVI columns
    aa_woreda['sum_NDVI'] = [s['sum'] for s in ndvi_stats]
    aa_woreda['mean_NDVI'] = [s['mean'] for s in ndvi_stats]

    aa_woreda['ndvi_area_km2'] = aa_woreda['sum_NDVI']/1000000

    # Inspect results
    # print(aa_woreda[['sum_NDVI','mean_NDVI','ndvi_area_km2']].head())
    # print(aa_woreda[['sum_NDVI','mean_NDVI']].describe())

    return aa_woreda


def compositeIndicators():
    aa_woreda = loadVector("aa_worda_boundary", "aa_worda_boundary.shp")
    print("Woreda CRS:", aa_woreda.crs)
    aa_woreda = computePopDensity(aa_woreda)
    aa_woreda = computeRoadDensity(aa_woreda)
    aa_woreda = computeUrbanDensity(aa_woreda)
    aa_woreda = computeTransportDensity(aa_woreda)
    aa_woreda = computeNdvi(aa_woreda)

    return aa_woreda

# ------------------------------------------
# Additional socioeconomic variables
# ------------------------------------------


def computeHealthCenterDensity(composite_df):
    health_df = loadVector('Ethiopia_HealthFacility',
                           'Ethiopia_HealthFacility.shp')

    print('Health CRS:', health_df.crs)
    # print(health_df.columns)

    health_points = health_df.to_crs(epsg=4326)

    health_centers = gpd.sjoin(health_points, composite_df, predicate="within")

    # Count health centers by woreda
    health_centers_by_woreda = (health_centers
                                .groupby(["Sub_City", "Woreda"],
                                         as_index=False)['name'].count())

    # Merge to woreda table
    composite_df = composite_df.merge(health_centers_by_woreda,
                                      on=['Sub_City', 'Woreda'],
                                      how='left')

    composite_df = composite_df.rename(columns={'name': 'health_center_count'})
    composite_df['health_center_count'] = \
        composite_df['health_center_count'].fillna(0)

    composite_df['health_center_density'] = composite_df['health_center_count'] / \
        composite_df['area_km2']

    return composite_df


def computeEduFacilitiesDensity(composite_df):
   # Load edu facilities shp files
   edu_points = loadVector('hotosm_eth_education_facilities_polygons_shp',
                           'hotosm_eth_education_facilities_polygons_shp.shp')

   print('Education CRS:', edu_points.crs)
   # Join spatial data frame with woreda gdf
   edu_centers = gpd.sjoin(edu_points, composite_df, predicate="within")

   # Count education facilities by woreda
   edu_facilities_by_woreda = (edu_centers
                               .groupby(["Sub_City", "Woreda"],
                                        as_index=False)['osm_id'].count())

   # Merge to woreda table
   composite_df = composite_df.merge(edu_facilities_by_woreda,
                                     on=['Sub_City', 'Woreda'],
                                     how='left')
   # Rename columns and fill na
   composite_df.rename(
       columns={'osm_id': 'edu_facilities_count'}, inplace=True)
   composite_df['edu_facilities_count'] = \
       composite_df['edu_facilities_count'].fillna(0)
   # Compute edu facilities density
   composite_df['edu_facilities_density'] = \
       composite_df['edu_facilities_count'] / composite_df['area_km2']

   return composite_df


def computeHealthConcern(composite_df):
    # Read health concerns & survey household location file
    health = loadCsv('ETH_2021_ESPS-W5_v02_M_CSV',
                     'sect3_hh_w5.csv')
    poly_var = loadCsv('ETH_2021_ESPS-W5_v02_M_CSV',
                       'eth_plotgeovariables_y5.csv')

    # Select key columns
    health = health[['household_id', 's3q05', 's3q06_1']]
    poly_var = poly_var[['household_id', 'lat_dd_mod', 'lon_dd_mod']]

    # Merge two survey files on household id
    health_concern = health.merge(poly_var,
                                  on='household_id',
                                  how='left')

    # Convert df to geo dataframe with matching woreda crs
    health_gdf = gpd.GeoDataFrame(health_concern,
                                  geometry=gpd.points_from_xy(
                                      health_concern['lon_dd_mod'],
                                      health_concern['lat_dd_mod']),
                                  crs='EPSG:4326')

    # Spatial join with woreda geo df
    health_joined = gpd.sjoin(health_gdf,
                              composite_df,
                              how='right',
                              predicate='within')

    # Count health concerns by woreda
    health_concerns_by_woreda = (health_joined.groupby(['Sub_City', 'Woreda'],
                                                       as_index=False)
                                 ['s3q06_1'].count())
    # Rename column
    health_concerns_by_woreda.rename(columns={'s3q06_1': 'health_concern_count'},
                                     inplace=True)
    # Merge to woreda dataframe
    composite_df = composite_df.merge(health_concerns_by_woreda,
                                      on=['Sub_City', 'Woreda'],
                                      how='left')

    return composite_df


def computeIncomeStability(composite_df):
    income_df = loadCsv('ETH_2021_ESPS-W5_v02_M_CSV',
                        'cons_agg_w5.csv')
    poly_var = loadCsv('ETH_2021_ESPS-W5_v02_M_CSV',
                       'eth_plotgeovariables_y5.csv')

    # Select key columns
    # Using nominal annual consumption per adult equivalent for income
    # stability measurement
    income_df = income_df[['household_id', 'nom_totcons_aeq']]
    poly_var = poly_var[['household_id', 'lat_dd_mod', 'lon_dd_mod']]

    # Merge with geo location file
    income_merged = income_df.merge(poly_var,
                                    on='household_id',
                                    how='left')

    # Convert to geo dataframe with matching woreda crs
    income_gdf = gpd.GeoDataFrame(income_merged,
                                  geometry=gpd.points_from_xy(
                                      income_merged['lon_dd_mod'],
                                      income_merged['lat_dd_mod']),
                                  crs='EPSG:4326')

    # Spatial join with woreda geo df
    income_joined = gpd.sjoin(income_gdf,
                              composite_df,
                              how='right',
                              predicate='within')

    # Average income by woreda
    average_income_by_woreda = (income_joined.groupby(['Sub_City', 'Woreda'],
                                                      as_index=False)
                                ['nom_totcons_aeq'].mean())

    average_income_by_woreda['nom_totcons_aeq'] = \
        average_income_by_woreda['nom_totcons_aeq'].fillna(0)

    average_income_by_woreda.rename(columns={'nom_totcons_aeq': 'avg_income'},
                                    inplace=True)

    # Merge with woreda df
    composite_df = composite_df.merge(average_income_by_woreda,
                                      on=['Sub_City', 'Woreda'],
                                      how='left')

    return composite_df


def additionalIndicators(primary_ind):
    additional_ind = computeHealthCenterDensity(primary_ind)
    additional_ind = computeEduFacilitiesDensity(additional_ind)
    additional_ind = computeHealthConcern(additional_ind)
    additional_ind = computeIncomeStability(additional_ind)

    return additional_ind


# ------------------------------------------
# Exploratory data analysis plots
# ------------------------------------------


def plotNdviByWoreda(final_woreda, save_path=None):
    fig, ax = plt.subplots(figsize=(10, 8))

    aa_plot = final_woreda.to_crs(epsg=32637)

    # Plot mean NDVI by woreda on map
    aa_plot.plot(column='mean_NDVI',
                 cmap='Greens',
                 legend='True',
                 ax=ax)

    # Label woredas by subcity name
    for idx, row in aa_plot.iterrows():
        point = row.geometry.representative_point()

        ax.text(point.x,
                point.y,
                f"{row['Sub_City']}",
                fontsize=6,
                ha='center')

    plt.title('NDVI by Addis Ababa Woreda')

    if save_path:
        fig.savefig(save_path)

    plt.show()


def plotIndicatorHeatmap(final_woreda, save_path=None):
    fig, ax = plt.subplots(figsize=(10, 6))
    # Indicator correlation
    ind_df = pd.DataFrame(final_woreda[['pop_density',
                                        'road_density',
                                        'built_pct',
                                        'transport_density',
                                        'stop_count',
                                        'mean_NDVI']].corr())
    # Heat map for correlation
    # plt.figure(figsize=(10, 8))
    heat_plt = sns.heatmap(ind_df, annot=True)
    heat_plt.xaxis.tick_top()
    plt.title("Indicator Correlation Heat Map")

    if save_path:
        fig.savefig(save_path)

    plt.show()


def plotNormalDistribution(final_woreda, save_path=None):
    key_col = {'pop_density': 'blue',
               'road_density': 'brown',
               'built_pct': 'gray',
               'transport_density': 'red',
               'mean_NDVI': 'green',
               'health_center_density': 'purple',
               'edu_facilities_density': 'teal',
               'health_concern_count': 'pink',
               'avg_income': 'black'}

    fig, axes = plt.subplots(3, 3, figsize=(15, 8))
    axes = axes.flatten()
    for i, (key, value) in enumerate(key_col.items()):
        sns.histplot(final_woreda[key],
                     kde=True,
                     ax=axes[i],
                     color=value)
        axes[i].set_title(key)

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path)

    plt.show()



def plotScatter(final_woreda, save_path=None):
    key_col_dic = {'blue': {'pop_density': 'mean_NDVI'},
                   'brown': {'road_density': 'pop_density'},
                   'gray': {'built_pct': 'road_density'},
                   'red': {'transport_density': 'mean_NDVI'},
                   'orange': {'stop_count': 'mean_NDVI'},
                   'green': {'mean_NDVI': 'built_pct'}
                   }

    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    axes = axes.flatten()

    for i, (parent_key, nested_dict) in enumerate(key_col_dic.items()):
        for key, value in nested_dict.items():
            sns.regplot(data=final_woreda,
                        x=key,
                        y=value,
                        ax=axes[i],
                        color=parent_key)
            axes[i].set_title(f'{key} vs {value}')

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path)

    plt.show()


def plotBoxPlot(final_woreda, save_path=None):
    key_col = {'pop_density': 'blue',
               'road_density': 'brown',
               'built_pct': 'gray',
               'transport_density': 'red',
               'stop_count': 'orange',
               'mean_NDVI': 'green'}

    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    axes = axes.flatten()
    for i, (key, value) in enumerate(key_col.items()):
        sns.boxplot(x=final_woreda[key],
                    ax=axes[i],
                    color=value)
        axes[i].set_title(f'{key}')

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path)

    plt.show()


def generatePlots(geodf):
    try:
        ndvi_fname = 'ndvi_by_woreda.png'
        ndvi_path = RESULTS_DIR / ndvi_fname
        plotNdviByWoreda(geodf, ndvi_path)

        heatmap_fname = 'correlation_heatmap.png'
        heatmap_path = RESULTS_DIR / heatmap_fname
        plotIndicatorHeatmap(geodf, heatmap_path)

        nor_dis_fname = 'normal_distribution.png'
        nor_dis_path = RESULTS_DIR / nor_dis_fname
        plotNormalDistribution(geodf, nor_dis_path)

        scatter_fname = 'scatter.png'
        scatter_path = RESULTS_DIR / scatter_fname
        plotScatter(geodf, scatter_path)

        box_plt_fname = 'boxplot.png'
        box_plt_path = RESULTS_DIR / box_plt_fname
        plotBoxPlot(geodf, box_plt_path)

    except Exception as e:
        return print(f'Unexpected error: {e}')


# ------------------------------------------
# Normalize indicators & compute sustainability risk
# ------------------------------------------


def computeSustainabilityRisk(additional_ind):
    # Use log transform for right skewed indicators to remove
    # effect of extreme values & normalize data
    additional_ind['pop_density_log_base'] = \
        np.log1p(additional_ind['pop_density'])
    additional_ind['transport_density_log_base'] = \
        np.log1p(additional_ind['transport_density'])
    additional_ind['stop_count_log_base'] = \
        np.log1p(additional_ind['stop_count'])
    additional_ind['health_center_log_base'] = \
        np.log1p(additional_ind['health_center_density'])
    additional_ind['edu_facilities_log_base'] = \
        np.log1p(additional_ind['edu_facilities_density'])
    additional_ind['avg_income_log_base'] = \
        np.log1p(additional_ind['avg_income'])
    additional_ind['health_concern_log_base'] = \
        np.log1p(additional_ind['health_concern_count'])

    # Scaler class variable
    scaler = MinMaxScaler()

    # Key cols & log transformed cols
    key_cols = ['pop_density_log_base',
                'road_density',
                'transport_density_log_base',
                'built_pct',
                'stop_count_log_base',
                'health_center_log_base',
                'edu_facilities_log_base',
                'health_concern_log_base',
                'avg_income_log_base']

    # Use min-max scaling to normalize values on 0-1 scale
    df_normalized = additional_ind.copy()
    df_normalized[key_cols] = \
        scaler.fit_transform(df_normalized[key_cols])

    # Inverse indicators with positive effect
    df_normalized['income_inverse'] = 1 - df_normalized['avg_income_log_base']
    df_normalized['edu_fac_inverse'] = 1 - \
        df_normalized['edu_facilities_log_base']
    df_normalized['ndvi_inverse'] = 1 - df_normalized['mean_NDVI']
    df_normalized['health_center_inverse'] = 1 - \
        df_normalized['health_center_log_base']

    # Calculate sustainability risk
    df_normalized['sustainability_risk_index_score'] = (df_normalized['pop_density_log_base'] +
                                                        df_normalized['road_density'] +
                                                        df_normalized['transport_density_log_base'] +
                                                        df_normalized['built_pct'] +
                                                        (1-df_normalized['mean_NDVI']))/5

    return df_normalized

# ------------------------------------------
# Plot normalized indicators & sustainability risk
# ------------------------------------------


def plotNormalizedIndicators(df_norm):
    # Figure dimensions
    fig, axes = plt.subplots(3, 3, figsize=(15, 8))
    axes = axes.flatten()

    # Key column & corresponding chart color dictionary
    cols_dict = {'pop_density_log_base': 'blue',
                 'road_density': 'brown',
                 'built_pct': 'gray',
                 'transport_density_log_base': 'red',
                 'mean_NDVI': 'green',
                 'health_center_log_base': 'purple',
                 'edu_facilities_log_base': 'teal',
                 'health_concern_log_base': 'pink',
                 'avg_income_log_base': 'gray'}

    # Iterate through key columns and plot histogram with normal distribution
    # line
    for i, (key, value) in enumerate(cols_dict.items()):
        sns.histplot(df_norm[key],
                     kde=True,
                     ax=axes[i],
                     color=value)
        axes[i].set_title(key)

    # Charts per col on a single window
    plt.tight_layout()

    # Save plot
    fname = 'normalized_distribution.png'
    save_path = RESULTS_DIR / fname
    fig.savefig(save_path)

    plt.show()


def plotRiskIndex(final_woreda):
    fig, ax = plt.subplots(figsize=(10, 8))

    aa_plot = final_woreda.to_crs(epsg=32637)

    # Plot mean NDVI by woreda on map
    aa_plot.plot(column='sustainability_risk_index_score',
                 cmap='Blues',
                 legend='True',
                 ax=ax)

    # Label woredas by subcity name
    for idx, row in aa_plot.iterrows():
        point = row.geometry.representative_point()

        ax.text(point.x,
                point.y,
                f"{row['Sub_City']}",
                fontsize=6,
                ha='center')

    plt.title('Sustainability Risk by Addis Ababa Woreda')

    risk_plt_fname = 'risk_plot.png'
    risk_plt_path = RESULTS_DIR / risk_plt_fname
    fig.savefig(risk_plt_path)

    plt.show()

# ------------------------------------------
# Spatial analysis
# ------------------------------------------


def spatialAnalysis(df_normalized):
    # Define spatial relationships by determining neighboring woredas
    # using geometry column.
    # Using Queen criteria two locations only need to share a single
    # point to be considered neighbors
    w = Queen.from_dataframe(df_normalized[['geometry']], use_index=False)
    # Apply a row based transformation where the sum of all the neighbors
    # in the observation is one, standardizing the weights
    w.transform = 'r'
    # Use the risk index as a variable to test for spatial clustering
    y = df_normalized['sustainability_risk_index_score']
    # Apply risk index values and neighbor weight to Global Moran's I
    moran = Moran(y, w)
    # Display Moran's I measure & p-value
    print("-----")
    print("Sustainability Risk Spatial Autocorrelation Index")
    print("Moran's I:", moran.I)  # strength of clustering
    print("p-value:", moran.p_sim)  # statistical significance
    print("-----\n")
    print("Independent Variables Spatial Autocorrelation Index")
    # Calculate clustering per woreda
    lisa = Moran_Local(y, w)
    # Create column to store quadrants per woreda & significance of clustering
    df_normalized['cluster'] = lisa.q
    df_normalized['significance'] = lisa.p_sim < 0.05
    # Moran I scatterplot, LISA map, Choropleth map
    plot_local_autocorrelation(lisa,
                               df_normalized,
                               'sustainability_risk_index_score')
    fname = 'autocorrelation_plot.png'
    save_path = RESULTS_DIR / fname
    plt.savefig(save_path)
    plt.show()

    # Clustering patterns for additional variables
    add_var = ['income_inverse',
               'health_center_inverse',
               'edu_fac_inverse',
               'health_concern_count']
    # Run Moran's I and LISA for each variable and plot results
    for i in add_var:
        moran_var = Moran(df_normalized[i], w)
        print(f'{i}')
        print("Moran's I:", moran_var.I)
        print("p-value:", moran_var.p_sim)
        print("-----")
        lisa_var = Moran_Local(df_normalized[i], w)
        colname = f'cluster_{i}'
        df_normalized[colname] = lisa_var.q
        plot_local_autocorrelation(lisa_var, df_normalized, i)
        plt.title(i)
        fname = f'{i}_cluster_plot.png'
        save_path = RESULTS_DIR / fname
        plt.savefig(save_path)
        plt.show()
    # Key columns used to calculate sustainability risk, variables, and
    # local cluster pattern results
    main_columns = [
        'Sub_City',
        'Woreda',
        'Shape_Area',
        'geometry',
        'road_density',
        'built_pct',
        'pop_density_log_base',
        'transport_density_log_base',
        'stop_count_log_base',
        'sustainability_risk_index_score',
        'avg_income',
        'health_concern_count',
        'avg_income_log_base',
        'health_concern_log_base',
        'health_center_log_base',
        'edu_facilities_log_base',
        'income_inverse',
        'edu_fac_inverse',
        'ndvi_inverse',
        'health_center_inverse',
        'cluster',
        'significance',
        'cluster_income_inverse',
        'cluster_health_center_inverse',
        'cluster_edu_fac_inverse',
        'cluster_health_concern_count']

    df_normalized = df_normalized[main_columns]

    return df_normalized

# ------------------------------------------
# Models
# ------------------------------------------


def models(final_df):
    # Ordinary Least Squares
    # Dependent variable
    y = final_df['sustainability_risk_index_score']
    # Independent variables
    x = final_df[['avg_income_log_base',
                  'edu_facilities_log_base',
                  'health_center_log_base',
                  'health_concern_log_base']]
    # Use independent variables as constant
    x = sm.add_constant(x)
    # Apply variables, fit model, & display results
    ols_model = sm.OLS(y, x).fit()
    print(ols_model.summary())

    # Spatial Lag model
    # Spatial weight object
    w = Queen.from_dataframe(final_df[['geometry']])
    w.transform = 'r'
    # Array for dependent variable
    y = final_df['sustainability_risk_index_score'].values.reshape(-1, 1)
    # Independent variables
    x = final_df[['avg_income_log_base',
                  'edu_facilities_log_base',
                  'health_center_log_base',
                  'health_concern_log_base']].values
    # Names for use in output
    y_name = 'Sustainability Risk'
    x_names = ['Income',
               'Education Facilities',
               'Health Centers',
               'Health Concerns']
    w_name = 'Queen'
    # Apply values to spatial lag model & display results
    mllag = ML_Lag(y, x, w,
                   name_y=y_name, name_x=x_names, name_w=w_name)
    print(mllag.summary)

    return


def minimizeFinalResult(final_results):
    final_results = final_results.to_crs(epsg=4326)

    final_results["longitude"] = final_results.geometry.centroid.x
    final_results["latitude"] = final_results.geometry.centroid.y
    
    final_col = ['Sub_City',
                 'sustainability_risk_index_score',
                 'Woreda',
                 'longitude',
                 'latitude']
    
    final_results = final_results[final_col]
    dashboard_fname = "for_dashboard.xlsx"
    final_results.to_excel(RESULTS_DIR / dashboard_fname,
                                                    index=False
    )
    
    return
    
# ------------------------------------------
# Main
# ------------------------------------------


def main():
    # Primary indicators
    composite_df = compositeIndicators()
    # Additional variables
    additional_ind = additionalIndicators(composite_df)
    # Plot results
    generatePlots(additional_ind)
    # Normalize indicators
    normalized_df = computeSustainabilityRisk(additional_ind)
    # Plot normalized results & risk index
    plotNormalizedIndicators(normalized_df)
    plotRiskIndex(normalized_df)
    # Spatial analysis
    final_df = spatialAnalysis(normalized_df)
    # Save final results
    final_fname = 'final_results.xlsx'
    final_df.to_excel(RESULTS_DIR / final_fname)
    # Run models
    models(final_df)
    
    # minimizeFinalResult(final_df)


if __name__ == "__main__":
    main()
