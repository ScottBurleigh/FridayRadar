import type { Metadata } from "next";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Lock } from "lucide-react";
import {
  SESSION_COOKIE,
  SESSION_TTL_MS,
  createSessionToken,
  credentialsValid,
  safeNextPath,
} from "@/lib/auth";

export const metadata: Metadata = {
  title: "Sign in",
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; error?: string }>;
}) {
  const params = await searchParams;
  const next = safeNextPath(params.next);
  const failed = params.error === "1";

  async function signIn(formData: FormData) {
    "use server";
    const user = String(formData.get("username") ?? "");
    const password = String(formData.get("password") ?? "");
    const target = safeNextPath(String(formData.get("next") ?? "/"));

    if (!credentialsValid(user, password)) {
      // Never echo back what was typed — no username in the retry URL.
      const qs = new URLSearchParams({ error: "1" });
      if (target !== "/") qs.set("next", target);
      redirect(`/login?${qs.toString()}`);
    }

    const store = await cookies();
    store.set(SESSION_COOKIE, await createSessionToken(user), {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: Math.floor(SESSION_TTL_MS / 1000),
    });
    redirect(target);
  }

  return (
    <main className="flex flex-1 items-center justify-center px-4 py-16">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center text-center">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/fridayradar-mark.svg" alt="" width={64} height={64} className="size-16" />
          <h1 className="mt-4 font-heading text-2xl font-semibold tracking-tight text-zinc-50">
            FridayRadar
          </h1>
          <p className="mt-1.5 text-sm text-zinc-400">
            This site is private. Sign in to continue.
          </p>
        </div>

        <form
          action={signIn}
          className="mt-7 flex flex-col gap-4 rounded-xl border border-amber-400/30 bg-[#17233d] p-5"
        >
          <input type="hidden" name="next" value={next} />

          {failed ? (
            <p
              role="alert"
              className="rounded-lg border border-rose-400/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-200"
            >
              That username and password combination didn&apos;t work. Try again.
            </p>
          ) : null}

          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="username"
              className="text-xs font-medium uppercase tracking-wide text-zinc-300"
            >
              Username
            </label>
            <input
              id="username"
              name="username"
              type="text"
              autoComplete="username"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              required
              autoFocus
              className="h-10 w-full rounded-lg border border-amber-200/45 bg-[#0f1a2e] px-3 text-sm text-zinc-50 outline-none placeholder:text-zinc-500 focus-visible:border-amber-300 focus-visible:ring-2 focus-visible:ring-amber-400/40"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="password"
              className="text-xs font-medium uppercase tracking-wide text-zinc-300"
            >
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              className="h-10 w-full rounded-lg border border-amber-200/45 bg-[#0f1a2e] px-3 text-sm text-zinc-50 outline-none placeholder:text-zinc-500 focus-visible:border-amber-300 focus-visible:ring-2 focus-visible:ring-amber-400/40"
            />
          </div>

          <button
            type="submit"
            className="mt-1 inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-amber-400 px-4 text-sm font-semibold text-zinc-950 transition-colors hover:bg-amber-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300"
          >
            <Lock className="size-4" aria-hidden />
            Sign in
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-zinc-500">
          2027+ high school football recruiting talent
        </p>
      </div>
    </main>
  );
}
