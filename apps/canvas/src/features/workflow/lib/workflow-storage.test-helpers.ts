import { beforeEach, vi } from "vitest";

const mockFetch = vi.fn<Parameters<typeof fetch>, ReturnType<typeof fetch>>();

export const jsonResponse = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });

export const queueResponses = (responses: Response[]) => {
  const queue = [...responses];
  mockFetch.mockImplementation(() => {
    const next = queue.shift();
    if (!next) {
      throw new Error("No more mocked responses available");
    }
    return Promise.resolve(next);
  });
};

export const getFetchMock = () => mockFetch;

export const setupFetchMock = () => {
  beforeEach(() => {
    mockFetch.mockReset();
    globalThis.fetch = mockFetch as unknown as typeof fetch;
  });
};
