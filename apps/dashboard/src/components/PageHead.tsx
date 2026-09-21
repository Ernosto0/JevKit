interface Props {
  title: string;
  description?: string;
}

export function PageHead({ title, description }: Props) {
  return (
    <header className="page-head">
      <h1>{title}</h1>
      {description && <p>{description}</p>}
    </header>
  );
}
