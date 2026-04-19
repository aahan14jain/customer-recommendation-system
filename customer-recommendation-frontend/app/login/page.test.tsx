import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { PropsWithChildren } from 'react'
import { appRouterMock } from '@/__mocks__/next/navigation'
import { ROUTES } from '@/lib/routes'
import LoginPage from './page'

jest.mock('next/link', () => ({
  __esModule: true,
  default({
    children,
    href,
    ...rest
  }: PropsWithChildren<{ href: string }>) {
    return (
      <a href={href} {...rest}>
        {children}
      </a>
    )
  },
}))

const mockFetch = jest.fn() as jest.MockedFunction<typeof fetch>

function mockLoginResponse(
  overrides: Partial<Response> & {
    jsonData?: { access?: string; refresh?: string; detail?: string }
  },
) {
  const { jsonData = {}, ok = true, status = ok ? 200 : 401, ...rest } =
    overrides
  return {
    ok,
    status,
    json: async () => jsonData,
    ...rest,
  } as Response
}

describe('LoginPage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    localStorage.clear()
    global.fetch = mockFetch
  })

  it('renders username and password fields and the login button', () => {
    mockFetch.mockResolvedValue(mockLoginResponse({ ok: false, jsonData: {} }))

    render(<LoginPage />)

    expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /log in/i }),
    ).toBeInTheDocument()
  })

  it('submits credentials, stores tokens, and navigates on successful login', async () => {
    const user = userEvent.setup()
    mockFetch.mockResolvedValue(
      mockLoginResponse({
        ok: true,
        status: 200,
        jsonData: { access: 'test-access-token', refresh: 'test-refresh-token' },
      }),
    )

    render(<LoginPage />)

    await user.type(screen.getByLabelText(/username/i), 'alice')
    await user.type(screen.getByLabelText(/password/i), 'secret')
    await user.click(screen.getByRole('button', { name: /log in/i }))

    await waitFor(() => {
      expect(appRouterMock.push).toHaveBeenCalledWith(ROUTES.dashboard)
    })

    expect(localStorage.getItem('access_token')).toBe('test-access-token')
    expect(localStorage.getItem('refresh_token')).toBe('test-refresh-token')

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/auth\/login\/$/),
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: 'alice', password: 'secret' }),
      }),
    )
  })

  it('shows an error when the login API returns invalid credentials', async () => {
    const user = userEvent.setup()
    mockFetch.mockResolvedValue(
      mockLoginResponse({
        ok: false,
        status: 401,
        jsonData: { detail: 'Invalid credentials' },
      }),
    )

    render(<LoginPage />)

    await user.type(screen.getByLabelText(/username/i), 'bad')
    await user.type(screen.getByLabelText(/password/i), 'creds')
    await user.click(screen.getByRole('button', { name: /log in/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Invalid credentials')
    })

    expect(appRouterMock.push).not.toHaveBeenCalled()
    expect(localStorage.getItem('access_token')).toBeNull()
  })

  it('shows an error when fetch fails (network error)', async () => {
    const user = userEvent.setup()
    mockFetch.mockRejectedValue(new Error('Network failure'))

    render(<LoginPage />)

    await user.type(screen.getByLabelText(/username/i), 'alice')
    await user.type(screen.getByLabelText(/password/i), 'secret')
    await user.click(screen.getByRole('button', { name: /log in/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Invalid credentials')
    })

    expect(appRouterMock.push).not.toHaveBeenCalled()
  })

  it('disables the form and shows signing in while login is in progress', async () => {
    const user = userEvent.setup()
    let finishLogin!: (value: Response) => void
    const loginPending = new Promise<Response>((resolve) => {
      finishLogin = resolve
    })
    mockFetch.mockReturnValueOnce(loginPending)

    render(<LoginPage />)

    await user.type(screen.getByLabelText(/username/i), 'alice')
    await user.type(screen.getByLabelText(/password/i), 'secret')
    await user.click(screen.getByRole('button', { name: /log in/i }))

    const submitButton = await screen.findByRole('button', { name: /signing in/i })
    expect(submitButton).toBeDisabled()
    expect(screen.getByLabelText(/username/i)).toBeDisabled()
    expect(screen.getByLabelText(/password/i)).toBeDisabled()

    finishLogin(
      mockLoginResponse({
        ok: true,
        status: 200,
        jsonData: { access: 'token' },
      }),
    )

    await waitFor(() => {
      expect(appRouterMock.push).toHaveBeenCalledWith(ROUTES.dashboard)
    })
  })
})
