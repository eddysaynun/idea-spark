export const pendingDeletionFrom = (error) => {
  const detail = error?.response?.data?.detail;
  return detail?.code === 'account_deletion_pending' ? detail : null;
};
