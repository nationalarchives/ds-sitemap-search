import Cookies from "@nationalarchives/cookies";
import { initAll } from "@nationalarchives/frontend/nationalarchives/all.mjs";

initAll();

const cookies = new Cookies();
window.TNAFrontendCookies = cookies;

const setTheme = (theme) => {
  if (theme === "light") {
    document.documentElement.classList.remove(
      "tna-template--dark-theme",
      "tna-template--system-theme",
    );
  } else if (theme === "dark") {
    document.documentElement.classList.remove("tna-template--system-theme");
    document.documentElement.classList.add(`tna-template--dark-theme`);
  } else {
    document.documentElement.classList.remove("tna-template--dark-theme");
    document.documentElement.classList.add(`tna-template--system-theme`);
  }
};

const updateThemeFromCookie = () => {
  if (cookies.exists("theme")) {
    setTheme(cookies.get("theme"));
  } else {
    setTheme("system");
  }
};

if (cookies.preference("settings")) {
  updateThemeFromCookie();
} else {
  cookies.once("changePreference", (policies) => {
    if (policies.settings) {
      updateThemeFromCookie();
    }
  });
}
