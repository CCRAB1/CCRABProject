# CCRAB API Client

JavaScript client for the CCRAB Dashboard REST API. This package mirrors the
Python `datautilities.ccrab_api.client` API for use from the dashboard's static
JavaScript directory. It uses the built-in `fetch` implementation available in
Node 18 and newer, plus the vendored Luxon copy in `static/vendor/luxon` for
date-time formatting.

## Location

The client lives in the dashboard static JavaScript tree:

```text
/Users/danramage/Documents/workspace/CCRAB/CCRABProject/apps/CCRABDashBoard/static/js/CCRABApiClient
```

## Usage

```js
import { CCRABRestClient } from "@ccrab/api-client";

const client = await CCRABRestClient.fromCredentials("username", "password", {
  baseUrl: "http://127.0.0.1:8000",
});

const projects = await client.listProjects({
  q: "air",
  projectType: "monitoring",
});

const platformData = await client.getPlatformData(
  new Date(2026, 0, 2, 8, 0, 0),
  new Date(2026, 0, 2, 12, 0, 0),
  "purple-air-1",
  ["pm25", "temperature"],
);
```

You can also construct the client with existing JWTs:

```js
const client = new CCRABRestClient({
  baseUrl: "https://dashboard.example.org",
  accessToken: process.env.CCRAB_ACCESS_TOKEN,
  refreshToken: process.env.CCRAB_REFRESH_TOKEN,
});

const platform = await client.getPlatform("hampton-st");
```

## API

The package exports:

- `CCRABRestClient`
- `CCRABApiError`
- `CCRABAuthenticationError`
- `TokenBundle`
- `DEFAULT_BASE_URL`

`CCRABRestClient` includes these endpoint helpers:

- `registerUser(username, password, { email, storeTokens })`
- `obtainToken(username, password)`
- `authenticate(username, password)`
- `refreshAccessToken()`
- `listProjects(options)`
- `projectFacets()`
- `getProject(code)`
- `getProjectProducts(code)`
- `listPlatforms(options)`
- `getPlatform(shortName, options)`
- `legacyPlatformInfo(options)`
- `platformConfiguration(options)`
- `getPlatformConfiguration(options)`
- `getPlatformData(startDate, endDate, platformHandle, observations, params)`
- `get(path, options)`
- `post(path, options)`
- `request(method, path, options)`

Requests automatically add a bearer token when available. If an authenticated
request returns `401` and a refresh token is available, the client refreshes the
access token once and retries the original request.

## Tests

```sh
npm test
```
