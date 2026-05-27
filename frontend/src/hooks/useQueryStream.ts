// TODO: SSE/streaming hook that posts to /v1/query and yields incremental tokens.
export function useQueryStream() {
  return { stream: async (_q: string) => undefined };
}
