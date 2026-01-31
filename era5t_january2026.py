#!/usr/bin/env python3
"""
ERA5T + Open-Meteo Cross-Validation for January 2026
ERA5T = ERA5 near-real-time (~5 day delay)
"""

import cdsapi
import numpy as np
import json
import os
from datetime import datetime, timedelta
import requests

# Historical GISS January anomalies (°C vs 1951-1980 baseline)
GISS_JANUARY = {
    2016: 1.17,
    2017: 1.02,
    2018: 0.82,
    2019: 0.93,
    2020: 1.17,
    2021: 0.82,
    2022: 0.93,
    2023: 0.91,
    2024: 1.30,  # Record
    2025: 1.38,  # New record
}

def fetch_era5t_daily(year, month, days):
    """Fetch ERA5T daily 2m temperature data."""
    c = cdsapi.Client()
    
    output_file = f"/tmp/era5t_{year}_{month:02d}.nc"
    
    print(f"📡 Fetching ERA5T for {year}-{month:02d} (days 1-{days})...")
    
    try:
        c.retrieve(
            'reanalysis-era5-single-levels',
            {
                'product_type': 'reanalysis',
                'variable': '2m_temperature',
                'year': str(year),
                'month': f'{month:02d}',
                'day': [f'{d:02d}' for d in range(1, days + 1)],
                'time': ['00:00', '06:00', '12:00', '18:00'],
                'data_format': 'netcdf',
            },
            output_file
        )
        return output_file
    except Exception as e:
        print(f"❌ ERA5T fetch failed: {e}")
        return None

def analyze_era5t_file(filepath):
    """Analyze ERA5T NetCDF file."""
    import netCDF4 as nc
    
    ds = nc.Dataset(filepath)
    t2m = ds.variables['t2m'][:]  # Temperature in Kelvin
    
    # Global mean (area-weighted would be better, but simple mean for now)
    global_mean_k = np.mean(t2m)
    global_mean_c = global_mean_k - 273.15
    
    ds.close()
    return global_mean_c

def fetch_openmeteo_global_sample(year, month, days):
    """Fetch Open-Meteo data from global sample points."""
    
    # Representative global points (lat, lon, weight for area)
    points = [
        # Northern Hemisphere
        (64.0, -21.0, 0.5),   # Reykjavik
        (55.7, 37.6, 0.8),    # Moscow
        (40.7, -74.0, 0.9),   # New York
        (35.7, 139.7, 0.9),   # Tokyo
        (39.9, 116.4, 0.9),   # Beijing
        (51.5, -0.1, 0.85),   # London
        (48.9, 2.3, 0.85),    # Paris
        (52.5, 13.4, 0.85),   # Berlin
        # Tropics
        (1.3, 103.8, 1.0),    # Singapore
        (-6.2, 106.8, 1.0),   # Jakarta
        (19.4, -99.1, 0.95),  # Mexico City
        (-23.5, -46.6, 0.95), # Sao Paulo
        (28.6, 77.2, 0.95),   # Delhi
        # Southern Hemisphere
        (-33.9, 151.2, 0.8),  # Sydney
        (-33.4, -70.6, 0.7),  # Santiago
        (-26.2, 28.0, 0.75),  # Johannesburg
    ]
    
    temps = []
    weights = []
    
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{days:02d}"
    
    print(f"🌍 Fetching Open-Meteo for {len(points)} global points...")
    
    for lat, lon, weight in points:
        try:
            url = f"https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "start_date": start_date,
                "end_date": end_date,
                "daily": "temperature_2m_mean",
                "timezone": "UTC"
            }
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            
            if "daily" in data and data["daily"]["temperature_2m_mean"]:
                valid_temps = [t for t in data["daily"]["temperature_2m_mean"] if t is not None]
                if valid_temps:
                    temps.append(np.mean(valid_temps))
                    weights.append(weight)
        except Exception as e:
            print(f"  ⚠️ Failed for ({lat}, {lon}): {e}")
    
    if temps:
        weighted_mean = np.average(temps, weights=weights)
        return weighted_mean, len(temps)
    return None, 0

def estimate_giss_anomaly(era5t_mean=None, openmeteo_mean=None):
    """
    Estimate GISS anomaly from ERA5T/Open-Meteo data.
    Uses historical correlation between data sources and GISS.
    """
    
    # Historical January data for calibration
    # These are approximate correlations based on past data
    
    if era5t_mean is not None:
        # ERA5 global mean January temps and corresponding GISS anomalies
        # Calibration: ERA5 ~= 12.5°C corresponds to GISS ~1.0°C anomaly
        # Each 0.1°C in ERA5 ≈ 0.08°C in GISS anomaly
        baseline_era5 = 12.0  # Approximate ERA5 baseline for Jan
        giss_from_era5 = 0.9 + (era5t_mean - baseline_era5) * 0.8
        return giss_from_era5, "ERA5T"
    
    if openmeteo_mean is not None:
        # Open-Meteo sample is biased toward land/cities
        # Calibration based on our sample points
        baseline_om = 10.0
        giss_from_om = 0.9 + (openmeteo_mean - baseline_om) * 0.1
        return giss_from_om, "Open-Meteo"
    
    return None, None

def main():
    print("=" * 60)
    print("🌡️  JANUARY 2026 TEMPERATURE ANALYSIS")
    print("=" * 60)
    print()
    
    year = 2026
    month = 1
    today = datetime.now()
    
    # How many days of January do we have?
    if today.year == year and today.month == month:
        days_available = today.day - 1  # Yesterday is latest reliable
    elif today.year > year or (today.year == year and today.month > month):
        days_available = 31
    else:
        days_available = 0
    
    # For ERA5T, data is ~5 days behind
    era5t_days = max(0, days_available - 5)
    
    print(f"📅 Today: {today.strftime('%Y-%m-%d')}")
    print(f"📅 Days available for Open-Meteo: {days_available}")
    print(f"📅 Days available for ERA5T: ~{era5t_days}")
    print()
    
    results = {}
    
    # 1. Try ERA5T
    if era5t_days >= 10:
        print("─" * 40)
        print("1️⃣  ERA5T Analysis")
        print("─" * 40)
        nc_file = fetch_era5t_daily(year, month, era5t_days)
        if nc_file and os.path.exists(nc_file):
            era5t_mean = analyze_era5t_file(nc_file)
            results['era5t'] = {
                'mean_temp': era5t_mean,
                'days': era5t_days
            }
            print(f"   Global mean temp: {era5t_mean:.2f}°C")
            os.remove(nc_file)
        print()
    else:
        print("⚠️ Not enough days for ERA5T (need at least 10)")
        print()
    
    # 2. Open-Meteo
    print("─" * 40)
    print("2️⃣  Open-Meteo Analysis")
    print("─" * 40)
    if days_available >= 5:
        om_mean, om_points = fetch_openmeteo_global_sample(year, month, days_available)
        if om_mean:
            results['openmeteo'] = {
                'mean_temp': om_mean,
                'points': om_points,
                'days': days_available
            }
            print(f"   Sample mean temp: {om_mean:.2f}°C ({om_points} points)")
    print()
    
    # 3. Estimate GISS anomaly
    print("─" * 40)
    print("3️⃣  GISS Anomaly Estimation")
    print("─" * 40)
    
    estimates = []
    
    if 'era5t' in results:
        est, src = estimate_giss_anomaly(era5t_mean=results['era5t']['mean_temp'])
        if est:
            estimates.append((est, src, 0.7))  # Higher confidence
            print(f"   From ERA5T: {est:.2f}°C")
    
    if 'openmeteo' in results:
        est, src = estimate_giss_anomaly(openmeteo_mean=results['openmeteo']['mean_temp'])
        if est:
            estimates.append((est, src, 0.3))  # Lower confidence
            print(f"   From Open-Meteo: {est:.2f}°C")
    
    if estimates:
        # Weighted average
        total_weight = sum(e[2] for e in estimates)
        final_estimate = sum(e[0] * e[2] for e in estimates) / total_weight
        
        print()
        print("=" * 60)
        print(f"📊 FINAL ESTIMATE: {final_estimate:.2f}°C anomaly")
        print("=" * 60)
        
        # Compare to historical
        print()
        print("📈 Historical January Anomalies (GISS):")
        for yr, anom in sorted(GISS_JANUARY.items()):
            marker = "←" if yr == 2025 else ""
            print(f"   {yr}: {anom:.2f}°C {marker}")
        
        print()
        print(f"   2026: {final_estimate:.2f}°C (ESTIMATE)")
        
        # Ranking
        all_years = list(GISS_JANUARY.values()) + [final_estimate]
        all_years_sorted = sorted(all_years, reverse=True)
        rank = all_years_sorted.index(final_estimate) + 1
        
        print()
        print(f"🏆 Estimated Rank: #{rank} warmest January on record")
        
        # Market implications
        print()
        print("─" * 40)
        print("💰 MARKET IMPLICATIONS")
        print("─" * 40)
        
        if final_estimate >= 1.19:
            print("   Temperature >1.19°C → BET on '>1.19°C' if odds are good")
        elif final_estimate >= 1.09:
            print(f"   Temperature ~{final_estimate:.2f}°C → In range 1.05-1.19°C")
        else:
            print(f"   Temperature ~{final_estimate:.2f}°C → Likely below 1.09°C")
        
        if rank == 1:
            print("   Ranking: Could be WARMEST → Check 'Hottest' market")
        elif rank == 2:
            print("   Ranking: Could be 2nd WARMEST → Check '2nd hottest' market")
        elif rank == 3:
            print("   Ranking: Could be 3rd WARMEST → Check '3rd hottest' market")
        else:
            print(f"   Ranking: #{rank} → '4th or lower' likely correct")
        
        return final_estimate, rank
    
    print("❌ Could not generate estimate")
    return None, None

if __name__ == "__main__":
    main()
