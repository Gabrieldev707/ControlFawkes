export function getDefaultDeviceName(userAgent: string = navigator.userAgent): string {
  if (/iPhone/i.test(userAgent)) return 'iPhone';
  if (/Android|Mobile/i.test(userAgent)) return 'Celular';
  return 'Navegador';
}
