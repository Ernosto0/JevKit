interface Props {
  label: string;
  value: string;
  note?: string;
}

export function Stat({ label, value, note }: Props) {
  return (
    <div className="card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {note && <div className="stat-note">{note}</div>}
    </div>
  );
}
