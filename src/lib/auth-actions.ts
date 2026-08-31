"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE } from "@/lib/auth";

/**
 * Clears the session and returns to the login page.
 *
 * Exposed as a server action (POST) rather than a plain /logout link on
 * purpose: Next prefetches links, and a GET logout would sign people out just
 * for hovering the control.
 */
export async function signOut() {
  const store = await cookies();
  store.delete(SESSION_COOKIE);
  redirect("/login");
}
