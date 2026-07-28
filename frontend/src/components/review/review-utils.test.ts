import { describe, expect, it } from "vitest";

import { formatReviewError, removeReviewQueueEntry, reviewOutcomeMessage } from "./review-utils";

describe("Review Queue state helpers", () => {
  it("removes only the reviewed proposal without mutating the source queue", () => {
    const queue = [{ id: "proposed-a" }, { id: "proposed-b" }];

    expect(removeReviewQueueEntry(queue, "proposed-a")).toEqual([{ id: "proposed-b" }]);
    expect(queue).toEqual([{ id: "proposed-a" }, { id: "proposed-b" }]);
  });

  it("reports lifecycle and missing-target failures without treating them as success", () => {
    expect(formatReviewError({ status: 400, message: "Replacement Entry must be proposed" })).toContain(
      "lifecycle",
    );
    expect(formatReviewError({ status: 404, message: "Not found" })).toContain("canon 또는 anchor");
    expect(formatReviewError(new TypeError("Failed to fetch"))).toContain("네트워크");
  });

  it("describes both lifecycle states after a supersede", () => {
    expect(
      reviewOutcomeMessage("supersede", {
        old_entry: { status: "superseded" },
        new_entry: { status: "canon" },
      }),
    ).toContain("새 Entry는 canon, 기존 canon은 superseded");
  });
});
