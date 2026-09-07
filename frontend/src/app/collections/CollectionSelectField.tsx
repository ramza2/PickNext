import { useState } from "react";
import type { ApiCollection } from "../../types/api";
import { CollectionPickerModal } from "./CollectionPickerModal";

export function CollectionSelectField({
  selected,
  disabled,
  onChange,
  showToast,
  label = "Collection",
}: {
  selected: { id: string; name: string } | null;
  disabled?: boolean;
  onChange: (collection: ApiCollection | null) => void;
  showToast: (message: string) => void;
  label?: string;
}) {
  const [pickerOpen, setPickerOpen] = useState(false);

  return (
    <div>
      <div className="block text-sm font-medium text-foreground mb-1.5">
        {label}{" "}
        <span className="text-muted-foreground font-normal text-xs">(선택)</span>
      </div>
      {selected ? (
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex-1 min-w-0 px-3 py-2.5 border border-border rounded-xl text-sm bg-muted/40 text-foreground truncate">
            {selected.name}
          </div>
          <button
            type="button"
            disabled={disabled}
            onClick={() => setPickerOpen(true)}
            className="text-xs border border-border px-3 py-2 rounded-xl hover:bg-muted disabled:opacity-50"
          >
            변경
          </button>
          <button
            type="button"
            disabled={disabled}
            onClick={() => onChange(null)}
            className="text-xs border border-border px-3 py-2 rounded-xl hover:bg-muted disabled:opacity-50"
          >
            제거
          </button>
        </div>
      ) : (
        <button
          type="button"
          disabled={disabled}
          onClick={() => setPickerOpen(true)}
          className="w-full text-left px-3 py-2.5 border border-border rounded-xl text-sm text-muted-foreground hover:bg-muted disabled:opacity-50"
        >
          Collection 선택
        </button>
      )}

      <CollectionPickerModal
        mode="select"
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        showToast={showToast}
        currentCollection={selected}
        allowClear
        onSelect={(collection) => {
          onChange(collection);
        }}
      />
    </div>
  );
}
