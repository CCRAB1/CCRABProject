import { DateTime } from "../../../vendor/luxon/3.7.2/luxon.min.js";

const DEFAULT_TIMEOUT_MS = 30000;
const API_DATE_TIME_FORMAT = "yyyy-MM-dd'T'HH:mm:ss";

export const DEFAULT_BASE_URL = "https://159.203.109.18.sslip.io/";
//export const DEFAULT_BASE_URL = "http://127.0.0.1:8000";

export class TokenBundle {
  constructor(access, refresh = null) {
    this.access = access;
    this.refresh = refresh;
  }
}

export class CCRABApiError extends Error {
  constructor(
    message,
    { statusCode = null, url = null, payload = null, response = null } = {},
  ) {
    super(message);
    this.name = "CCRABApiError";
    this.statusCode = statusCode;
    this.url = url;
    this.payload = payload;
    this.response = response;
  }
}

export class CCRABAuthenticationError extends CCRABApiError {
  constructor(message, options = {}) {
    super(message, options);
    this.name = "CCRABAuthenticationError";
  }
}

export class CCRABRestClient {
  constructor(baseUrlOrOptions = DEFAULT_BASE_URL, options = {}) {
    let resolvedOptions = options;
    if (isPlainObject(baseUrlOrOptions)) {
      resolvedOptions = baseUrlOrOptions;
    } else {
      resolvedOptions = { ...options, baseUrl: baseUrlOrOptions };
    }

    this.baseUrl = stripTrailingSlash(
      resolvedOptions.baseUrl ?? DEFAULT_BASE_URL,
    );
    this.apiPrefix = stripSlashes(resolvedOptions.apiPrefix ?? "api");
    this.accessToken = resolvedOptions.accessToken ?? null;
    this.refreshToken = resolvedOptions.refreshToken ?? null;
    this.timeoutMs = resolveTimeoutMs(resolvedOptions);
    this.fetchFn = resolveFetchFn(resolvedOptions.fetchFn);

    if (typeof this.fetchFn !== "function") {
      throw new CCRABApiError(
        "CCRABRestClient requires a fetch implementation. Use Node 18+ or pass fetchFn.",
      );
    }
  }

  static async fromCredentials(username, password, options = {}) {
    const client = new CCRABRestClient(options);
    await client.obtainToken(username, password);
    return client;
  }

  static async fromRegistration(username, password, options = {}) {
    const { email = null, ...clientOptions } = options;
    const client = new CCRABRestClient(clientOptions);
    await client.registerUser(username, password, { email });
    return client;
  }

  get tokens() {
    if (!this.accessToken) {
      return null;
    }
    return new TokenBundle(this.accessToken, this.refreshToken);
  }

  setTokens(access, refresh = undefined) {
    this.accessToken = access;
    if (refresh !== undefined) {
      this.refreshToken = refresh;
    }
    return new TokenBundle(this.accessToken, this.refreshToken);
  }

  async registerUser(
    username,
    password,
    { email = null, storeTokens = true } = {},
  ) {
    const payload = {
      username,
      password,
    };

    if (email !== null && email !== undefined) {
      payload.email = email;
    }

    const data = await this.post("register/", {
      json: payload,
      auth: false,
    });
    if (storeTokens) {
      this.#storeTokensFromPayload(data);
    }
    return data;
  }

  async obtainToken(username, password) {
    const data = await this.post("token/", {
      json: {
        username,
        password,
      },
      auth: false,
    });
    this.#storeTokensFromPayload(data);
    return data;
  }

  async authenticate(username, password) {
    return this.obtainToken(username, password);
  }

  async refreshAccessToken() {
    if (!this.refreshToken) {
      throw new CCRABAuthenticationError("No refresh token is available.");
    }

    const data = await this.post("token/refresh/", {
      json: {
        refresh: this.refreshToken,
      },
      auth: false,
    });
    this.#storeTokensFromPayload(data);
    return data;
  }

  async listProjects({
    q = null,
    keywords = null,
    projectType = null,
    neighborhood = null,
    region = null,
    page = null,
    ...params
  } = {}) {
    const queryParams = this.#params(params, {
      q,
      keywords,
      project_type: projectType,
      neighborhood,
      region,
      page,
    });
    return this.get("projects/", { params: queryParams });
  }

  async projectFacets() {
    return this.get("projects/facets/");
  }

  async getProject(code) {
    return this.get(`projects/${this.#pathPart(code)}/`);
  }

  async getProjectProducts(code) {
    return this.get(`projects/${this.#pathPart(code)}/products/`);
  }

  async listPlatforms({ name = null, bbox = null, ...params } = {}) {
    const queryParams = this.#params(params, {
      name,
      bbox: this.#formatBbox(bbox),
    });
    return this.get("platforms/", { params: queryParams });
  }

  async getPlatform(shortName, { bbox = null, ...params } = {}) {
    const queryParams = this.#params(params, {
      bbox: this.#formatBbox(bbox),
    });
    return this.get(`platforms/${this.#pathPart(shortName)}/`, {
      params: queryParams,
    });
  }

  async legacyPlatformInfo({ name = null, bbox = null, ...params } = {}) {
    const queryParams = this.#params(params, {
      name,
      bbox: this.#formatBbox(bbox),
    });
    return this.get("v1/platform_info/", { params: queryParams });
  }

  async platformConfiguration({
    dataSource = "purple_air",
    ...params
  } = {}) {
    const queryParams = this.#params(params, {
      data_source: dataSource,
    });
    return this.get("v1/system/platform_configuration/", {
      params: queryParams,
    });
  }

  async getPlatformConfiguration(options = {}) {
    return this.platformConfiguration(options);
  }

  async getPlatformData(
    startDate,
    endDate,
    platformHandle,
    observations = [],
    params = {},
  ) {
    const queryParams = this.#params(params, {
      start_date: toApiDateTime(startDate),
      end_date: toApiDateTime(endDate),
      platform_handle: platformHandle,
      observations: observations.join(","),
    });
    return this.get("v1/platform_data_request/", { params: queryParams });
  }

  async get(path, options = {}) {
    return this.request("GET", path, options);
  }

  async post(path, options = {}) {
    return this.request("POST", path, options);
  }

  async request(method, path, options = {}) {
    const {
      auth = true,
      retryOnUnauthorized = true,
      headers = null,
      params = null,
      json = undefined,
      body = undefined,
      signal = null,
      timeoutMs = this.timeoutMs,
      ...fetchOptions
    } = options;

    const url = this.#url(path, params);
    const requestHeaders = this.#headers(headers, { auth });
    const requestOptions = {
      ...fetchOptions,
      method: method.toUpperCase(),
      headers: requestHeaders,
    };

    if (json !== undefined) {
      if (!hasHeader(requestHeaders, "content-type")) {
        requestHeaders["Content-Type"] = "application/json";
      }
      requestOptions.body = JSON.stringify(json);
    } else if (body !== undefined) {
      requestOptions.body = body;
    }

    const response = await this.#fetchWithTimeout(url, requestOptions, {
      signal,
      timeoutMs,
    });

    if (
      response.status === 401 &&
      auth &&
      retryOnUnauthorized &&
      this.refreshToken
    ) {
      await this.refreshAccessToken();
      return this.request(method, path, {
        ...options,
        retryOnUnauthorized: false,
      });
    }

    await this.#raiseForStatus(response);
    return decodeResponse(response);
  }

  #storeTokensFromPayload(payload) {
    const access = payload?.access;
    const refresh = payload?.refresh;

    if (!access) {
      throw new CCRABAuthenticationError(
        "Authentication response did not include an access token.",
        { payload },
      );
    }

    return this.setTokens(access, refresh);
  }

  #url(path, params = null) {
    let cleanPath = String(path).replace(/^\/+/, "");
    if (this.apiPrefix && cleanPath.startsWith(`${this.apiPrefix}/`)) {
      cleanPath = cleanPath.slice(this.apiPrefix.length + 1);
    }

    let url = this.apiPrefix
      ? `${this.baseUrl}/${this.apiPrefix}/${cleanPath}`
      : `${this.baseUrl}/${cleanPath}`;

    url = appendParams(url, params);
    return url;
  }

  #headers(headers, { auth }) {
    const requestHeaders = {};
    if (headers) {
      for (const [key, value] of Object.entries(headers)) {
        requestHeaders[key] = value;
      }
    }

    if (auth && this.accessToken) {
      requestHeaders.Authorization = `Bearer ${this.accessToken}`;
    }

    return requestHeaders;
  }

  #params(params = null, values = {}) {
    const merged = {};
    if (params) {
      for (const [key, value] of Object.entries(params)) {
        merged[key] = value;
      }
    }

    for (const [key, value] of Object.entries(values)) {
      merged[key] = value;
    }

    const cleaned = {};
    for (const [key, value] of Object.entries(merged)) {
      if (value === null || value === undefined || value === "") {
        continue;
      }
      cleaned[key] = value;
    }
    return cleaned;
  }

  #formatBbox(bbox) {
    if (bbox === null || bbox === undefined || bbox === "") {
      return null;
    }
    if (typeof bbox === "string") {
      return bbox;
    }
    if (!Array.isArray(bbox)) {
      throw new TypeError(
        "bbox must be a string or an array of [minLon, minLat, maxLon, maxLat].",
      );
    }
    if (bbox.length !== 4) {
      throw new RangeError(
        "bbox must contain minLon, minLat, maxLon, maxLat.",
      );
    }

    const values = [];
    for (const value of bbox) {
      values.push(String(value));
    }
    return values.join(",");
  }

  #pathPart(value) {
    const cleanValue = String(value).replace(/^\/+|\/+$/g, "");
    return encodeURIComponent(cleanValue).replace(/[!'()*]/g, (character) => {
      return `%${character.charCodeAt(0).toString(16).toUpperCase()}`;
    });
  }

  async #raiseForStatus(response) {
    if (response.status < 400) {
      return;
    }

    const payload = await safeJson(response);
    const url = response.url || null;
    let message = `CCRAB API request failed with status ${response.status}`;
    if (url) {
      message = `${message}: ${url}`;
    }

    const ErrorClass = response.status === 401 || response.status === 403
      ? CCRABAuthenticationError
      : CCRABApiError;

    throw new ErrorClass(message, {
      statusCode: response.status,
      url,
      payload,
      response,
    });
  }

  async #fetchWithTimeout(url, requestOptions, { signal, timeoutMs }) {
    if (!timeoutMs) {
      return this.fetchFn(url, { ...requestOptions, signal: signal ?? undefined });
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    const abortFromSignal = () => controller.abort(signal.reason);

    if (signal) {
      if (signal.aborted) {
        controller.abort(signal.reason);
      } else {
        signal.addEventListener("abort", abortFromSignal, { once: true });
      }
    }

    try {
      return await this.fetchFn(url, {
        ...requestOptions,
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeout);
      if (signal) {
        signal.removeEventListener("abort", abortFromSignal);
      }
    }
  }
}

async function decodeResponse(response) {
  if (response.status === 204) {
    return null;
  }

  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function safeJson(response) {
  try {
    return await response.clone().json();
  } catch {
    return null;
  }
}

function appendParams(url, params) {
  if (!params) {
    return url;
  }

  const searchParams = new URLSearchParams();
  if (params instanceof URLSearchParams) {
    for (const [key, value] of params.entries()) {
      searchParams.append(key, value);
    }
  } else if (Array.isArray(params)) {
    for (const [key, value] of params) {
      appendSearchParam(searchParams, key, value);
    }
  } else {
    for (const [key, value] of Object.entries(params)) {
      appendSearchParam(searchParams, key, value);
    }
  }

  const query = searchParams.toString();
  if (!query) {
    return url;
  }

  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}${query}`;
}

function appendSearchParam(searchParams, key, value) {
  if (value === null || value === undefined) {
    return;
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      appendSearchParam(searchParams, key, item);
    }
    return;
  }

  searchParams.append(key, String(value));
}

function hasHeader(headers, name) {
  const target = name.toLowerCase();
  for (const key of Object.keys(headers)) {
    if (key.toLowerCase() === target) {
      return true;
    }
  }
  return false;
}

function stripTrailingSlash(value) {
  return String(value).replace(/\/+$/g, "");
}

function stripSlashes(value) {
  return String(value).replace(/^\/+|\/+$/g, "");
}

function isPlainObject(value) {
  return (
    value !== null &&
    typeof value === "object" &&
    Object.getPrototypeOf(value) === Object.prototype
  );
}

function resolveFetchFn(fetchFn) {
  if (fetchFn !== undefined && fetchFn !== null) {
    return fetchFn;
  }

  return typeof globalThis.fetch === "function"
    ? globalThis.fetch.bind(globalThis)
    : globalThis.fetch;
}

function resolveTimeoutMs(options) {
  if (options.timeoutMs !== undefined) {
    return options.timeoutMs;
  }
  if (options.timeout !== undefined) {
    return options.timeout * 1000;
  }
  return DEFAULT_TIMEOUT_MS;
}

function toApiDateTime(value) {
  let dateTime;
  if (DateTime.isDateTime(value)) {
    dateTime = value;
  } else if (value instanceof Date) {
    dateTime = DateTime.fromJSDate(value);
  } else if (typeof value === "string") {
    dateTime = DateTime.fromISO(value, { setZone: true });
  } else {
    throw new TypeError(
      "Expected a Date, Luxon DateTime, or ISO-like date-time string.",
    );
  }

  if (!dateTime.isValid) {
    throw new TypeError(`Invalid date-time value: ${dateTime.invalidReason}`);
  }
  return dateTime.toFormat(API_DATE_TIME_FORMAT);
}
