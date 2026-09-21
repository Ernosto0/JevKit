interface Props {
  status: string;
}

/** Renders an execution or validation status with its own colour. */
export function StatusPill({ status }: Props) {
  return <span className={`pill ${status}`}>{status.replace(/_/g, ' ')}</span>;
}
