import { ReactNode } from "react";

interface StickyActionsProps {
  summary?: ReactNode;
  children: ReactNode;
}

export function StickyActions({ summary, children }: StickyActionsProps) {
  return (
    <div className="sticky-action-bar">
      {summary ? <div className="sticky-action-summary">{summary}</div> : null}
      <div className="button-row sticky-action-buttons">{children}</div>
    </div>
  );
}
