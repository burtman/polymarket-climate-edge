#!/usr/bin/env python3
"""
ERA5 Data Fetcher via Copernicus CDS API

Setup:
1. Create account at https://cds.climate.copernicus.eu/
2. Get API key from profile page
3. Create ~/.cdsapirc with:
   url: https://cds.climate.copernicus.eu/api/v2
   key: <UID>:<API_KEY>
"""

import os
import sys
from datetime import datetime, timedelta

try:
    import cdsapi
    import netCDF4 as nc
    import numpy as np
except ImportError:
    print("Install required packages: pip install cdsapi netCDF4 numpy")
    sys.exit(1)


def check_cds_credentials():
    """Check if CDS API credentials are configured."""
    cdsapirc = os.path.expanduser("~/.cdsapirc")
    if not os.path.exists(cdsapirc):
        print("❌ No ~/.cdsapirc found!")
        print("\nSetup instructions:")
        print("1. Go to https://cds.climate.copernicus.eu/user")
        print("2. Copy your UID and API key")
        print("3. Create ~/.cdsapirc with:")
        print("   url: https://cds.climate.copernicus.eu/api/v2")
        print("   key: <UID>:<API_KEY>")
        return False
    return True


def fetch_era5_monthly(year: int, month: int, output_file: str = None):
    """
    Fetch ERA5 monthly averaged 2m temperature.
    
    Args:
        year: Year to fetch
        month: Month to fetch (1-12)
        output_file: Output NetCDF file path
    
    Returns:
        Global mean temperature anomaly (vs 1951-1980 baseline)
    """
    if not check_cds_credentials():
        return None
    
    if output_file is None:
        output_file = f"era5_{year}_{month:02d}.nc"
    
    c = cdsapi.Client()
    
    print(f"Fetching ERA5 data for {year}-{month:02d}...")
    
    c.retrieve(
        'reanalysis-era5-single-levels-monthly-means',
        {
            'product_type': 'monthly_averaged_reanalysis',
            'variable': '2m_temperature',
            'year': str(year),
            'month': f'{month:02d}',
            'time': '00:00',
            'format': 'netcdf',
        },
        output_file
    )
    
    print(f"✅ Downloaded to {output_file}")
    return output_file


def fetch_era5_daily(year: int, month: int, days: list = None, output_file: str = None):
    """
    Fetch ERA5 daily 2m temperature for specific days.
    
    Args:
        year: Year to fetch
        month: Month to fetch (1-12)
        days: List of days to fetch, or None for all available
        output_file: Output NetCDF file path
    """
    if not check_cds_credentials():
        return None
    
    if days is None:
        # Fetch all days up to 5 days ago (ERA5 lag)
        today = datetime.now()
        era5_cutoff = today - timedelta(days=5)
        if year == era5_cutoff.year and month == era5_cutoff.month:
            days = list(range(1, era5_cutoff.day + 1))
        elif (year, month) < (era5_cutoff.year, era5_cutoff.month):
            # Full month available
            import calendar
            days = list(range(1, calendar.monthrange(year, month)[1] + 1))
        else:
            print(f"❌ Data not yet available for {year}-{month:02d}")
            return None
    
    if output_file is None:
        output_file = f"era5_daily_{year}_{month:02d}.nc"
    
    c = cdsapi.Client()
    
    print(f"Fetching ERA5 daily data for {year}-{month:02d} (days: {days[0]}-{days[-1]})...")
    
    c.retrieve(
        'reanalysis-era5-single-levels',
        {
            'product_type': 'reanalysis',
            'variable': '2m_temperature',
            'year': str(year),
            'month': f'{month:02d}',
            'day': [f'{d:02d}' for d in days],
            'time': ['00:00', '06:00', '12:00', '18:00'],
            'format': 'netcdf',
        },
        output_file
    )
    
    print(f"✅ Downloaded to {output_file}")
    return output_file


def calculate_global_mean(nc_file: str) -> float:
    """
    Calculate global area-weighted mean temperature from NetCDF file.
    
    Args:
        nc_file: Path to NetCDF file with 2m temperature
    
    Returns:
        Global mean temperature in Kelvin
    """
    ds = nc.Dataset(nc_file)
    
    # Get temperature (t2m) and coordinates
    t2m = ds.variables['t2m'][:]  # Shape: (time, lat, lon)
    lats = ds.variables['latitude'][:]
    
    # Calculate area weights (cosine of latitude)
    weights = np.cos(np.deg2rad(lats))
    weights = weights / weights.sum()
    
    # Calculate weighted mean
    # First average over longitude, then weighted average over latitude
    lon_mean = np.nanmean(t2m, axis=-1)  # (time, lat)
    global_mean = np.average(lon_mean, axis=-1, weights=weights)  # (time,)
    
    ds.close()
    
    return float(np.mean(global_mean))


# Baseline: 1951-1980 mean for each month (approximate, from GISS)
BASELINE_1951_1980 = {
    1: 287.0,   # January (~14°C)
    2: 287.2,
    3: 287.8,
    4: 288.5,
    5: 289.1,
    6: 289.5,
    7: 289.6,
    8: 289.4,
    9: 289.0,
    10: 288.4,
    11: 287.7,
    12: 287.2,
}


def era5_to_anomaly(global_mean_k: float, month: int) -> float:
    """
    Convert ERA5 global mean (Kelvin) to anomaly vs 1951-1980.
    
    Args:
        global_mean_k: Global mean temperature in Kelvin
        month: Month (1-12)
    
    Returns:
        Temperature anomaly in °C
    """
    baseline = BASELINE_1951_1980.get(month, 288.0)
    return global_mean_k - baseline


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Fetch ERA5 temperature data")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--month", type=int, default=1)
    parser.add_argument("--daily", action="store_true", help="Fetch daily instead of monthly")
    parser.add_argument("--check", action="store_true", help="Just check credentials")
    
    args = parser.parse_args()
    
    if args.check:
        if check_cds_credentials():
            print("✅ CDS credentials configured!")
        sys.exit(0)
    
    if args.daily:
        result = fetch_era5_daily(args.year, args.month)
    else:
        result = fetch_era5_monthly(args.year, args.month)
    
    if result:
        global_mean = calculate_global_mean(result)
        anomaly = era5_to_anomaly(global_mean, args.month)
        print(f"\n📊 Results:")
        print(f"   Global mean: {global_mean:.2f} K ({global_mean - 273.15:.2f}°C)")
        print(f"   Anomaly: {anomaly:.2f}°C (vs 1951-1980)")
