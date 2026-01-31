# Polymarket Climate Edge

🌡️ Analyse climatique pour opportunités Polymarket - Estimation janvier 2026

## 🎯 Status Actuel (31/01/2026)

**✅ Fonctionnel**: Téléchargement données, parsing NetCDF  
**❌ Problème**: Calibration ERA5T→GISS cassée (-5.08°C impossible)  
**✅ Fiable**: Open-Meteo donne ~1.02°C d'anomalie (réaliste)

## 📊 Derniers Résultats

```
ERA5T (25 jours): 4.52°C global → -5.08°C anomalie (CASSÉ)
Open-Meteo (30 jours): 11.17°C → 1.02°C anomalie ✅
Estimation finale: ~1.02°C (rang #6-7 janvier le plus chaud)
```

**Implication marchés**: Pas d'edge évident, "4th or lower" semble correct

## ⚠️ Problèmes Identifiés

### 1. Calibration ERA5T Défectueuse
- ERA5T raw: 4.52°C (normal pour moyenne globale)
- Conversion GISS: -5.08°C (impossible, erreur de formule)
- **Urgence**: Recalibrer ERA5T→GISS avec vraie baseline

### 2. Fiabilité Sources
- **Open-Meteo**: Cohérent, résultats plausibles ✅
- **ERA5T**: Télécharge bien, calibration foireuse ❌  
- **Recommandation**: Open-Meteo primary jusqu'au fix ERA5T

## 🔧 Setup Rapide

```bash
# Dependencies
pip install -r requirements.txt

# CDS API (pour ERA5T)
echo "url: https://cds.climate.copernicus.eu/api\nkey: YOUR_KEY" > ~/.cdsapirc

# Run
python era5t_january2026.py
```

## 🚀 Améliorations Prioritaires

### Court terme (urgent)
1. **Fixer calibration ERA5T** - baseline GISS correcte
2. **Plus de points Open-Meteo** - coverage géographique
3. **Validation résultats** - sanity checks anomalies

### Moyen terme  
4. **Backtesting** - valider sur mois connus
5. **Error handling** - API failures gracieux
6. **Auto-update** - run quotidien automatisé

## 📁 Structure Code

```
├── era5t_january2026.py     # Script principal (TESTÉ ✅)
├── climate_edge_v3.py       # Analyseur Polymarket original  
├── era5_fetcher.py          # Fetcher Copernicus
├── january_2026_state.json  # État actuel analyse
├── requirements.txt         # Dependencies Python
└── README.md               # Cette doc
```

## 🎯 Marchés Ciblés

| Marché | Volume | Notre estimation | Edge? |
|--------|--------|------------------|-------|
| Temp >1.19°C | ~$594k | Peu probable | ❌ |
| Ranking "4th or lower" | ~$334k | Probable | ✅ Confirme |
| 2026 annual ranking | ~$1M+ | TBD | ? |

## 💡 Observations

**Points forts**:
- ERA5T télécharge 143MB en 4s (efficace)
- NetCDF parsing fonctionne  
- Open-Meteo stable et fiable

**Points faibles**:
- Formule calibration complètement cassée
- Pas assez de points géographiques
- Pas de validation historique

**Conclusion**: Outil prometteur mais needs calibration fix avant utilisation réelle.

---
*Last update: 31/01/2026 - Tests OK, calibration KO*