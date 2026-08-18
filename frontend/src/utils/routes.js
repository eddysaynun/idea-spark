const PAGE_PATHS = {
  generate: '/',
  history: '/history',
  account: '/account',
  login: '/login',
  admin: '/admin',
  detail: '/detail',
  privacy: '/privacy',
  terms: '/terms',
  refund: '/refund',
};

export const pageFromPath = (pathname) => {
  if (pathname === '/auth/callback') return 'login';
  return Object.entries(PAGE_PATHS).find(([, path]) => path === pathname)?.[0] || 'generate';
};

export const pathForPage = (page) => PAGE_PATHS[page] || '/';
