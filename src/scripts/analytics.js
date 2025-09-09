import {
  GA4,
  helpers,
} from "@nationalarchives/frontend/nationalarchives/analytics.mjs";

const ga4Id = document.documentElement.getAttribute("data-ga4id");
if (ga4Id) {
  const analytics = new GA4({ id: ga4Id });

  analytics.addListeners("#results", "results", [
    {
      eventName: "select_result",
      on: "click",
      targetElement: ".tna-card__heading-link",
      data: {
        state: ($el) =>
          parseInt($el.closest(".tna-card")?.dataset.resultPosition || "0"),
        value: helpers.valueGetters.text,
      },
    },
  ]);
}
