import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex w-full max-w-lg flex-1 flex-col items-center justify-center px-4 py-24 text-center">
      <p className="text-sm uppercase tracking-widest text-amber-400/80">404</p>
      <h1 className="mt-2 text-2xl font-semibold text-zinc-50">School not on the board</h1>
      <p className="mt-2 text-sm text-zinc-500">
        That program is not in the current 2027+ dataset.
      </p>
      <Link href="/" className="mt-6 text-amber-300 hover:underline">
        Back to rankings
      </Link>
    </main>
  );
}
