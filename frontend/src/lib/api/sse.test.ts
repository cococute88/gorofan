import { describe, expect, it } from "vitest";

import { parseFrame } from "./sse";

describe("parseFrame", () => {
  it("parses a token frame", () => {
    const evt = parseFrame('event: token\ndata: {"delta":"안녕"}');
    expect(evt).toEqual({ event: "token", data: { delta: "안녕" } });
  });

  it("parses a done frame", () => {
    const evt = parseFrame('event: done\ndata: {"message_id":"m1","token_count":3}');
    expect(evt?.event).toBe("done");
    expect(evt?.data.message_id).toBe("m1");
  });

  it("parses an error frame", () => {
    const evt = parseFrame('event: error\ndata: {"code":"PROVIDER_ERROR","message":"boom"}');
    expect(evt?.event).toBe("error");
    expect(evt?.data.code).toBe("PROVIDER_ERROR");
  });

  it("returns null for frames without data", () => {
    expect(parseFrame(": keep-alive comment")).toBeNull();
    expect(parseFrame("")).toBeNull();
  });

  it("returns null for malformed JSON", () => {
    expect(parseFrame("event: token\ndata: {not json}")).toBeNull();
  });
});
