#!/usr/bin/env python3
"""
Climate Edge Detector v3 - Real-time Supplement

Based on working v2, with Open-Meteo supplement to show recent-day trends.
Core MC calculation uses ERA5 only (reliable baseline).
Open-Meteo shows directional trend for most recent days.
"""

import json
import subprocess
import sys
import math
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import statistics
import time

# Configuration
ERA5_URL = "https://climatereanalyzer.org/clim/t2_daily/json/era5_world_t2_day.json"
ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
GAMMA_API = "https://gamma-api.polymarket.com"
STATE_FILE = Path("/home/ubuntu/clawd/polymarket/climate_state_v3.json")

# Open-Meteo sampling grid (representative global points)
SAMPLE_GRID = [
    (0, -170), (0, -110), (0, -50), (0, 10), (0, 70), (0, 130),
    (10, -140), (10, -80), (10, -20), (10, 40), (10, 100),
    (-10, -140), (-10, -80), (-10, -20), (-10, 40), (-10, 100),
    (30, -120), (30, -60), (30, 0), (30, 60), (30, 120),
    (-30, -120), (-30, -60), (-30, 0), (-30, 60), (-30, 120),
    (45, -100), (45, 0), (45, 100),
    (-45, -70), (-45, 140),
    (60, -100), (60, 100),
]

WARMING_TREND_PER_YEAR = 0.02
REFERENCE_YEAR = 2000

HISTORICAL_RANKINGS = {
    1: {"year": 2024, "anomaly": 1.29},
    2: {"year": 2023, "anomaly": 1.18},
    3: {"year": 2016, "anomaly": 1.00},
    4: {"year": 2020, "anomaly": 0.98},
    5: {"year": 2019, "anomaly": 0.95},
    6: {"year": 2017, "anomaly": 0.91},
}


def fetch_json(url: str, headers: Dict = None) -> Optional[any]:
    default_headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ClimateBot/3.0)",
        "Accept": "application/json"
    }
    if headers:
        default_headers.update(headers)
    
    header_args = " ".join([f'-H "{k}: {v}"' for k, v in default_headers.items()])
    cmd = f'curl -s {header_args} "{url}"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except:
        return None


def fetch_text(url: str) -> Optional[str]:
    cmd = f'curl -s "{url}"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None


def fetch_era5_data() -> Dict[str, List[float]]:
    """Fetch ERA5 data from Climate Reanalyzer."""
    print("Fetching ERA5 data...")
    data = fetch_json(ERA5_URL)
    if not data:
        return {}
    
    result = {}
    for series in data:
        name = series.get("name", "")
        if name.isdigit():
            result[name] = [t if t is not None else None for t in series.get("data", [])]
    return result


def fetch_openmeteo_recent() -> Dict[str, float]:
    """Fetch recent global temp estimates from Open-Meteo (last 7 days)."""
    print("Fetching Open-Meteo recent data...")
    
    today = datetime.now(timezone.utc)
    start = (today - timedelta(days=10)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")
    
    all_data = {}
    success = 0
    
    for lat, lon in SAMPLE_GRID:
        url = (f"https://archive-api.open-meteo.com/v1/archive"
               f"?latitude={lat}&longitude={lon}"
               f"&start_date={start}&end_date={end}"
               f"&daily=temperature_2m_mean&timezone=UTC")
        data = fetch_json(url)
        if not data or "daily" not in data:
            continue
        
        weight = math.cos(math.radians(lat))
        for date, temp in zip(data["daily"].get("time", []), 
                              data["daily"].get("temperature_2m_mean", [])):
            if temp is not None:
                if date not in all_data:
                    all_data[date] = []
                all_data[date].append((temp, weight))
        success += 1
        time.sleep(0.03)
    
    # Weighted average per day
    result = {}
    for date, readings in all_data.items():
        total_w = sum(w for _, w in readings)
        if total_w > 0:
            result[date] = sum(t * w for t, w in readings) / total_w
    
    print(f"  Got {len(result)} days from {success}/{len(SAMPLE_GRID)} grid points")
    return result


def fetch_oni_data() -> Dict[str, float]:
    print("Fetching ENSO (ONI) data...")
    text = fetch_text(ONI_URL)
    if not text:
        return {}
    
    oni_data = {}
    for line in text.strip().split('\n'):
        parts = line.split()
        if len(parts) >= 4:
            try:
                period = f"{parts[0]}_{parts[1]}"
                oni = float(parts[3])
                oni_data[period] = oni
            except:
                continue
    return oni_data


def get_current_enso_state(oni_data: Dict[str, float]) -> Dict:
    if not oni_data:
        return {"state": "neutral", "oni": 0.0, "impact": 0.0}
    
    latest = max(oni_data.keys(), key=lambda x: (int(x.split('_')[1]), x.split('_')[0]))
    oni = oni_data[latest]
    
    if oni >= 0.5:
        state, impact = "el_nino", 0.08 * (oni / 1.0)
    elif oni <= -0.5:
        state, impact = "la_nina", -0.08 * (abs(oni) / 1.0)
    else:
        state, impact = "neutral", 0.0
    
    return {"state": state, "oni": oni, "period": latest, "impact": impact,
            "description": f"{state.replace('_', ' ').title()} (ONI: {oni})"}


def get_2026_progress(era5_data: Dict) -> Dict:
    """Calculate 2026 progress using ERA5 data only."""
    year_2026 = era5_data.get("2026", [])
    valid_temps = [t for t in year_2026 if t is not None]
    
    if not valid_temps:
        return None
    
    days_so_far = len(valid_temps)
    mean_temp = statistics.mean(valid_temps)
    
    # Compare with other years (same number of days)
    comparisons = {}
    for year_str, temps in era5_data.items():
        if year_str == "2026" or not year_str.isdigit():
            continue
        if int(year_str) < 2015:
            continue
        year_temps = [t for t in temps[:days_so_far] if t is not None]
        if year_temps:
            comparisons[year_str] = {
                "mean": statistics.mean(year_temps),
                "diff_vs_2026": mean_temp - statistics.mean(year_temps)
            }
    
    # Baseline
    baseline_years = [era5_data.get(str(y), []) for y in range(2020, 2024)]
    baseline_temps = [statistics.mean([t for t in temps[:days_so_far] if t])
                      for temps in baseline_years if any(t for t in temps[:days_so_far] if t)]
    baseline_mean = statistics.mean(baseline_temps) if baseline_temps else 12.5
    
    # Historical variability - using ANOMALY drift (not raw temp drift)
    # This removes seasonal effects by comparing to period-specific baselines
    
    # Calculate baselines for YTD and full year periods
    baseline_ytd_temps = []
    baseline_full_temps = []
    for y in range(1991, 2021):
        y_temps = era5_data.get(str(y), [])
        if len(y_temps) >= days_so_far:
            baseline_ytd_temps.extend([t for t in y_temps[:days_so_far] if t is not None])
        if len(y_temps) >= 365:
            baseline_full_temps.extend([t for t in y_temps[:365] if t is not None])
    
    baseline_ytd = statistics.mean(baseline_ytd_temps) if baseline_ytd_temps else 12.5
    baseline_full = statistics.mean(baseline_full_temps) if baseline_full_temps else 14.0
    
    # Calculate how anomalies drift from YTD to full year
    diffs = []
    for year in range(2015, 2025):
        y_temps = era5_data.get(str(year), [])
        valid_ytd = [t for t in y_temps[:days_so_far] if t is not None]
        valid_full = [t for t in y_temps[:365] if t is not None]
        
        if len(valid_ytd) >= days_so_far * 0.8 and len(valid_full) >= 300:
            ytd_anomaly = statistics.mean(valid_ytd) - baseline_ytd
            full_anomaly = statistics.mean(valid_full) - baseline_full
            diffs.append(full_anomaly - ytd_anomaly)  # Anomaly drift
    
    return {
        "days_so_far": days_so_far,
        "latest_temp": valid_temps[-1],
        "mean_2026_ytd": mean_temp,
        "baseline_mean": baseline_mean,
        "raw_anomaly": mean_temp - baseline_mean,
        "comparisons": comparisons,
        "historical_variability": {
            "std": statistics.stdev(diffs) if len(diffs) > 1 else 0.15,
            "mean_drift": statistics.mean(diffs) if diffs else 0.0,
            "samples": len(diffs)
        }
    }


def get_openmeteo_trend(om_data: Dict[str, float], era5_days: int) -> Dict:
    """Analyze Open-Meteo data for recent trend."""
    if not om_data:
        return {"available": False}
    
    # Sort by date
    sorted_days = sorted(om_data.items())
    
    # Look for days after ERA5 coverage
    today = datetime.now(timezone.utc)
    year_start = datetime(today.year, 1, 1, tzinfo=timezone.utc)
    
    recent_temps = []
    for date_str, temp in sorted_days:
        date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        day_of_year = (date - year_start).days + 1
        if day_of_year > era5_days:
            recent_temps.append((date_str, temp))
    
    if not recent_temps:
        return {"available": False}
    
    # Calculate trend
    temps = [t for _, t in recent_temps]
    avg = statistics.mean(temps)
    
    # Compare with earlier days in Open-Meteo data
    earlier = [t for d, t in sorted_days if d not in [x[0] for x in recent_temps]]
    earlier_avg = statistics.mean(earlier) if earlier else avg
    
    trend = avg - earlier_avg
    
    return {
        "available": True,
        "days_after_era5": len(recent_temps),
        "recent_dates": [d for d, _ in recent_temps],
        "recent_avg": avg,
        "trend_vs_earlier": trend,
        "direction": "warming" if trend > 0.1 else "cooling" if trend < -0.1 else "stable"
    }


def monte_carlo_ranking(progress: Dict, enso: Dict, n_sim: int = 10000) -> Dict[int, float]:
    """Run Monte Carlo simulation for ranking probabilities."""
    comparisons = progress["comparisons"]
    std = progress["historical_variability"]["std"]
    drift = progress["historical_variability"]["mean_drift"]
    enso_impact = enso.get("impact", 0)
    
    days_remaining = 365 - progress["days_so_far"]
    uncertainty = std * math.sqrt(days_remaining / 365)
    
    diff_2024 = comparisons.get("2024", {}).get("diff_vs_2026", 0)
    diff_2023 = comparisons.get("2023", {}).get("diff_vs_2026", 0)
    diff_2020 = comparisons.get("2020", {}).get("diff_vs_2026", 0)
    
    counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    
    for _ in range(n_sim):
        noise = random.gauss(0, uncertainty)
        adj = drift + noise + enso_impact * random.uniform(0.5, 1.5)
        
        f_2024 = diff_2024 + adj
        f_2023 = diff_2023 + adj
        f_2020 = diff_2020 + adj
        
        if f_2024 > 0:
            rank = 1
        elif f_2023 > 0:
            rank = 2
        elif f_2020 > 0.02:
            rank = 3
        elif f_2020 > -0.03:
            rank = random.choice([4, 5])
        else:
            rank = random.choice([5, 6])
        
        counts[rank] += 1
    
    return {k: v / n_sim for k, v in counts.items()}


def fetch_polymarket_odds() -> List[Dict]:
    print("Fetching Polymarket markets...")
    
    data = fetch_json(f"{GAMMA_API}/markets?limit=100")
    if not data:
        return []
    
    markets = []
    keywords = ["hottest", "temperature", "warmest", "2026"]
    
    for m in data:
        q = m.get("question", "").lower()
        if any(kw in q for kw in keywords):
            yes_price = None
            for t in m.get("tokens", []):
                if t.get("outcome", "").lower() == "yes":
                    yes_price = float(t.get("price", 0))
                    break
            markets.append({
                "question": m.get("question"),
                "slug": m.get("slug"),
                "yes_price": yes_price,
                "volume": m.get("volume", 0),
                "url": f"https://polymarket.com/event/{m.get('slug', '')}"
            })
    
    return markets


def calculate_edges(mc_probs: Dict[int, float], markets: List[Dict]) -> List[Dict]:
    rank_patterns = {
        "hottest year": 1, "second-hottest": 2, "second hottest": 2,
        "third-hottest": 3, "fourth-hottest": 4, "fifth-hottest": 5,
        "sixth-hottest": 6, "sixth hottest": 6,
    }
    
    edges = []
    for m in markets:
        if m["yes_price"] is None:
            continue
        
        q = m["question"].lower()
        market_prob = m["yes_price"] * 100
        our_prob, rank = None, None
        
        for pattern, r in rank_patterns.items():
            if pattern in q:
                rank = r
                our_prob = mc_probs.get(r, 0) * 100
                break
        
        if "sixth" in q and "or lower" in q:
            our_prob = sum(mc_probs.get(r, 0) for r in [6]) * 100
            rank = 6
        
        if our_prob is not None:
            edge = our_prob - market_prob
            edges.append({
                "rank": rank,
                "question": m["question"],
                "market_prob": market_prob,
                "our_prob": our_prob,
                "edge": edge,
                "direction": "BUY YES" if edge > 0 else "BUY NO",
                "confidence": "HIGH" if abs(edge) > 15 else "MEDIUM" if abs(edge) > 8 else "LOW",
                "volume": m.get("volume", 0),
                "url": m["url"]
            })
    
    return sorted(edges, key=lambda x: abs(x["edge"]), reverse=True)


def main():
    print("=" * 60)
    print("Climate Edge Detector v3 - Real-time Supplement")
    print("=" * 60)
    
    era5_data = fetch_era5_data()
    if not era5_data:
        print("ERROR: Could not fetch ERA5 data")
        return
    
    om_data = fetch_openmeteo_recent()
    oni_data = fetch_oni_data()
    enso = get_current_enso_state(oni_data)
    
    print(f"\n📊 ENSO: {enso['description']}")
    
    progress = get_2026_progress(era5_data)
    if not progress:
        print("ERROR: No 2026 data")
        return
    
    # Add ENSO adjustment
    progress["enso_impact"] = enso["impact"]
    progress["enso_adjusted_anomaly"] = progress["raw_anomaly"] + enso["impact"]
    
    # Check Open-Meteo trend
    om_trend = get_openmeteo_trend(om_data, progress["days_so_far"])
    
    print(f"\n📈 2026 Progress (Day {progress['days_so_far']} ERA5):")
    print(f"   Mean temp: {progress['mean_2026_ytd']:.3f}°C")
    print(f"   vs 2024: {progress['comparisons'].get('2024', {}).get('diff_vs_2026', 0):+.3f}°C")
    print(f"   vs 2023: {progress['comparisons'].get('2023', {}).get('diff_vs_2026', 0):+.3f}°C")
    
    if om_trend.get("available"):
        print(f"\n🌡️  Open-Meteo (days {progress['days_so_far']+1}-{progress['days_so_far']+om_trend['days_after_era5']}):")
        print(f"   Trend: {om_trend['direction'].upper()} ({om_trend['trend_vs_earlier']:+.2f}°C)")
    
    # Monte Carlo
    print("\n🎲 Monte Carlo simulation...")
    mc_probs = monte_carlo_ranking(progress, enso)
    
    print("\n📊 Ranking Probabilities:")
    for rank in range(1, 7):
        prob = mc_probs.get(rank, 0) * 100
        bar = "█" * int(prob / 2)
        print(f"   #{rank}: {prob:5.1f}% {bar}")
    
    # Markets
    markets = fetch_polymarket_odds()
    edges = calculate_edges(mc_probs, markets)
    
    if edges:
        print("\n🎯 Trading Opportunities:")
        for e in edges[:6]:
            print(f"\n   {e['direction']} ({e['confidence']})")
            print(f"   {e['question']}")
            print(f"   Market: {e['market_prob']:.1f}% | Model: {e['our_prob']:.1f}% | Edge: {e['edge']:+.1f}%")
    
    # Save
    state = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "v3",
        "enso": enso,
        "progress": progress,
        "openmeteo_trend": om_trend,
        "mc_probs": mc_probs,
        "edges": edges
    }
    STATE_FILE.write_text(json.dumps(state, indent=2))
    print(f"\n✅ Saved to {STATE_FILE}")
    
    if "--alert" in sys.argv:
        high = [e for e in edges if e["confidence"] == "HIGH" and abs(e["edge"]) > 20]
        if high:
            print("\n🚨 HIGH CONFIDENCE ALERTS:")
            for e in high:
                print(f"   {e['direction']}: {e['question']}")
                print(f"   Edge: {e['edge']:+.1f}%")


if __name__ == "__main__":
    main()
