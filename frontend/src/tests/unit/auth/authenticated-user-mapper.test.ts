import { describe, expect, it } from "vitest";

import { toAuthenticatedUser } from "@/features/auth/mappers/authenticated-user";

describe("toAuthenticatedUser", () => {
  /**
   * GIVEN a backend user payload carrying a snake_case full name
   * WHEN the payload is normalized for the product
   * THEN the identifier and e-mail are preserved and the name is camelCased
   */
  it("renames the snake_case name to the frontend casing", () => {
    expect(
      toAuthenticatedUser({
        id: 1,
        email: "ada@example.com",
        full_name: "Ada Lovelace",
      }),
    ).toEqual({ id: 1, email: "ada@example.com", fullName: "Ada Lovelace" });
  });

  /**
   * GIVEN a backend user payload whose full name is an empty string
   * WHEN the payload is normalized for the product
   * THEN the empty name is carried through instead of being replaced
   */
  it("keeps an empty full name empty rather than inventing a placeholder", () => {
    expect(
      toAuthenticatedUser({ id: 7, email: "ada@example.com", full_name: "" }),
    ).toEqual({ id: 7, email: "ada@example.com", fullName: "" });
  });
});
