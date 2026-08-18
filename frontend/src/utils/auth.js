export const registrationOptions = (username, captchaToken, emailRedirectTo) => ({
  emailRedirectTo,
  ...(captchaToken ? { captchaToken } : {}),
  data: { username: username.trim() },
});
