import { describe, expect, it } from "vitest";

import { canReviewRecommendations, priorityColor } from "./recommendations";

describe("recommendation workspace helpers", () => {
  it("uses stable BCR priority bands", () => {
    expect(priorityColor({ benefit_cost_ratio: 6 })).toBe("#b42318");
    expect(priorityColor({ benefit_cost_ratio: 3 })).toBe("#d97706");
    expect(priorityColor({ benefit_cost_ratio: 1 })).toBe("#2563eb");
  });

  it("limits review actions to engineering and administration roles", () => {
    expect(canReviewRecommendations(["analyst"])).toBe(false);
    expect(canReviewRecommendations(["traffic_engineer"])).toBe(true);
    expect(canReviewRecommendations(["admin"])).toBe(true);
  });
});
