import type { NextRouter } from 'next/router'

/**
 * Shared mock router for the Pages Router (`next/router`).
 * Import `pagesRouterMock` in tests to assert on `push` / `replace`, etc.
 */
export const pagesRouterMock = {
  basePath: '',
  pathname: '/',
  route: '/',
  asPath: '/',
  query: {},
  isReady: true,
  isPreview: false,
  isLocaleDomain: false,
  locale: undefined,
  locales: undefined,
  defaultLocale: undefined,
  domainLocales: undefined,
  isFallback: false,
  forward: jest.fn(),
  push: jest.fn(),
  prefetch: jest.fn().mockResolvedValue(undefined),
  replace: jest.fn(),
  reload: jest.fn(),
  back: jest.fn(),
  beforePopState: jest.fn(),
  events: {
    on: jest.fn(),
    off: jest.fn(),
    emit: jest.fn(),
  },
} as unknown as NextRouter

export function useRouter(): NextRouter {
  return pagesRouterMock
}
