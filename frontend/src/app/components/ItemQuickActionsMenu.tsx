import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  Check,
  Edit2,
  MoreVertical,
  RefreshCw,
  Trash2,
} from "lucide-react";
import type { ItemsListViewModel } from "../mappers/items";

export function ItemQuickActionsMenu({
  item,
  disabled = false,
  onEdit,
  onToggleStatus,
  onDelete,
}: {
  item: ItemsListViewModel;
  disabled?: boolean;
  onEdit: (item: ItemsListViewModel) => void;
  onToggleStatus: (item: ItemsListViewModel) => void;
  onDelete: (item: ItemsListViewModel) => void;
}) {
  const statusLabel =
    item.status === "PLANNED" ? "완료 처리" : "볼 예정으로 변경";
  const StatusIcon = item.status === "PLANNED" ? Check : RefreshCw;

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          disabled={disabled}
          aria-label={`${item.title} 빠른 작업`}
          className="p-1.5 -m-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          onClick={(event) => event.stopPropagation()}
        >
          <MoreVertical size={14} />
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={6}
          collisionPadding={8}
          className="z-[80] min-w-44 rounded-xl border border-border bg-card p-1.5 shadow-xl"
          onClick={(event) => event.stopPropagation()}
        >
          <DropdownMenu.Item
            className="flex cursor-pointer select-none items-center gap-2 rounded-lg px-3 py-2 text-sm text-foreground outline-none hover:bg-muted focus:bg-muted"
            onSelect={() => onEdit(item)}
          >
            <Edit2 size={14} />
            수정
          </DropdownMenu.Item>

          <DropdownMenu.Item
            className="flex cursor-pointer select-none items-center gap-2 rounded-lg px-3 py-2 text-sm text-foreground outline-none hover:bg-muted focus:bg-muted"
            onSelect={() => onToggleStatus(item)}
          >
            <StatusIcon size={14} />
            {statusLabel}
          </DropdownMenu.Item>

          <DropdownMenu.Separator className="my-1 h-px bg-border" />

          <DropdownMenu.Item
            className="flex cursor-pointer select-none items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-600 outline-none hover:bg-red-50 focus:bg-red-50"
            onSelect={() => onDelete(item)}
          >
            <Trash2 size={14} />
            삭제
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
