#!/usr/bin/env python3
"""
January 2026 Polymarket Analysis

Targets:
- Market 1: "January 2026 Temperature Increase (ºC)" 
  → Brackets: <1.00, 1.00-1.04, 1.05-1.09, 1.10-1.14, 1.15-1.19, >1.19
  → End: Feb 10, 2026

- Market 2: "2026 January 1st/2nd/3rd hottest on record?"
  → Outcomes: 1st, 2nd, 3rd, 4th or lower
  → End: Feb 10, 2026

Resolution source: NASA GISS Global Land-Ocean Temperature Index
https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.txt
"""

import json
import requests
from datetime import datetime
from typing import Dict, List, Tuple

# Historical NASA GISS January data (anomaly in °C vs 1951-1980)
GISS_JANUARY_HISTORICAL = {
    2025: 1.38, 2024: 1.25, 2023: 0.88, 2022: 0.91, 2021: 0.81,
    2020: 1.18, 2019: 0.93, 2018: 0.82, 2017: 1.02, 2016: 1.18,
    2015: 0.87, 2014: 0.77, 2013: 0.71, 2012: 0.47, 2011: 0.52,
    2010: 0.75, 2009: 0.65, 2008: 0.30, 2007: 1.02, 2006: 0.56,
    2005: 0.75, 2004: 0.58, 2003: 0.74, 2002: 0.77, 2001: 0.45,
    2000: 0.25, 1999: 0.48, 1998: 0.58, 1997: 0.32, 1996: 0.24,
}

# Market 1: Temperature brackets
TEMP_BRACKETS = [
    ("<1.00°C", lambda x: x < 1.00),
    ("1.00-1.04°C", lambda x: 1.00 <= x < 1.05),
    ("1.05-1.09°C", lambda x: 1.05 <= x < 1.10),
    ("1.10-1.14°C", lambda x: 1.10 <= x < 1.15),
    ("1.15-1.19°C", lambda x: 1.15 <= x < 1.20),
    (">1.19°C", lambda x: x >= 1.20),
]

# Current market odds (as of Jan 31, 2026)
MARKET_ODDS_TEMP = {
    "<1.00°C": 0.013,
    "1.00-1.04°C": 0.032,
    "1.05-1.09°C": 0.51,
    "1.10-1.14°C": 0.40,
    "1.15-1.19°C": 0.05,
    ">1.19°C": 0.0135,
}

MARKET_ODDS_RANKING = {
    "1st hottest": 0.0055,
    "2nd hottest": 0.005,
    "3rd hottest": 0.011,
    "4th or lower": 0.9785,
}


def get_january_ranking(anomaly: float) -> str:
    """Determine where January 2026 would rank given an anomaly."""
    sorted_years = sorted(GISS_JANUARY_HISTORICAL.items(), key=lambda x: x[1], reverse=True)
    
    for rank, (year, hist_anomaly) in enumerate(sorted_years, 1):
        if anomaly > hist_anomaly:
            if rank == 1:
                return "1st hottest"
            elif rank == 2:
                return "2nd hottest"
            elif rank == 3:
                return "3rd hottest"
            else:
                return "4th or lower"
    
    return "4th or lower"


def get_temp_bracket(anomaly: float) -> str:
    """Determine which temperature bracket the anomaly falls into."""
    for bracket_name, check_fn in TEMP_BRACKETS:
        if check_fn(anomaly):
            return bracket_name
    return ">1.19°C"


def estimate_january_2026_from_openmeteo() -> Tuple[float, float]:
    """
    Estimate January 2026 anomaly using Open-Meteo sampling.
    Returns (estimated_anomaly, uncertainty).
    
    WARNING: This is a rough estimate with high uncertainty.
    """
    # Sample points for global coverage
    sample_points = [
        (0, 0), (0, 90), (0, -90), (0, 180),
        (45, 0), (45, 90), (-45, 0), (-45, 90),
        (30, 45), (-30, 45), (60, 0), (-60, 0),
    ]
    
    def get_jan_mean(year: int) -> float:
        temps = []
        for lat, lon in sample_points:
            try:
                url = f"https://archive-api.open-meteo.com/v1/archive"
                params = {
                    "latitude": lat,
                    "longitude": lon,
                    "start_date": f"{year}-01-01",
                    "end_date": f"{year}-01-30",
                    "daily": "temperature_2m_mean",
                }
                resp = requests.get(url, params=params, timeout=10)
                if resp.ok:
                    data = resp.json()
                    daily = data.get("daily", {}).get("temperature_2m_mean", [])
                    valid = [t for t in daily if t is not None]
                    if valid:
                        temps.extend(valid)
            except:
                pass
        return sum(temps) / len(temps) if temps else None
    
    jan_2026 = get_jan_mean(2026)
    jan_2025 = get_jan_mean(2025)
    jan_2024 = get_jan_mean(2024)
    
    if not all([jan_2026, jan_2025]):
        return None, None
    
    # Use relative difference to estimate GISS anomaly
    diff_vs_2025 = jan_2026 - jan_2025
    estimated_anomaly = GISS_JANUARY_HISTORICAL[2025] + diff_vs_2025
    
    # Uncertainty is high due to sampling limitations
    uncertainty = 0.30  # ±0.30°C
    
    return estimated_anomaly, uncertainty


def calculate_edge(our_prob: float, market_prob: float) -> Dict:
    """Calculate trading edge and expected value."""
    edge = our_prob - market_prob
    
    # Kelly criterion (simplified)
    if edge > 0:
        kelly = edge / (1 - market_prob) if market_prob < 1 else 0
    else:
        kelly = 0
    
    return {
        "edge": edge,
        "edge_pct": edge * 100,
        "direction": "BUY YES" if edge > 0 else ("BUY NO" if edge < -0.05 else "PASS"),
        "kelly_fraction": min(kelly, 0.25),  # Cap at 25% of bankroll
    }


def run_analysis():
    """Run full January 2026 analysis."""
    print("=" * 60)
    print("🌡️  JANUARY 2026 POLYMARKET ANALYSIS")
    print("=" * 60)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    
    # Estimate anomaly
    print("\n📊 Estimating January 2026 anomaly...")
    estimated, uncertainty = estimate_january_2026_from_openmeteo()
    
    if estimated is None:
        print("❌ Failed to estimate - using fallback")
        estimated = 1.05
        uncertainty = 0.40
    
    print(f"   Estimate: {estimated:.2f}°C (±{uncertainty:.2f}°C)")
    
    # Determine most likely outcomes
    bracket = get_temp_bracket(estimated)
    ranking = get_january_ranking(estimated)
    
    print(f"   → Temperature bracket: {bracket}")
    print(f"   → Historical ranking: {ranking}")
    
    # Monte Carlo simulation for probabilities
    print("\n🎲 Monte Carlo Simulation (10,000 runs)...")
    import random
    
    temp_counts = {b[0]: 0 for b in TEMP_BRACKETS}
    rank_counts = {"1st hottest": 0, "2nd hottest": 0, "3rd hottest": 0, "4th or lower": 0}
    
    n_sims = 10000
    for _ in range(n_sims):
        sim_anomaly = random.gauss(estimated, uncertainty)
        temp_counts[get_temp_bracket(sim_anomaly)] += 1
        rank_counts[get_january_ranking(sim_anomaly)] += 1
    
    our_temp_probs = {k: v / n_sims for k, v in temp_counts.items()}
    our_rank_probs = {k: v / n_sims for k, v in rank_counts.items()}
    
    # Calculate edges
    print("\n" + "=" * 60)
    print("📈 MARKET 1: Temperature Increase (ºC)")
    print("=" * 60)
    print(f"{'Bracket':<15} {'Market':<10} {'Our Est.':<10} {'Edge':<10} {'Action':<10}")
    print("-" * 55)
    
    for bracket_name, market_prob in MARKET_ODDS_TEMP.items():
        our_prob = our_temp_probs.get(bracket_name, 0)
        edge_info = calculate_edge(our_prob, market_prob)
        
        action = edge_info["direction"]
        if abs(edge_info["edge"]) < 0.03:
            action = "PASS"
        
        print(f"{bracket_name:<15} {market_prob*100:>6.1f}%    {our_prob*100:>6.1f}%    "
              f"{edge_info['edge_pct']:>+6.1f}%   {action:<10}")
    
    print("\n" + "=" * 60)
    print("📈 MARKET 2: January Ranking")
    print("=" * 60)
    print(f"{'Outcome':<15} {'Market':<10} {'Our Est.':<10} {'Edge':<10} {'Action':<10}")
    print("-" * 55)
    
    for outcome, market_prob in MARKET_ODDS_RANKING.items():
        our_prob = our_rank_probs.get(outcome, 0)
        edge_info = calculate_edge(our_prob, market_prob)
        
        action = edge_info["direction"]
        if abs(edge_info["edge"]) < 0.03:
            action = "PASS"
        
        print(f"{outcome:<15} {market_prob*100:>6.1f}%    {our_prob*100:>6.1f}%    "
              f"{edge_info['edge_pct']:>+6.1f}%   {action:<10}")
    
    # Save state
    state = {
        "timestamp": datetime.now().isoformat(),
        "estimated_anomaly": estimated,
        "uncertainty": uncertainty,
        "our_probabilities": {
            "temperature": our_temp_probs,
            "ranking": our_rank_probs,
        },
        "market_odds": {
            "temperature": MARKET_ODDS_TEMP,
            "ranking": MARKET_ODDS_RANKING,
        },
    }
    
    with open("january_2026_state.json", "w") as f:
        json.dump(state, f, indent=2)
    
    print(f"\n✅ State saved to january_2026_state.json")
    
    return state


if __name__ == "__main__":
    run_analysis()
