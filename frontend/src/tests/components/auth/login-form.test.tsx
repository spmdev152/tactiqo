import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { randomUUID } from "node:crypto";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LoginForm } from "@/features/auth/components/login-form";
import type { SignInActionResult } from "@/features/auth/types/sign-in-action-result";

const { signInAction } = vi.hoisted(() => ({ signInAction: vi.fn() }));

vi.mock("@/features/auth/server/actions", () => ({ signInAction }));

/**
 * Fills the credential fields and submits the sign-in form.
 *
 * @param email - E-mail address to type into the form.
 * @param password - Password to type into the form, generated when omitted.
 */
function submitCredentials(email: string, password = randomUUID()): void {
  fireEvent.change(screen.getByLabelText("E-mail"), {
    target: { value: email },
  });

  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: password },
  });

  fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
}

describe("LoginForm", () => {
  beforeEach(() => {
    signInAction.mockReset();
    signInAction.mockResolvedValue({ error: "invalid-credentials" });
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
   * GIVEN an empty sign-in form
   * WHEN it is submitted
   * THEN both fields report their own error and no request is attempted
   */
  it("rejects empty credentials before calling the action", async () => {
    render(<LoginForm />);

    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText("Enter your e-mail address.")).toBeVisible();
    expect(screen.getByText("Enter your password.")).toBeVisible();
    expect(signInAction).not.toHaveBeenCalled();
  });

  /**
   * GIVEN a password and an address that is not a valid e-mail
   * WHEN the form is submitted
   * THEN the address is reported as invalid and no request is attempted
   */
  it("rejects a malformed address before calling the action", async () => {
    render(<LoginForm />);
    submitCredentials("ada@");

    expect(
      await screen.findByText("Enter a valid e-mail address."),
    ).toBeVisible();

    expect(signInAction).not.toHaveBeenCalled();
  });

  /**
   * GIVEN an address typed with surrounding whitespace
   * WHEN the form is submitted
   * THEN the action receives the trimmed address
   */
  it("trims the address before submitting it", async () => {
    const password = randomUUID();

    render(<LoginForm />);
    submitCredentials("  ada@example.com  ", password);

    await waitFor(() =>
      expect(signInAction).toHaveBeenCalledWith({
        email: "ada@example.com",
        password,
      }),
    );
  });

  /**
   * GIVEN a sign-in attempt the backend rejects as invalid credentials
   * WHEN the credentials are submitted
   * THEN the rejection is announced through an alert region
   */
  it("announces an invalid-credentials rejection", async () => {
    render(<LoginForm />);
    submitCredentials("ada@example.com");

    await expect(screen.findByRole("alert")).resolves.toHaveTextContent(
      "Invalid e-mail or password.",
    );
  });

  /**
   * GIVEN a sign-in attempt the backend throttled
   * WHEN the credentials are submitted
   * THEN the visitor is told to wait rather than to retype a password
   */
  it("announces a throttled attempt as its own failure", async () => {
    signInAction.mockResolvedValue({ error: "rate-limited" });

    render(<LoginForm />);
    submitCredentials("ada@example.com");

    await expect(screen.findByRole("alert")).resolves.toHaveTextContent(
      "Too many sign-in attempts. Wait a moment before trying again.",
    );
  });

  /**
   * GIVEN a failed sign-in attempt
   * WHEN the form has settled after the failure
   * THEN the typed e-mail is still in the field, because the form owns its state
   */
  it("keeps the typed e-mail after a failed attempt", async () => {
    render(<LoginForm />);
    submitCredentials("ada@example.com");

    await screen.findByRole("alert");

    expect(screen.getByLabelText("E-mail")).toHaveValue("ada@example.com");
  });

  /**
   * GIVEN a sign-in attempt still in flight
   * WHEN the submit button is inspected
   * THEN it keeps its label, reports itself busy, and shows a spinner
   */
  it("swaps only the arrow for a spinner while submitting", async () => {
    const { promise, resolve } = Promise.withResolvers<SignInActionResult>();

    signInAction.mockReturnValue(promise);

    const { container } = render(<LoginForm />);

    submitCredentials("ada@example.com");

    const submit = await screen.findByRole("button", { name: "Sign in" });

    await waitFor(() => expect(submit).toBeDisabled());

    expect(submit).toHaveAttribute("aria-busy", "true");
    expect(container.querySelector("[data-slot=spinner]")).toBeVisible();

    resolve({ error: "invalid-credentials" });

    await screen.findByRole("alert");

    expect(screen.getByRole("button", { name: "Sign in" })).not.toBeDisabled();
    expect(container.querySelector("[data-slot=spinner]")).toBeNull();
  });
});
