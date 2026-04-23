"use client";

import type { ContextEntity } from "@/lib/sessions";
import { ContextCard } from "./ContextCard";

interface Props {
  entities: ContextEntity[];
  onRemove: (entityId: string) => void;
  onClear: () => void;
  onCollapse: () => void;
}

export function ContextPanel({ entities, onRemove, onClear, onCollapse }: Props) {
  return (
    <aside className="context-panel">
      <header className="context-panel-header">
        <div className="context-panel-title">Context</div>
        <div className="context-panel-actions">
          {entities.length > 0 && (
            <button className="icon-btn" onClick={onClear} title="Clear all">
              {"\u232B"}
            </button>
          )}
          <button className="icon-btn" onClick={onCollapse} title="Hide panel">
            {"\u203A"}
          </button>
        </div>
      </header>
      <div className="context-panel-body">
        {entities.length === 0 ? (
          <div className="context-empty">
            <div className="context-empty-icon">{"\u25C7"}</div>
            <div>Entities mentioned in this chat will appear here automatically.</div>
          </div>
        ) : (
          entities.map((e) => <ContextCard key={e.id} entity={e} onRemove={() => onRemove(e.id)} />)
        )}
      </div>
    </aside>
  );
}
