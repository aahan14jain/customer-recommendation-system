type PlaceholderCardProps = {
  title: string;
  description?: string;
  children?: React.ReactNode;
};

/**
 * Simple bordered card for dashboard sections. Replace contents when wiring real data.
 */
export function PlaceholderCard({
  title,
  description,
  children,
}: PlaceholderCardProps) {
  return (
    <section className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
        {title}
      </h2>
      {description ? (
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          {description}
        </p>
      ) : null}
      <div className="mt-4 text-sm text-zinc-600 dark:text-zinc-300">
        {children ?? (
          <p className="rounded-md bg-zinc-50 py-8 text-center text-zinc-400 dark:bg-zinc-900 dark:text-zinc-500">
            Coming soon
          </p>
        )}
      </div>
    </section>
  );
}
