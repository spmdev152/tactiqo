import "server-only";

import { headers } from "next/headers";

const FORWARDED_FOR_HEADER = "x-forwarded-for";

/**
 * Builds the headers that tell the backend which visitor a call is made for.
 *
 * @remarks
 * The browser never contacts the backend API, so every request the API sees
 * arrives from this server and its peer address identifies this server rather
 * than a visitor. Forwarding the chain is what lets the backend key its
 * sign-in throttle per visitor instead of collapsing every visitor into one
 * bucket.
 *
 * The chain is forwarded verbatim, and deciding which of its entries names the
 * visitor is deliberately left to the backend: that is the side which knows
 * which addresses belong to this project's own infrastructure, and it refuses
 * the header outright from a peer it does not trust. Next.js fills the header
 * in from the connecting socket when no proxy set one, so a chain is available
 * even with nothing deployed in front of this server.
 *
 * @returns The forwarding header to merge into a backend call, or no header at
 * all when the current request carries no chain.
 */
export async function forwardingHeaders(): Promise<Record<string, string>> {
  const requestHeaders = await headers();

  const forwardingChain = requestHeaders.get(FORWARDED_FOR_HEADER);

  return forwardingChain === null
    ? {}
    : { [FORWARDED_FOR_HEADER]: forwardingChain };
}
