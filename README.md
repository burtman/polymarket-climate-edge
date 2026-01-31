# Polymarket Climate Edge

🌡️ Outil d'analyse pour identifier des edges sur les marchés climatiques Polymarket.

## Objectif

Estimer les anomalies de température globale **avant** la publication officielle de NASA GISS pour trouver des opportunités de trading sur Polymarket.

## Marchés ciblés

| Marché | Résolution | Volume |
|--------|------------|--------|
| January 2026 Temperature Increase (ºC) | NASA GISS | ~$594k |
| 2026 January Ranking (1st/2nd/3rd hottest) | NASA GISS | ~$334k |
| Where will 2026 rank (annual) | NASA GISS | ~$1M+ |

## Sources de données

| Source | Lag | Usage |
|--------|-----|-------|
| ERA5 (Copernicus) | 5 jours | Estimation précise |
| Open-Meteo | Temps réel | Estimation rapide |
| NASA GISS | ~15 jours | Résolution officielle |
| NOAA NCEI | ~2 semaines | Validation croisée |

## Structure

```
├── climate_edge_v3.py      # Script principal d'analyse
├── climate_state_v2.json   # État actuel des estimations
├── era5_fetcher.py         # (TODO) Fetcher Copernicus ERA5
├── calibration.py          # (TODO) Calibration ERA5 → GISS
└── README.md
```

## Usage

```bash
# Lancer l'analyse
python3 climate_edge_v3.py

# Résultat dans climate_state_v2.json
```

## Roadmap

- [x] v1: Sampling global Open-Meteo
- [x] v2: Intégration ERA5 historique  
- [x] v3: Calibration ERA5/Open-Meteo hybride
- [ ] v4: API Copernicus CDS pour ERA5 temps réel
- [ ] v5: Backtesting sur données historiques

## ⚠️ Limitations actuelles

- Échantillonnage Open-Meteo biaisé vers les terres
- Pas encore d'accès ERA5 temps réel (Copernicus CDS)
- Edge estimé mais non confirmé

## Licence

Privé - Usage personnel uniquement.
