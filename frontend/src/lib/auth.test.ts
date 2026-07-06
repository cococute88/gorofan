import { describe, expect, it } from "vitest";

import { parseAccessTokenFromHash } from "./auth";

describe("parseAccessTokenFromHash", () => {
  it("extracts a token from a fragment with leading #", () => {
    expect(parseAccessTokenFromHash("#access_token=ey.abc.123")).toBe("ey.abc.123");
  });

  it("extracts a token without the leading #", () => {
    expect(parseAccessTokenFromHash("access_token=tok")).toBe("tok");
  });

  it("ignores other fragment params", () => {
    expect(parseAccessTokenFromHash("#state=x&access_token=tok&foo=bar")).toBe("tok");
  });

  it("returns null when absent", () => {
    expect(parseAccessTokenFromHash("")).toBeNull();
    expect(parseAccessTokenFromHash("#error=denied")).toBeNull();
  });

  it("returns null for an empty token value", () => {
    expect(parseAccessTokenFromHash("#access_token=")).toBeNull();
  });
});
