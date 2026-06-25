import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { ChatMeta } from "@/lib/chatsApi";

interface RowProps {
  c: ChatMeta;
  currentId: string | null;
  onSelect: (id: string) => void;
  onTogglePin: (chat: ChatMeta) => void;
  onDelete: (chat: ChatMeta) => void;
}

function Row({ c, currentId, onSelect, onTogglePin, onDelete }: RowProps) {
  return (
    <div
      className={
        "group flex cursor-pointer items-start gap-2 rounded-lg px-2 py-2 text-sm hover:bg-accent " +
        (c.id === currentId ? "bg-accent" : "")
      }
      onClick={() => onSelect(c.id)}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1">
          {c.pinned && <span>📌</span>}
          <span className="truncate font-medium">{c.title || "Без названия"}</span>
        </div>
        {c.preview && (
          <div className="truncate text-xs text-muted-foreground">{c.preview}</div>
        )}
        {c.tags.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-1">
            {c.tags.map((t) => (
              <span
                key={t}
                className="rounded bg-secondary px-1.5 py-0.5 text-[10px] text-secondary-foreground"
              >
                #{t}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="flex shrink-0 gap-1 opacity-0 group-hover:opacity-100">
        <button
          title={c.pinned ? "Открепить" : "Закрепить"}
          onClick={(e) => {
            e.stopPropagation();
            onTogglePin(c);
          }}
        >
          📌
        </button>
        <button
          title="Удалить"
          onClick={(e) => {
            e.stopPropagation();
            onDelete(c);
          }}
        >
          🗑
        </button>
      </div>
    </div>
  );
}

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  pageChats: ChatMeta[];
  allChats: ChatMeta[];
  currentId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onTogglePin: (chat: ChatMeta) => void;
  onDelete: (chat: ChatMeta) => void;
}

export function Sidebar({
  open,
  onClose,
  pageChats,
  allChats,
  currentId,
  onSelect,
  onNew,
  onTogglePin,
  onDelete,
}: SidebarProps) {
  const [tagFilter, setTagFilter] = useState<string | null>(null);

  const allTags = Array.from(new Set(allChats.flatMap((c) => c.tags))).sort();
  const applyFilter = (list: ChatMeta[]) =>
    tagFilter ? list.filter((c) => c.tags.includes(tagFilter)) : list;

  return (
    <>
      {open && (
        <div className="absolute inset-0 z-10 bg-black/40" onClick={onClose} />
      )}
      <aside
        className={
          "absolute left-0 top-0 z-20 flex h-full w-72 flex-col border-r bg-background transition-transform " +
          (open ? "translate-x-0" : "-translate-x-full")
        }
      >
        <div className="flex items-center justify-between border-b px-3 py-2">
          <span className="text-sm font-semibold">Чаты</span>
          <Button variant="ghost" size="sm" onClick={onClose}>
            ✕
          </Button>
        </div>
        <div className="px-3 py-2">
          <Button className="w-full" size="sm" onClick={onNew}>
            ＋ Новый чат
          </Button>
        </div>
        {allTags.length > 0 && (
          <div className="flex flex-wrap gap-1 px-3 pb-2">
            {allTags.map((t) => (
              <button
                key={t}
                onClick={() => setTagFilter((f) => (f === t ? null : t))}
                className={
                  "rounded px-1.5 py-0.5 text-[10px] " +
                  (tagFilter === t
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-secondary-foreground")
                }
              >
                #{t}
              </button>
            ))}
          </div>
        )}
        <ScrollArea className="flex-1">
          <div className="px-2 pb-4">
            <div className="px-2 pt-2 text-xs font-semibold text-muted-foreground">
              Эта страница
            </div>
            {applyFilter(pageChats).length === 0 && (
              <div className="px-2 py-1 text-xs text-muted-foreground">Нет чатов</div>
            )}
            {applyFilter(pageChats).map((c) => (
              <Row key={c.id} c={c} currentId={currentId} onSelect={onSelect} onTogglePin={onTogglePin} onDelete={onDelete} />
            ))}
            <div className="px-2 pt-3 text-xs font-semibold text-muted-foreground">
              Все чаты
            </div>
            {applyFilter(allChats).map((c) => (
              <Row key={c.id} c={c} currentId={currentId} onSelect={onSelect} onTogglePin={onTogglePin} onDelete={onDelete} />
            ))}
          </div>
        </ScrollArea>
      </aside>
    </>
  );
}
