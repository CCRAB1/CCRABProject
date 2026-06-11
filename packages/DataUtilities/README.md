# Data Utilities

This is the package repo for what will be various APIs and other
remote data interfaces to pull data in for the CCRAB project.

## TSI Link External API

```python
from datautilities.tsi_api import TSIExternalAPIClient

client = TSIExternalAPIClient.from_client_credentials(
    client_id="your-client-id",
    client_secret="your-client-secret",
)

devices = client.list_devices(model="8143", include_shared=True)
telemetry = client.get_flat_telemetry(
    age=1,
    telem=["serial", "model", "mcpm2x5", "temperature", "rh"],
)
```

The TSI client wraps the v3 external API endpoints for OAuth tokens, devices,
legacy devices, nested telemetry, legacy telemetry, CSV telemetry, and flat
telemetry.
