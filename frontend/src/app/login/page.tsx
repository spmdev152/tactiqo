import { redirect } from "next/navigation";

import { ModeToggle } from "@/components/mode-toggle";
import { LoginForm } from "@/features/auth/components/login-form";
import { getCurrentUser } from "@/features/auth/server/get-current-user";

/**
 * Renders the sign-in page and turns an already-authenticated visitor away.
 *
 * @remarks
 * The middleware redirects on cookie presence alone, so a stale cookie still
 * lands here; confirming the session against the backend is what makes the
 * redirect trustworthy. The mode toggle is part of this page because the theme
 * has to be reachable before anyone has an account session.
 *
 * @returns The sign-in page tree.
 */
export default async function LoginPage() {
  const user = await getCurrentUser();

  if (user !== null) {
    redirect("/");
  }

  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-8 px-6 py-16">
      <LoginForm />

      <ModeToggle />
    </main>
  );
}
