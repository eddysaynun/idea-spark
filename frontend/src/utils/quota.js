export const clampGenerationCount = (count, remaining) => {
  if (remaining < 1) return 0;
  return Math.min(remaining, Math.max(1, Number.parseInt(count, 10) || 1));
};
