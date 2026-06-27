# Vendored JavaScript

This directory contains the minimal third-party JavaScript artifacts served by
the CCRAB Dashboard. Keep only runtime files needed by the app plus the
corresponding license files.

## Current Assets

- `alpinejs/3.15.12/module.esm.min.js`
  - Source package: `alpinejs`
  - Upstream: https://github.com/alpinejs/alpine
  - License: MIT, see `alpinejs/3.15.12/LICENSE.md`
- `luxon/3.7.2/luxon.min.js`
  - Source package: `luxon`
  - Upstream: https://github.com/moment/luxon
  - License: MIT, see `luxon/3.7.2/LICENSE.md`
- `timeseries-ts/1.0.7/index.js`
  - Source package: `@eagle-io/timeseries`
  - Upstream: https://github.com/eagle-io/timeseries
  - License: MIT, see `timeseries-ts/1.0.7/LICENSE`

When upgrading a dependency, add the new version in its own directory and update
the application imports/templates to point at the new versioned path.
