import type { ReactNode } from "react";

interface SectionCardProps {
  title?: string;
  description?: string;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}

export function SectionCard({ title, description, action, className = "", children }: SectionCardProps) {
  return (
    <section className={`section-card ${className}`}>
      {title || description || action ? (
        <div className="section-card__header">
          <div>
            {title ? <h2>{title}</h2> : null}
            {description ? <p>{description}</p> : null}
          </div>
          {action ? <div className="section-card__action">{action}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}
