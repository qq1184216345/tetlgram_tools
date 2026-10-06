interface PlaceholderPageProps {
  title: string;
  features: string[];
}

export function PlaceholderPage({ title, features }: PlaceholderPageProps) {
  return (
    <div className="placeholder-page">
      <div className="placeholder-card">
        <h3>{title}</h3>
        <p>该模块将在后续版本中实现，计划功能如下：</p>
        <ul>
          {features.map((feature) => (
            <li key={feature}>{feature}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
