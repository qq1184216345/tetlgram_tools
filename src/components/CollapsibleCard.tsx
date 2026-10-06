import { ReactNode, useState } from "react";

interface CollapsibleCardProps {
  title: string;
  defaultOpen?: boolean;
  danger?: boolean;
  children: ReactNode;
}

export function CollapsibleCard({
  title,
  defaultOpen = false,
  danger = false,
  children,
}: CollapsibleCardProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={`card collapsible-card${danger ? " danger-card" : ""}${open ? " open" : ""}`}>
      <button type="button" className="collapse-toggle" onClick={() => setOpen((value) => !value)}>
        <h3>{title}</h3>
        <span className="collapse-hint">{open ? "收起" : "展开"}</span>
      </button>
      {open ? <div className="collapse-body">{children}</div> : null}
    </div>
  );
}
