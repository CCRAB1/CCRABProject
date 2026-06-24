import assert from "node:assert/strict";
import test from "node:test";

import {
  CCRABAuthenticationError,
  CCRABRestClient,
  TokenBundle,
} from "../src/index.js";
import { DateTime } from "../../luxon/src/luxon.js";

test("obtainToken posts credentials and stores returned tokens", async () => {
  const fetch = createFakeFetch([
    jsonResponse({ access: "access-token", refresh: "refresh-token" }),
  ]);
  const client = new CCRABRestClient({
    baseUrl: "https://ccrab.example",
    fetchFn: fetch.fn,
  });

  const payload = await client.obtainToken("dan", "secret");

  assert.deepEqual(payload, {
    access: "access-token",
    refresh: "refresh-token",
  });
  assert.deepEqual(client.tokens, new TokenBundle("access-token", "refresh-token"));
  assert.equal(fetch.requests.length, 1);
  assert.equal(fetch.requests[0].url, "https://ccrab.example/api/token/");
  assert.equal(fetch.requests[0].options.method, "POST");
  assert.equal(fetch.requests[0].options.headers["Content-Type"], "application/json");
  assert.equal(fetch.requests[0].options.headers.Authorization, undefined);
  assert.deepEqual(JSON.parse(fetch.requests[0].options.body), {
    username: "dan",
    password: "secret",
  });
});

test("listProjects sends bearer token and cleans empty query params", async () => {
  const fetch = createFakeFetch([
    jsonResponse([{ code: "AIR-1", name: "Air Sensors" }]),
  ]);
  const client = new CCRABRestClient({
    baseUrl: "https://ccrab.example/",
    accessToken: "access-token",
    fetchFn: fetch.fn,
  });

  const projects = await client.listProjects({
    q: "air",
    projectType: "monitoring",
    neighborhood: "",
    region: null,
    page: 2,
  });

  assert.deepEqual(projects, [{ code: "AIR-1", name: "Air Sensors" }]);
  const requestUrl = new URL(fetch.requests[0].url);
  assert.equal(requestUrl.origin, "https://ccrab.example");
  assert.equal(requestUrl.pathname, "/api/projects/");
  assert.equal(requestUrl.searchParams.get("q"), "air");
  assert.equal(requestUrl.searchParams.get("project_type"), "monitoring");
  assert.equal(requestUrl.searchParams.get("page"), "2");
  assert.equal(requestUrl.searchParams.has("neighborhood"), false);
  assert.equal(requestUrl.searchParams.has("region"), false);
  assert.equal(
    fetch.requests[0].options.headers.Authorization,
    "Bearer access-token",
  );
});

test("getPlatform encodes path parts and formats bbox arrays", async () => {
  const fetch = createFakeFetch([jsonResponse({ short_name: "north/site" })]);
  const client = new CCRABRestClient({
    baseUrl: "https://ccrab.example",
    accessToken: "access-token",
    fetchFn: fetch.fn,
  });

  const platform = await client.getPlatform("north/site", {
    bbox: [-80.1, 32.7, -79.9, 33.1],
  });

  assert.deepEqual(platform, { short_name: "north/site" });
  const requestUrl = new URL(fetch.requests[0].url);
  assert.equal(requestUrl.pathname, "/api/platforms/north%2Fsite/");
  assert.equal(requestUrl.searchParams.get("bbox"), "-80.1,32.7,-79.9,33.1");
});

test("getPlatformData formats dates and observation list", async () => {
  const fetch = createFakeFetch([jsonResponse([{ value: 3.4 }])]);
  const client = new CCRABRestClient({
    baseUrl: "https://ccrab.example",
    accessToken: "access-token",
    fetchFn: fetch.fn,
  });

  const data = await client.getPlatformData(
    new Date(2026, 0, 2, 3, 4, 5),
    DateTime.local(2026, 1, 2, 4, 4, 5),
    "purple-air-1",
    ["pm25", "temperature"],
    { aggregate: "hourly" },
  );

  assert.deepEqual(data, [{ value: 3.4 }]);
  const requestUrl = new URL(fetch.requests[0].url);
  assert.equal(requestUrl.pathname, "/api/v1/platform_data_request/");
  assert.equal(requestUrl.searchParams.get("start_date"), "2026-01-02T03:04:05");
  assert.equal(requestUrl.searchParams.get("end_date"), "2026-01-02T04:04:05");
  assert.equal(requestUrl.searchParams.get("platform_handle"), "purple-air-1");
  assert.equal(requestUrl.searchParams.get("observations"), "pm25,temperature");
  assert.equal(requestUrl.searchParams.get("aggregate"), "hourly");
});

test("default browser fetch keeps the global receiver", async () => {
  const originalFetch = globalThis.fetch;
  const requests = [];

  globalThis.fetch = async function (url, options = {}) {
    assert.equal(this, globalThis);
    requests.push({ url, options });
    return jsonResponse([{ code: "AIR-1" }]);
  };

  try {
    const client = new CCRABRestClient({
      baseUrl: "https://ccrab.example",
    });

    const projects = await client.listProjects();

    assert.deepEqual(projects, [{ code: "AIR-1" }]);
    assert.equal(requests.length, 1);
    assert.equal(requests[0].url, "https://ccrab.example/api/projects/");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("request refreshes access token once after a 401 response", async () => {
  const fetch = createFakeFetch([
    jsonResponse({ detail: "expired" }, { status: 401 }),
    jsonResponse({ access: "new-access", refresh: "same-refresh" }),
    jsonResponse([{ code: "AIR-1" }]),
  ]);
  const client = new CCRABRestClient({
    baseUrl: "https://ccrab.example",
    accessToken: "old-access",
    refreshToken: "same-refresh",
    fetchFn: fetch.fn,
  });

  const projects = await client.listProjects();

  assert.deepEqual(projects, [{ code: "AIR-1" }]);
  assert.equal(fetch.requests.length, 3);
  assert.equal(
    fetch.requests[0].options.headers.Authorization,
    "Bearer old-access",
  );
  assert.equal(fetch.requests[1].url, "https://ccrab.example/api/token/refresh/");
  assert.equal(fetch.requests[1].options.headers.Authorization, undefined);
  assert.deepEqual(JSON.parse(fetch.requests[1].options.body), {
    refresh: "same-refresh",
  });
  assert.equal(
    fetch.requests[2].options.headers.Authorization,
    "Bearer new-access",
  );
});

test("non-success responses raise typed errors with status and payload", async () => {
  const fetch = createFakeFetch([
    jsonResponse({ detail: "Permission denied" }, { status: 403 }),
  ]);
  const client = new CCRABRestClient({
    baseUrl: "https://ccrab.example",
    accessToken: "access-token",
    fetchFn: fetch.fn,
  });

  await assert.rejects(
    () => client.getProject("restricted"),
    (error) => {
      assert.equal(error instanceof CCRABAuthenticationError, true);
      assert.equal(error.statusCode, 403);
      assert.deepEqual(error.payload, { detail: "Permission denied" });
      assert.match(error.message, /CCRAB API request failed with status 403/);
      return true;
    },
  );
});

function createFakeFetch(responses) {
  const requests = [];
  return {
    requests,
    fn: async (url, options = {}) => {
      requests.push({ url, options });
      const response = responses.shift();
      assert.ok(response, `Unexpected request to ${url}`);
      return response;
    },
  };
}

function jsonResponse(payload, { status = 200, url = "https://ccrab.example" } = {}) {
  const response = new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
  Object.defineProperty(response, "url", {
    value: url,
  });
  return response;
}
