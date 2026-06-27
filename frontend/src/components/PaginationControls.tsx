import type { PaginatedResponse } from "@/types/api";

interface PaginationControlsProps {
  page: PaginatedResponse<unknown>;
  currentPage: number;
  onPageChange: (page: number) => void;
  pageSize?: number;
  onPageSizeChange?: (size: number) => void;
  pageSizeOptions?: number[];
}

function parsePageFromUrl(url: string | null): number | null {
  if (!url) return null;
  try {
    const page = new URL(url, window.location.origin).searchParams.get("page");
    return page ? Number(page) : null;
  } catch {
    return null;
  }
}

export function PaginationControls({
  page,
  currentPage,
  onPageChange,
  pageSize,
  onPageSizeChange,
  pageSizeOptions = [25, 50, 100],
}: PaginationControlsProps) {
  const totalPages = pageSize ? Math.max(1, Math.ceil(page.count / pageSize)) : 1;
  const prevPage = parsePageFromUrl(page.previous) ?? currentPage - 1;
  const nextPage = parsePageFromUrl(page.next) ?? currentPage + 1;
  const showingFrom = page.count === 0 ? 0 : (currentPage - 1) * (pageSize ?? 50) + 1;
  const showingTo = Math.min(currentPage * (pageSize ?? 50), page.count);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-4 py-3">
      <p className="text-xs text-slate-500">
        Showing {showingFrom}–{showingTo} of {page.count}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        {onPageSizeChange && pageSize !== undefined && (
          <label className="flex items-center gap-1.5 text-xs text-slate-600">
            Per page
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              className="rounded border border-slate-300 px-2 py-1 text-xs"
            >
              {pageSizeOptions.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
        )}
        <button
          type="button"
          disabled={!page.previous}
          onClick={() => onPageChange(prevPage)}
          className="rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
        >
          Previous
        </button>
        <span className="text-xs text-slate-600">
          Page {currentPage} of {totalPages}
        </span>
        <button
          type="button"
          disabled={!page.next}
          onClick={() => onPageChange(nextPage)}
          className="rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
        >
          Next
        </button>
      </div>
    </div>
  );
}
