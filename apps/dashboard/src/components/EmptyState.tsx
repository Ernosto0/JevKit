interface Props {
  title: string;
  hint?: string;
}

/**
 * Shown when there is genuinely nothing stored yet.
 *
 * The console never fills an empty view with sample numbers: a reader must be
 * able to trust that every figure on screen was measured (PLAN.md section 16).
 */
export function EmptyState({ title, hint }: Props) {
  return (
    <div className="empty">
      <div>{title}</div>
      {hint && <div style={{ marginTop: 6, fontSize: 12 }}>{hint}</div>}
    </div>
  );
}
