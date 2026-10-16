/** Typed API client for Cobalt Workbench backend. */

const API_BASE = import.meta.env.VITE_API_BASE || ''

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { params, headers, ...init } = options
  const url = new URL(path, API_BASE || window.location.origin)
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) url.searchParams.set(key, String(value))
    })
  }

  const response = await fetch(url.toString(), {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    credentials: 'include',
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }))
    throw new Error(error.message || `HTTP ${response.status}`)
  }

  if (response.status === 204) return undefined as T
  return response.json()
}

export const api = {
  get: <T>(path: string, params?: RequestOptions['params']) => request<T>(path, { method: 'GET', params }),
  post: <T>(path: string, body: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) => request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}

/** Health check types */
export interface HealthResponse {
  status: string
  service: string
  version: string
  environment: string
}

/** ACP types */
export interface FoldStats {
  fold_id: string
  original_tokens: number
  folded_tokens: number
  compression_ratio: number
  anchor_count: number
  covered_message_count: number
  created_at: string
}

export interface SessionSummary {
  session_id: string
  agent_namespace: string
  conversation_id: string
  total_messages: number
  total_original_tokens: number
  total_folded_tokens: number
  overall_compression_ratio: number
  fold_count: number
  last_fold_at: string | null
}

export interface ACPStatusResponse {
  enabled: boolean
  default_window_tokens: number
  compression_target_ratio: number
  fold_threshold_tokens: number
  active_sessions: number
  total_folds: number
  total_tokens_saved: number
  sessions: SessionSummary[]
  recent_folds: FoldStats[]
}

export interface CompressRequest {
  messages: Record<string, unknown>[]
  window_tokens?: number
  preserve_recent?: number
}

export interface CompressResponse {
  folded_messages: Record<string, unknown>[]
  fold_anchors: Record<string, unknown>[]
  original_tokens: number
  folded_tokens: number
  compression_ratio: number
  fold_id: string
}

export interface DecompressRequest {
  folded_messages: Record<string, unknown>[]
  fold_anchors: Record<string, unknown>[]
}

export interface DecompressResponse {
  messages: Record<string, unknown>[]
  restored_count: number
}

/** API functions */
export async function getHealth(): Promise<HealthResponse> {
  return api.get('/health')
}

export async function getACPStatus(): Promise<ACPStatusResponse> {
  return api.get('/acp/status')
}

export async function compressHistory(request: CompressRequest): Promise<CompressResponse> {
  return api.post('/acp/compress', request)
}

export async function decompressHistory(request: DecompressRequest): Promise<DecompressResponse> {
  return api.post('/acp/decompress', request)
}