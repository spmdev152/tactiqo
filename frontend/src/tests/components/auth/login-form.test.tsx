import { fireEvent, render, screen } from "@testing-library/react";
import { randomUUID } from "node:crypto";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LoginForm } from "@/features/auth/components/login-form";
import type { SignInFormState } from "@/features/auth/types/sign-in-form-state";

const { signInAction } = vi.hoisted(() => ({ signInAction: vi.fn() }));

vi.mock("@/features/auth/server/actions", () => ({ signInAction }));

/**
 * Fills the credential fields and submits the sign-in form.
 *
 * @param email - E-mail address to type into the form.
 */
function submitCredentials(email: string): void {
  fireEvent.change(screen.getByLabelText("E-mail"), {
    target: { value: email },
  });

  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: randomUUID() },
  });

  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

describe("LoginForm", () => {
  beforeEach(() => {
    signInAction.mockReset();
  });

  /**
   * GIVEN a visitor opening the sign-in form
   * WHEN the form is rendered
   * THEN both credential fields are labelled and carry their autocomplete hints
   */
  it("renders labelled credential fields", () => {
    render(<LoginForm />);

    const email = screen.getByLabelText("E-mail");
    const password = screen.getByLabelText("Password");

    expect(email).toHaveAttribute("autocomplete", "email");
    expect(email).toHaveAttribute("type", "email");
    expect(password).toHaveAttribute("autocomplete", "current-password");
    expect(password).toHaveAttribute("type", "password");
  });

  /**
   * GIVEN a sign-in attempt the backend rejects as invalid credentials
   * WHEN the credentials are submitted
   * THEN the rejection is announced through an alert region
   */
  it("announces an invalid-credentials rejection", async () => {
    const rejected: SignInFormState = {
      email: "ada@example.com",
      error: "invalid-credentials",
    };

    signInAction.mockResolvedValue(rejected);

    render(<LoginForm />);
    submitCredentials("ada@example.com");

    await expect(screen.findByRole("alert")).resolves.toHaveTextContent(
      "Invalid e-mail or password.",
    );
  });

  /**
   * GIVEN a failed sign-in attempt whose e-mail the action echoed back
   * WHEN the form has settled after the failure
   * THEN the typed e-mail is still in the field and the password is cleared
   */
  it("keeps the typed e-mail after a failed attempt", async () => {
    const rejected: SignInFormState = {
      email: "ada@example.com",
      error: "invalid-credentials",
    };

    signInAction.mockResolvedValue(rejected);

    render(<LoginForm />);
    submitCredentials("ada@example.com");

    await screen.findByRole("alert");

    expect(screen.getByLabelText("E-mail")).toHaveValue("ada@example.com");
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });
});
