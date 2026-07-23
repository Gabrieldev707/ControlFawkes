export const CURRENT_SCREENS = [
  'HOME',
  'REMOTE_CONTROL',
  'NAVIGATION',
  'TOUCHPAD',
  'KEYBOARD',
  'VOLUME',
  'PLATFORMS',
  'SETTINGS',
  'PAIRING',
] as const

export type CurrentScreen = (typeof CURRENT_SCREENS)[number]
export type NavigableScreen = Exclude<CurrentScreen, 'PAIRING'>
