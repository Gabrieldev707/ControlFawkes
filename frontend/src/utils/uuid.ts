export const generateId = (): string => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for non-secure contexts (e.g., local network HTTP)
  return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
};
