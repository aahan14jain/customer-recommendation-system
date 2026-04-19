/** @type {import('jest').Config} */
module.exports = {
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1',
    '^next/image$': '<rootDir>/__mocks__/next/image.tsx',
    '^next/router$': '<rootDir>/__mocks__/next/router.ts',
    '^next/navigation$': '<rootDir>/__mocks__/next/navigation.ts',
  },
  transform: {
    '^.+\\.(js|jsx|ts|tsx)$': 'babel-jest',
  },
}
