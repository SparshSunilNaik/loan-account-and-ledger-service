export type ThemePreference = "light" | "dark" | "system";
export const THEME_KEY = "ledgercore-studio-theme";
export function validTheme(value: unknown): ThemePreference {
  return value === "light" || value === "dark" ? value : "system";
}
export function resolveTheme(preference: ThemePreference, darkOS: boolean) {
  return preference === "system" ? (darkOS ? "dark" : "light") : preference;
}
// Static trusted source only. Executes synchronously in <head>, before body paint.
// The same resolvers are serialized so bootstrap and hydrated controls cannot diverge.
export const THEME_BOOTSTRAP = `(()=>{const valid=${validTheme.toString()};const resolve=${resolveTheme.toString()};let p="system";try{p=valid(localStorage.getItem(${JSON.stringify(THEME_KEY)}))}catch{}const root=document.documentElement;root.dataset.themePreference=p;root.dataset.theme=resolve(p,matchMedia("(prefers-color-scheme: dark)").matches)})()`;
