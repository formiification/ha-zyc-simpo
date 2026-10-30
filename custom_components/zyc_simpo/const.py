"""Constants for the ZYC Simpo integration."""
from __future__ import annotations

DOMAIN = "zyc_simpo"

CONF_HOST = "host"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 60  # seconds
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 3600

# Persisted module set survives restarts (helpers.storage.Store).
STORAGE_VERSION = 1
# Re-scan for added/removed modules every N polls.
REDISCOVER_EVERY = 20
# Drop a known module only after this many consecutive successful re-scans
# find it absent — long enough that a transient/maintenance outage is kept and
# recovers, but a physically removed module is eventually cleaned up. Reversible:
# if it comes back it is re-added with its history. At the defaults this is about
# an hour (REDISCOVER_EVERY * PRUNE_AFTER_MISSED_SCANS * scan interval).
PRUNE_AFTER_MISSED_SCANS = 3

MANUFACTURER = "ZYC Energy"
MODEL = "Simpo 5000"

# Warning thresholds derived from the confirmed telemetry (per module),
# sized for a 16S ~51.2 V LiFePO4 module. These are safety heuristics, not the
# BMS's own protection flags; tune to taste.
WARN_VOLT_HIGH = 57.6  # V  (~3.60 V/cell)
WARN_VOLT_LOW = 44.8   # V  (~2.80 V/cell)
WARN_TEMP_HIGH = 55    # °C
WARN_TEMP_LOW_CHARGE = 0  # °C  (charging below freezing is harmful)
WARN_CURRENT_HIGH = 110   # A  magnitude per module (rated ~100 A)
WARN_CELL_IMBALANCE_MV = 50  # mV  cell max-min spread
