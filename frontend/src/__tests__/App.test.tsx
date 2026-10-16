import { describe, it, expect, vi, beforeEach, Mock } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import App from '../App'
import * as api from '../api/client'

vi.mock('../api/client', () => ({
  getHealth: vi.fn(),
  getACPStatus: vi.fn(),
  compressHistory: vi.fn(),
  decompressHistory: vi.fn(),
}))

const mockGetHealth = api.getHealth as Mock
const mockGetACPStatus = api.getACPStatus as Mock

describe('App', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders loading state initially', () => {
    mockGetHealth.mockResolvedValue(null)
    mockGetACPStatus.mockResolvedValue(null)

    render(<App />)

    expect(screen.getByText('Loading Cobalt Workbench...')).toBeInTheDocument()
  })

  it('renders health status and ACP stats after load', async () => {
    const mockHealth = {
      status: 'healthy',
      service: 'cobalt-workbench',
      version: '1.0.0',
      environment: 'development',
    }
    const mockAcpStatus = {
      enabled: true,
      default_window_tokens: 100000,
      compression_target_ratio: 0.2,
      fold_threshold_tokens: 80000,
      active_sessions: 2,
      total_folds: 9,
      total_tokens_saved: 1280000,
      sessions: [
        {
          session_id: 'sess_01abc',
          agent_namespace: 'dsh',
          conversation_id: 'conv_123',
          total_messages: 1250,
          total_original_tokens: 1250000,
          total_folded_tokens: 250000,
          overall_compression_ratio: 0.2,
          fold_count: 7,
          last_fold_at: '2026-10-15T14:32:00Z',
        },
      ],
      recent_folds: [
        {
          fold_id: 'fold_001',
          original_tokens: 180000,
          folded_tokens: 36000,
          compression_ratio: 0.2,
          anchor_count: 15,
          covered_message_count: 180,
          created_at: '2026-10-15T14:32:00Z',
        },
      ],
    }

    mockGetHealth.mockResolvedValue(mockHealth)
    mockGetACPStatus.mockResolvedValue(mockAcpStatus)

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Backend: healthy')).toBeInTheDocument()
      expect(screen.getByText('ACP: healthy')).toBeInTheDocument()
    })

    expect(screen.getByText('2')).toBeInTheDocument() // active sessions
    expect(screen.getByText('9')).toBeInTheDocument() // total folds
    expect(screen.getByText('1,280,000')).toBeInTheDocument() // tokens saved
    expect(screen.getByText('sess_01abc')).toBeInTheDocument()
    expect(screen.getByText('dsh')).toBeInTheDocument()
    expect(screen.getByText('fold_001')).toBeInTheDocument()
  })

  it('displays error banner on API failure', async () => {
    mockGetHealth.mockRejectedValue(new Error('Connection refused'))
    mockGetACPStatus.mockRejectedValue(new Error('Connection refused'))

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Connection refused')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
    })
  })

  it('shows empty state when no sessions', async () => {
    mockGetHealth.mockResolvedValue({
      status: 'healthy',
      service: 'cobalt-workbench',
      version: '1.0.0',
      environment: 'development',
    })
    mockGetACPStatus.mockResolvedValue({
      enabled: true,
      default_window_tokens: 100000,
      compression_target_ratio: 0.2,
      fold_threshold_tokens: 80000,
      active_sessions: 0,
      total_folds: 0,
      total_tokens_saved: 0,
      sessions: [],
      recent_folds: [],
    })

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('No active sessions. Start a conversation through your AI client.')).toBeInTheDocument()
      expect(screen.getByText('No folds yet. Compression runs automatically when threshold is reached.')).toBeInTheDocument()
    })
  })
})