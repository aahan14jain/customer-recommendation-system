import { NavLink } from "@/components/NavLink";
import { ROUTES } from "@/lib/routes";

export default function HomePage() {
  return (
    <div className="flex min-h-full flex-col">
      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center px-6 py-20">
        <p className="text-sm font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          Welcome
        </p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          Customer Recommendation System
        </h1>
        <p className="mt-4 text-lg leading-relaxed text-zinc-600 dark:text-zinc-400">
          Personalized vendor recommendations based on transaction behavior
        </p>
        <div className="mt-10 flex flex-wrap gap-3">
          <NavLink href={ROUTES.login} variant="primary">
            Login
          </NavLink>
          <NavLink href={ROUTES.dashboard}>Dashboard</NavLink>
        </div>
        <p className="mt-12 text-sm text-zinc-400 dark:text-zinc-500">
          API integration will be added in a later step.
        </p>
      </main>
    </div>
  );
}
