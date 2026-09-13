import { afterEach, describe, expect, it, vi } from "vitest";

import { parseFrame, streamSSE } from "./sse";
import wire from "./fixtures/novel-sse.json";

afterEach(() => vi.unstubAllGlobals());

describe("streamSSE consumes captured Novel endpoint wire", () => {
  for (const newline of ["LF", "CRLF"]) {
    for (const chunkSize of [1, 17, 65536]) {
      for (const scenario of ["success", "premature_eof", "rate_limited", "blocked", "budget_error", "other_provider_error"] as const) {
        it(`${scenario}, ${newline}, ${chunkSize}-byte chunks`, async () => {
          const text = newline === "LF" ? wire[scenario].replace(/\r\n/g, "\n") : wire[scenario];
          const bytes = new TextEncoder().encode(text);
          // One-byte chunks split emoji UTF-8, JSON, event names and CRLF pairs.
          const body = new ReadableStream<Uint8Array>({
            start(controller) {
              for (let i = 0; i < bytes.length; i += chunkSize) {
                controller.enqueue(bytes.slice(i, i + chunkSize));
              }
              controller.close();
            },
          });
          vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body, {
            headers: { "Content-Type": "text/event-stream" },
          })));
          const onToken = vi.fn();
          const onDone = vi.fn();
          const onError = vi.fn();
          const prose = await streamSSE("/works/chapters/mock/continue", {}, {
            onToken, onDone, onError,
          }, { accessToken: "test-access-token" });
          const expectedProse = {
            success: "새 문장이 이어졌다. 😊", premature_eof: "앞부분",
            rate_limited: "앞부분", blocked: "", budget_error: "", other_provider_error: "이어쓰기",
          }[scenario];
          expect(prose).toBe(expectedProse);
          expect(onToken).toHaveBeenCalledTimes(
            scenario === "success" || scenario === "other_provider_error" ? 2 : expectedProse ? 1 : 0,
          );
          expect(onDone).toHaveBeenCalledTimes(scenario === "success" ? 1 : 0);
          expect(onError).toHaveBeenCalledTimes(scenario === "success" ? 0 : 1);
          if (scenario !== "success") {
            expect(onError.mock.calls[0][0].code).toBe(
              scenario === "rate_limited" ? "PROVIDER_RATE_LIMIT" : scenario === "budget_error" ? "VALIDATION_ERROR" : "PROVIDER_ERROR",
            );
          }
        });
      }
    }
  }
});

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
