# Historical Weather Ingestion and Crash Join

Weather ingestion replaces the climate module's assumed adverse-weather share with a
canonical hourly weather layer and explicit exposure denominators.

## Providers

- **Open-Meteo historical API** is the zero-credential pilot path. The adapter
  requests ERA5-Land explicitly, UTC hourly data, and caches the unchanged JSON
  response under `cache/weather/open_meteo/`. Open-Meteo requires attribution
  under CC BY 4.0 and identifies precipitation as the preceding-hour sum.
- **Copernicus CDS ERA5-Land** is the credentialed production path.
  `build_era5_land_request()` emits the dataset and request payload for
  `cdsapi`; deployments retain downloads under their weather cache. ERA5-Land
  is CC BY 4.0 and should cite DOI `10.24381/cds.e2161bac`.
- **Official ISTAT/Bari weather fields** remain the event-reported categorical
  reference. `harmonize_official_weather()` maps source labels without
  overwriting them.

Canonical observations carry grid identity and centroid, UTC timestamp,
temperature, precipitation, snow depth, wind and gust speed, provider code,
derived condition, source, resolution, and quality flags.

## Join and exposure policy

Crashes with a timestamp are matched to the nearest provider hour within 90
minutes and flagged `nearest_hour`. Date-only legacy records use a same-day
noon proxy and are explicitly flagged `date_noon_proxy`; they are never
presented as hour-precise.

`condition_hour_exposure.csv` records wet, freezing/snow, high-wind, fog, and
total observed hours per segment-year. Downstream models can therefore compare
crash rates per condition-hour rather than raw adverse-weather crash counts.
With the current point-source pilot, the closest Bari provider grid represents
all linked segments; production multi-grid runs should request enough grid
points to preserve spatial weather variation.

## Bari command

```bash
PYTHONPATH=src python3 tools/bari_weather_join.py
```

The command reads official matched Bari crashes, fetches or reuses cached
ERA5-Land data through Open-Meteo, and writes:

- `crash_weather_join.csv`;
- `condition_hour_exposure.csv`;
- `weather_agreement.json`;
- `weather_join.manifest.json` with hashes, governance, and attribution.

For an already downloaded response, pass `--weather-json path.json`. The
agreement report compares the derived broad condition to the official
categorical field only where that field can be harmonized. Reanalysis is not
ground truth at street scale, and disagreement should trigger source/threshold
review rather than automatic correction of the official record.

HTTPS verification remains mandatory. If the host Python installation cannot
locate its CA bundle, configure the operating environment's certificate store
or use a response downloaded through an independently verified channel; the
adapter does not provide an insecure TLS bypass.
