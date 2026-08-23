"use client";

import { useActionState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { signInAction } from "@/features/auth/server/actions";
import type {
  SignInFormError,
  SignInFormState,
} from "@/features/auth/types/sign-in-form-state";

const INITIAL_STATE: SignInFormState = { email: "", error: null };

const ERROR_MESSAGES = {
  "missing-credentials": "Enter your e-mail address and your password.",
  "backend-not-configured":
    "Sign-in is unavailable because this deployment has no API configured.",
  "api-unreachable": "The API could not be reached. Try again in a moment.",
  "invalid-credentials": "Invalid e-mail or password.",
  "unexpected-status": "The API refused the sign-in request unexpectedly.",
  "undecodable-body":
    "The API answered the sign-in request with an unreadable response.",
  "contract-mismatch":
    "The API returned a payload that does not match the sign-in contract.",
} as const satisfies Record<SignInFormError, string>;

/**
 * Collects e-mail and password credentials and signs the visitor in.
 *
 * @remarks
 * A Client Component only because `useActionState` needs the pending flag and
 * the returned state; the credentials themselves are handled by the Server
 * Action and never appear in client state. The error region is rendered only
 * when there is something to say, so assistive technology announces it as it
 * appears instead of announcing an empty container on every keystroke.
 *
 * React resets an uncontrolled form once its action settles, which would wipe
 * the address a visitor just typed. Seeding `defaultValue` from the returned
 * state restores it, and the password is deliberately not restored.
 */
export function LoginForm() {
  const [state, formAction, isPending] = useActionState(
    signInAction,
    INITIAL_STATE,
  );

  return (
    <Card className="w-full max-w-sm">
      <CardHeader>
        <CardTitle>Sign in</CardTitle>
        <CardDescription>Access your Tactiqo workspace.</CardDescription>
      </CardHeader>

      <CardContent>
        <form action={formAction} className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <Label htmlFor="email">E-mail</Label>

            <Input
              autoComplete="email"
              defaultValue={state.email}
              id="email"
              name="email"
              placeholder="you@example.com"
              required
              type="email"
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="password">Password</Label>

            <Input
              autoComplete="current-password"
              id="password"
              name="password"
              required
              type="password"
            />
          </div>

          {state.error !== null && (
            <p className="text-sm text-destructive" role="alert">
              {ERROR_MESSAGES[state.error]}
            </p>
          )}

          <Button className="w-full" disabled={isPending} type="submit">
            {isPending ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
