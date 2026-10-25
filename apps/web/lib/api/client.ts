import type {
  ApiErrorBody,
  ApiErrorEnvelope,
  CapabilitiesResponse,
  Certificate,
  Challenge,
  Event,
  HealthResponse,
  Run,
  RunCreate,
  Template,
} from "./types";

/**
 * Base URL for the ProofLayer API. Configurable only through
 * `NEXT_PUBLIC_API_BASE_URL`; the browser never talks to Nebius, OpenShell or
 * any other upstream provider directly.
 */
const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000/api/v1";

export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL;
}

export class ApiRequestError extends Error {
  readonly code: ApiErrorBody["code"];
  readonly requestId: string | null;
  readonly status: number;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = body.code;
    this.requestId = body.request_id;
  }
}

function isErrorEnvelope(value: unknown): value is ApiErrorEnvelope {
  return (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof (value as ApiErrorEnvelope).error === "object"
  );
}

async function requestRaw<T>(
  path: string,
  init?: RequestInit,
): Promise<{ data: T; response: Response }> {
  const url = `${getApiBaseUrl()}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: {
        Accept: "application/json",
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiRequestError(0, {
      code: "network_error",
      message: `Could not reach the ProofLayer API at ${url}.`,
      request_id: null,
    });
  }

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    if (isErrorEnvelope(body)) {
      throw new ApiRequestError(response.status, body.error);
    }
    throw new ApiRequestError(response.status, {
      code: "internal_error",
      message: `Request to ${path} failed with status ${response.status}.`,
      request_id: null,
    });
  }

  return { data: (await response.json()) as T, response };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const { data } = await requestRaw<T>(path, init);
  return data;
}

export function getHealth(init?: RequestInit): Promise<HealthResponse> {
  return request<HealthResponse>("/health", init);
}

export function getCapabilities(
  init?: RequestInit,
): Promise<CapabilitiesResponse> {
  return request<CapabilitiesResponse>("/capabilities", init);
}

export function getTemplates(init?: RequestInit): Promise<Template[]> {
  return request<Template[]>("/templates", init);
}

export function listRuns(
  limit = 50,
  init?: RequestInit,
): Promise<Run[]> {
  return request<Run[]>(`/runs?limit=${limit}`, init);
}

export interface CreateRunResult {
  run: Run;
  replayed: boolean;
}

/**
 * Creates a fixture run. `idempotencyKey` should be unique per user action
 * (e.g. one `crypto.randomUUID()` per "Launch run" click) so a retried
 * request replays the original run instead of creating a duplicate.
 */
export async function createRun(
  body: RunCreate,
  idempotencyKey: string,
  init?: RequestInit,
): Promise<CreateRunResult> {
  const { data, response } = await requestRaw<Run>("/runs", {
    ...init,
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
      ...init?.headers,
    },
    body: JSON.stringify(body),
  });
  return { run: data, replayed: response.headers.get("Idempotent-Replayed") === "true" };
}

export function getRun(runId: string, init?: RequestInit): Promise<Run> {
  return request<Run>(`/runs/${runId}`, init);
}

export function getRunEvents(
  runId: string,
  afterSeq = 0,
  limit = 1000,
  init?: RequestInit,
): Promise<Event[]> {
  return request<Event[]>(
    `/runs/${runId}/events?after_seq=${afterSeq}&limit=${limit}`,
    init,
  );
}

export function cancelRun(runId: string, init?: RequestInit): Promise<Run> {
  return request<Run>(`/runs/${runId}/cancel`, { ...init, method: "POST" });
}

export interface CertificateFetch {
  certificate: Certificate;
  /** `X-Certificate-SHA256`: digest of the exact JSON bytes served, from `certificates.json_sha256`. */
  certificateSha256: string | null;
}

/**
 * 404 ("Not ready") until the independent verifier has graded the run.
 * Callers should treat a 404 here as "no certificate yet", not an error.
 */
export async function getCertificate(
  runId: string,
  init?: RequestInit,
): Promise<CertificateFetch> {
  const { data, response } = await requestRaw<Certificate>(`/runs/${runId}/certificate`, init);
  return { certificate: data, certificateSha256: response.headers.get("X-Certificate-SHA256") };
}

export function listChallenges(runId: string, init?: RequestInit): Promise<Challenge[]> {
  return request<Challenge[]>(`/runs/${runId}/challenges`, init);
}

/**
 * Queues a proof challenge for a certified run. 409 if the run isn't
 * certified yet, has no recorded workspace, or already has one in progress;
 * 429 over the per-run limit — both carry a human-readable `message`.
 */
export function requestChallenge(runId: string, init?: RequestInit): Promise<Challenge> {
  return request<Challenge>(`/runs/${runId}/challenge`, { ...init, method: "POST" });
}
