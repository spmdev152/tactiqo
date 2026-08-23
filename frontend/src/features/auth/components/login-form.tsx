"use client";

import { useState } from "react";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight } from "lucide-react";
import { Controller, useForm } from "react-hook-form";

import { ButtonSpinner } from "@/components/button-spinner";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import type { Credentials } from "@/features/auth/schemas/credentials";
import { credentialsSchema } from "@/features/auth/schemas/credentials";
import { signInAction } from "@/features/auth/server/actions";
import type { SignInActionError } from "@/features/auth/types/sign-in-action-result";

const EMPTY_CREDENTIALS: Credentials = { email: "", password: "" };

const ERROR_MESSAGES = {
  "malformed-request": "Check the credentials you submitted and try again.",
  "backend-not-configured":
    "Sign-in is unavailable because this deployment has no API configured.",
  "api-unreachable": "The API could not be reached. Try again in a moment.",
  "invalid-credentials": "Invalid e-mail or password.",
  "unexpected-status": "The API refused the sign-in request unexpectedly.",
  "undecodable-body":
    "The API answered the sign-in request with an unreadable response.",
  "contract-mismatch":
    "The API returned a payload that does not match the sign-in contract.",
} as const satisfies Record<SignInActionError, string>;

/**
 * Collects e-mail and password credentials and signs the visitor in.
 *
 * @remarks
 * React Hook Form owns the field state and validates against
 * {@link credentialsSchema} through `zodResolver`, which is the integration
 * shadcn/ui documents for its `Field` primitives. Holding the values in the
 * form means a rejected attempt keeps whatever was typed without the component
 * having to echo it back through the action.
 *
 * The credentials still only ever exist in client memory: the Server Action
 * receives them, and no request from this component reaches the backend
 * directly. A successful attempt never settles here, because the action
 * redirects, so the only outcome this component renders is a failure.
 *
 * While the attempt is in flight the submit button keeps its label and swaps
 * only its trailing icon for a spinner. Rewording the button moves it, which
 * shifts the pointer target out from under a visitor who is already mid-click,
 * and the label is the one part of a control that should never change while the
 * control is busy.
 *
 * The spinner comes from {@link ButtonSpinner}, which documents why it must not
 * contribute to the button's accessible name; `aria-busy` reports the state.
 */
export function LoginForm() {
  const [submissionError, setSubmissionError] =
    useState<SignInActionError | null>(null);

  const form = useForm<Credentials>({
    resolver: zodResolver(credentialsSchema),
    defaultValues: EMPTY_CREDENTIALS,
  });

  async function submitCredentials(credentials: Credentials) {
    setSubmissionError(null);

    const result = await signInAction(credentials);

    setSubmissionError(result.error);
  }

  return (
    <form
      className="flex flex-col gap-7"
      noValidate
      onSubmit={form.handleSubmit(submitCredentials)}
    >
      <FieldGroup className="gap-5">
        <Controller
          control={form.control}
          name="email"
          render={({ field, fieldState }) => (
            <Field data-invalid={fieldState.invalid}>
              <FieldLabel
                className="font-mono text-xs tracking-wider uppercase"
                htmlFor="sign-in-email"
              >
                E-mail
              </FieldLabel>

              <Input
                {...field}
                aria-invalid={fieldState.invalid}
                autoComplete="email"
                className="h-11"
                id="sign-in-email"
                placeholder="you@example.com"
                type="email"
              />

              <FieldError errors={[fieldState.error]} />
            </Field>
          )}
        />

        <Controller
          control={form.control}
          name="password"
          render={({ field, fieldState }) => (
            <Field data-invalid={fieldState.invalid}>
              <FieldLabel
                className="font-mono text-xs tracking-wider uppercase"
                htmlFor="sign-in-password"
              >
                Password
              </FieldLabel>

              <Input
                {...field}
                aria-invalid={fieldState.invalid}
                autoComplete="current-password"
                className="h-11"
                id="sign-in-password"
                placeholder="*********"
                type="password"
              />

              <FieldError errors={[fieldState.error]} />
            </Field>
          )}
        />
      </FieldGroup>

      {submissionError !== null && (
        <FieldError className="border-l-2 border-destructive pl-3">
          {ERROR_MESSAGES[submissionError]}
        </FieldError>
      )}

      <Button
        aria-busy={form.formState.isSubmitting}
        className="group h-11 w-full text-sm tracking-wide"
        disabled={form.formState.isSubmitting}
        type="submit"
      >
        Sign in
        {form.formState.isSubmitting ? (
          <ButtonSpinner />
        ) : (
          <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
        )}
      </Button>
    </form>
  );
}
