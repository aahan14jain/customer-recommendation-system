type AppRouterInstance = {
  back: () => void
  forward: () => void
  refresh: () => void
  push: (href: string, options?: object) => void
  prefetch: (href: string) => void
  replace: (href: string, options?: object) => void
}

/**
 * Shared mock for the App Router (`next/navigation`).
 * Import `appRouterMock` in tests to assert on navigation calls.
 */
export const appRouterMock: AppRouterInstance = {
  back: jest.fn(),
  forward: jest.fn(),
  refresh: jest.fn(),
  push: jest.fn(),
  prefetch: jest.fn(),
  replace: jest.fn(),
}

export function useRouter(): AppRouterInstance {
  return appRouterMock
}

export function usePathname(): string {
  return '/'
}

export function useSearchParams(): ReadonlyURLSearchParams {
  return new URLSearchParams() as ReadonlyURLSearchParams
}

export function useParams<T extends Record<string, string | string[]>>(): T {
  return {} as T
}

export function redirect(): never {
  throw new Error('NEXT_REDIRECT')
}

export function permanentRedirect(): never {
  throw new Error('NEXT_REDIRECT')
}

export function notFound(): never {
  throw new Error('NEXT_NOT_FOUND')
}

export function useSelectedLayoutSegment(): string | null {
  return null
}

export function useSelectedLayoutSegments(): string[] {
  return []
}
