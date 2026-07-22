import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import type { ReactNode } from "react";
import {
  Home, Search, Shuffle, List, Folder, Clock, Database, Settings,
  Plus, Star, Film, Tv, BookOpen, Utensils, Smile, AlignJustify,
  Grid, X, RefreshCw, Edit2, MoreVertical, ChevronLeft, ChevronRight,
  Menu, User, LogOut, Download, Upload, CheckCircle, Target,
  Layers, AlertTriangle, Package, MoreHorizontal, Trash2, Check,
  GripVertical, Eye, ExternalLink, Lock, ChevronsLeft, ChevronsRight,
  ShieldAlert, FileText, Palette,
} from "lucide-react";
import type { Page } from "./pageTypes";
import type {
  Status,
  RecommendStep,
  Candidate,
  Category,
  Item,
  Collection,
  HistoryEntry,
  TMDBResult,
  ImportStep,
} from "../types/mock";
import {
  CATEGORIES,
  ITEMS,
  COLLECTIONS,
  HISTORY,
  TMDB_RESULTS,
  MOCK_FILE,
} from "../mocks/data";
import AppLayout from "./layout/AppLayout";
import { useHomeReadData } from "./hooks/useHomeReadData";
import {
  useItemsReadData,
  type ItemsPageStateSnapshot,
  type ItemsQuerySnapshot,
  type ItemsViewMode,
} from "./hooks/useItemsReadData";
import {
  useCollectionsReadData,
  type CollectionsQuerySnapshot,
} from "./hooks/useCollectionsReadData";
import { useCollectionDetail } from "./hooks/useCollectionDetail";
import { useCollectionItemsReadData } from "./hooks/useCollectionItemsReadData";
import { useItemDetail } from "./hooks/useItemDetail";
import {
  mapApiCategoryToHomeCategory,
  mapApiItemToHomeRecentItem,
} from "./mappers/home";
import {
  displayItemRating,
  mapApiItemToItemsListViewModel,
} from "./mappers/items";
import {
  mapApiCollectionToDetail,
  mapApiCollectionToListItem,
  type CollectionListItemViewModel,
} from "./mappers/collections";
import {
  displayDetailRating,
  mapApiItemDetailToViewModel,
} from "./mappers/itemDetail";
import { formatDate } from "../utils/date";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const getCat = (id: string) => CATEGORIES.find(c => c.id === id);
const getCol = (id: string) => COLLECTIONS.find(c => c.id === id);

const suggestCategory = (r: TMDBResult): string | null => {
  if (r.type === "MOVIE") return r.country === "JP" ? "animemov" : "movie";
  if (r.country === "KR") return "kdrama";
  if (r.country === "JP") return "jdrama";
  if (["US","GB","IE","AU","CA"].includes(r.country)) return "usdrama";
  if (["CN","TW","HK"].includes(r.country)) return "cndrama";
  return null;
};

// ─── Shared Atoms ─────────────────────────────────────────────────────────────

function StarRating({ rating, sm }: { rating?: number; sm?: boolean }) {
  if (rating === undefined || rating === null || rating <= 0) {
    return <span className="text-xs text-muted-foreground">평가 없음</span>;
  }
  return (
    <span className="inline-flex items-center gap-0.5">
      {[1,2,3,4,5].map(i => {
        const filled = rating >= i;
        const half = !filled && rating >= i - 0.5;
        return (
          <Star
            key={i}
            size={sm?10:12}
            className={
              filled
                ? "fill-amber-400 text-amber-400"
                : half
                  ? "fill-amber-400/50 text-amber-400"
                  : "text-gray-200"
            }
          />
        );
      })}
      <span className="ml-1 text-xs text-muted-foreground">{rating.toFixed(1)}</span>
    </span>
  );
}

function StarPicker({ value, onChange }: { value?: number; onChange: (v?: number) => void }) {
  return (
    <div className="flex items-center gap-1">
      {[1,2,3,4,5].map(i => (
        <button key={i} type="button" onClick={() => onChange(value === i ? undefined : i)}
          className="p-0.5 hover:scale-110 transition-transform">
          <Star size={24} className={i<=(value||0)?"fill-amber-400 text-amber-400":"text-gray-300"}/>
        </button>
      ))}
      <span className="text-sm text-muted-foreground ml-1">{value ? `${value}점` : "평가 없음"}</span>
    </div>
  );
}

function StatusBadge({ status, sm }: { status: Status; sm?: boolean }) {
  return (
    <span className={`inline-flex items-center rounded font-medium ${sm?"text-[10px] px-1.5 py-px":"text-xs px-2 py-0.5"} ${status==="PLANNED"?"bg-blue-100 text-blue-700":"bg-emerald-100 text-emerald-700"}`}>
      {status==="PLANNED"?"예정":"완료"}
    </span>
  );
}

function CategoryBadge({ categoryId, sm }: { categoryId: string; sm?: boolean }) {
  const cat = getCat(categoryId);
  if (!cat) return null;
  return (
    <span className={`inline-flex items-center gap-1 rounded font-medium ${sm?"text-[10px] px-1.5 py-px":"text-xs px-2 py-0.5"}`}
      style={{ backgroundColor: cat.bgColor, color: cat.color }}>
      {cat.icon}{cat.name}
    </span>
  );
}

function Poster({ title, categoryId, size="md", src }: { title: string; categoryId: string; size?: "sm"|"md"|"lg"; src?: string }) {
  const cat = getCat(categoryId);
  const s = { sm:"w-10 h-14 text-base rounded-lg", md:"w-14 h-[84px] text-xl rounded-xl", lg:"w-32 h-48 text-4xl rounded-2xl" }[size];
  if (src) return <img src={src} alt={title} className={`${s} object-cover flex-shrink-0 bg-muted`} />;
  return (
    <div className={`${s} flex items-center justify-center flex-shrink-0 text-white font-bold`}
      style={{ backgroundColor: cat?.color||"#6B7280" }}>
      {title.charAt(0)}
    </div>
  );
}

function ProgressBar({ value, className="" }: { value: number; className?: string }) {
  return (
    <div className={`h-1.5 bg-gray-200 rounded-full overflow-hidden ${className}`}>
      <div className="h-full bg-blue-500 rounded-full transition-all" style={{ width:`${Math.min(100,Math.max(0,value))}%` }}/>
    </div>
  );
}

function Toast({ msg }: { msg: string }) {
  return (
    <div className="fixed bottom-24 sm:bottom-6 left-1/2 -translate-x-1/2 bg-zinc-900 text-white px-4 py-2.5 rounded-xl text-sm shadow-xl z-[70] flex items-center gap-2 whitespace-nowrap">
      <CheckCircle size={14} className="text-emerald-400 flex-shrink-0"/>{msg}
    </div>
  );
}

function ConfirmModal({ title, body, danger, confirmLabel, onConfirm, onClose, children }: {
  title: string; body: string; danger?: boolean; confirmLabel: string;
  onConfirm: () => void; onClose: () => void; children?: ReactNode;
}) {
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-card rounded-2xl w-full max-w-sm p-6 shadow-2xl">
        <h3 className="text-base font-bold text-foreground mb-2">{title}</h3>
        <p className="text-sm text-muted-foreground mb-4">{body}</p>
        {children}
        <div className="flex gap-3 mt-4">
          <button onClick={onClose}
            className="flex-1 border border-border text-foreground py-2.5 rounded-xl font-medium hover:bg-muted transition-colors text-sm">취소</button>
          <button onClick={onConfirm}
            className={`flex-1 py-2.5 rounded-xl font-medium transition-colors text-sm ${danger?"bg-red-500 hover:bg-red-600 text-white":"bg-primary hover:bg-blue-700 text-white"}`}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── TMDB Detail Panel ────────────────────────────────────────────────────────

function TMDBDetailPanel({ result, onClose, onRegister, addedIds }: {
  result: TMDBResult; onClose: () => void;
  onRegister: (r: TMDBResult) => void; addedIds: Set<number>;
}) {
  const isAdded = addedIds.has(result.id);
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-stretch sm:items-center justify-center">
      <div className="bg-card w-full sm:max-w-2xl sm:rounded-2xl overflow-y-auto max-h-screen sm:max-h-[90vh] shadow-2xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border flex-shrink-0">
          <h2 className="font-bold text-foreground">TMDB 상세 정보</h2>
          <button onClick={onClose} className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors"><X size={18}/></button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">
          <div className="flex gap-5 mb-5">
            <Poster title={result.title} categoryId={result.type==="MOVIE"?"movie":"kdrama"} size="lg" src={result.poster} />
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap gap-1.5 mb-2">
                <span className={`text-xs px-2 py-0.5 rounded font-medium ${result.type==="MOVIE"?"bg-blue-100 text-blue-700":"bg-purple-100 text-purple-700"}`}>
                  {result.type==="MOVIE"?"영화":"TV"}
                </span>
                <span className="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded">{result.country}</span>
                {isAdded && <span className="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded">이미 등록됨</span>}
              </div>
              <h1 className="text-xl font-bold text-foreground leading-tight">{result.title}</h1>
              <p className="text-sm text-muted-foreground mb-2">{result.originalTitle}</p>
              <div className="flex items-center gap-1 mb-3">
                <Star size={14} className="fill-amber-400 text-amber-400"/>
                <span className="font-semibold text-foreground">{result.rating}</span>
                <span className="text-xs text-muted-foreground ml-1">TMDB 평점</span>
              </div>
              <div className="space-y-1 text-sm">
                <div className="flex gap-3"><span className="text-muted-foreground w-16 flex-shrink-0">개봉일</span><span>{result.releaseDate}</span></div>
                <div className="flex gap-3"><span className="text-muted-foreground w-16 flex-shrink-0">장르</span><span>{result.genres.join(", ")}</span></div>
                {result.runtime && <div className="flex gap-3"><span className="text-muted-foreground w-16 flex-shrink-0">러닝타임</span><span>{result.runtime}분</span></div>}
                {result.seasons && <div className="flex gap-3"><span className="text-muted-foreground w-16 flex-shrink-0">시즌</span><span>{result.seasons}시즌</span></div>}
              </div>
            </div>
          </div>
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-foreground mb-1.5">줄거리</h3>
            <p className="text-sm text-muted-foreground leading-relaxed">{result.overview}</p>
          </div>
          {result.cast && result.cast.length > 0 && (
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-foreground mb-1.5">주요 출연진</h3>
              <div className="flex flex-wrap gap-1.5">
                {result.cast.map(name => (
                  <span key={name} className="text-xs bg-muted text-muted-foreground px-2 py-1 rounded-lg">{name}</span>
                ))}
              </div>
            </div>
          )}
          <p className="text-[10px] text-muted-foreground border-t border-border pt-3">
            This product uses the TMDB API but is not endorsed or certified by TMDB.
          </p>
        </div>
        <div className="px-5 py-4 border-t border-border flex gap-3 flex-shrink-0">
          <button onClick={onClose}
            className="flex-1 border border-border text-foreground py-2.5 rounded-xl font-medium hover:bg-muted transition-colors text-sm">닫기</button>
          {isAdded
            ? <button className="flex-1 bg-muted text-muted-foreground py-2.5 rounded-xl font-medium text-sm cursor-default">이미 등록됨</button>
            : <button onClick={() => onRegister(result)}
                className="flex-1 bg-primary text-white py-2.5 rounded-xl font-semibold hover:bg-blue-700 transition-colors text-sm">앞으로 볼 항목으로 등록 →</button>
          }
        </div>
      </div>
    </div>
  );
}

// ─── TMDB Register Form ───────────────────────────────────────────────────────

function TMDBRegisterForm({ result, onClose, onSave, showToast }: {
  result: TMDBResult; onClose: () => void;
  onSave: (id: number) => void; showToast: (m: string) => void;
}) {
  const suggested = suggestCategory(result);
  const [title, setTitle] = useState(result.title);
  const [categoryId, setCategoryId] = useState(suggested || "");
  const [collectionQuery, setCollectionQuery] = useState("");
  const [selectedCollectionId, setSelectedCollectionId] = useState<string | undefined>();
  const [progressNote, setProgressNote] = useState("");
  const [memo, setMemo] = useState("");
  const [usePoster, setUsePoster] = useState(!!result.poster);

  const filteredCols = useMemo(() =>
    COLLECTIONS.filter(c => collectionQuery === "" || c.name.includes(collectionQuery)),
  [collectionQuery]);

  const handleSave = () => {
    if (!categoryId) return;
    onSave(result.id);
    showToast(`"${title}"을(를) 앞으로 볼 항목으로 등록했습니다.`);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-stretch sm:items-center justify-center">
      <div className="bg-card w-full sm:max-w-lg sm:rounded-2xl flex flex-col max-h-screen sm:max-h-[90vh] shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border flex-shrink-0">
          <div>
            <h2 className="font-bold text-foreground">앞으로 볼 항목으로 등록</h2>
            <p className="text-xs text-muted-foreground">TMDB 정보를 확인하고 저장하세요</p>
          </div>
          <button onClick={onClose} className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors"><X size={18}/></button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* Auto-filled info */}
          <div className="bg-muted/50 rounded-xl p-4">
            <div className="flex gap-3 mb-2">
              {result.poster && usePoster
                ? <img src={result.poster} alt={result.title} className="w-12 h-[72px] rounded-xl object-cover"/>
                : <Poster title={result.title} categoryId={result.type==="MOVIE"?"movie":"kdrama"} size="sm"/>
              }
              <div>
                <div className="text-sm font-medium text-foreground">{result.title}</div>
                <div className="text-xs text-muted-foreground">{result.originalTitle}</div>
                <div className="flex gap-1.5 mt-1">
                  <span className={`text-[10px] px-1.5 py-px rounded font-medium ${result.type==="MOVIE"?"bg-blue-100 text-blue-700":"bg-purple-100 text-purple-700"}`}>
                    {result.type==="MOVIE"?"영화":"TV"}
                  </span>
                  <span className="text-[10px] bg-muted text-muted-foreground px-1.5 py-px rounded">TMDB</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>개봉일: {result.releaseDate}</span>
              {result.poster && (
                <label className="flex items-center gap-1 cursor-pointer ml-auto">
                  <input type="checkbox" checked={usePoster} onChange={e=>setUsePoster(e.target.checked)} className="w-3 h-3"/>
                  포스터 사용
                </label>
              )}
            </div>
          </div>

          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">제목 <span className="text-red-500">*</span></label>
            <input value={title} onChange={e=>setTitle(e.target.value)}
              className="w-full px-3 py-2.5 border border-border rounded-xl text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/25"/>
          </div>

          {/* Category suggestion */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">Category <span className="text-red-500">*</span></label>
            {suggested && (
              <div className="flex items-start gap-2 bg-blue-50 border border-blue-100 rounded-xl p-3 mb-2 text-xs text-blue-700">
                <AlertTriangle size={13} className="flex-shrink-0 mt-0.5"/>
                <div>
                  <strong>추천 Category: {getCat(suggested)?.name}</strong>
                  <p className="text-blue-600 mt-0.5">TMDB 제작 국가·유형 기준으로 추천했습니다. 저장 전 확인해 주세요.</p>
                </div>
              </div>
            )}
            {!suggested && (
              <div className="flex items-start gap-2 bg-amber-50 border border-amber-100 rounded-xl p-3 mb-2 text-xs text-amber-700">
                <AlertTriangle size={13} className="flex-shrink-0 mt-0.5"/>
                <span>Category를 선택해 주세요. (필수)</span>
              </div>
            )}
            <div className="grid grid-cols-2 gap-1.5">
              {CATEGORIES.map(cat => (
                <button key={cat.id} type="button" onClick={() => setCategoryId(cat.id)}
                  className={`flex items-center gap-1.5 p-2 rounded-lg border text-xs font-medium transition-colors text-left ${categoryId===cat.id?"border-primary bg-blue-50 text-blue-700":"border-border hover:border-primary/30 text-foreground"}`}>
                  <span style={{ color: cat.color }}>{cat.icon}</span>{cat.name}
                </button>
              ))}
            </div>
          </div>

          {/* Collection */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">Collection <span className="text-muted-foreground font-normal text-xs">(선택)</span></label>
            <div className="relative mb-2">
              <Search size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"/>
              <input value={collectionQuery} onChange={e=>setCollectionQuery(e.target.value)}
                placeholder="Collection 검색"
                className="w-full pl-7 pr-3 py-2 border border-border rounded-lg text-xs bg-background focus:outline-none focus:ring-2 focus:ring-primary/25"/>
            </div>
            <div className="border border-border rounded-xl overflow-hidden max-h-32 overflow-y-auto">
              <button type="button" onClick={() => setSelectedCollectionId(undefined)}
                className={`w-full text-left px-3 py-2 text-xs transition-colors border-b border-border ${!selectedCollectionId?"bg-blue-50 text-blue-700":"hover:bg-muted text-foreground"}`}>
                Collection 미지정
              </button>
              {filteredCols.map(col => (
                <button key={col.id} type="button" onClick={() => setSelectedCollectionId(col.id)}
                  className={`w-full text-left px-3 py-2 text-xs transition-colors border-b border-border last:border-0 ${selectedCollectionId===col.id?"bg-blue-50 text-blue-700":"hover:bg-muted text-foreground"}`}>
                  <div className="font-medium">{col.name}</div>
                  <div className="text-muted-foreground">{col.itemCount}개 항목</div>
                </button>
              ))}
            </div>
          </div>

          {/* Progress Note */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">Progress Note <span className="text-muted-foreground font-normal text-xs">(선택)</span></label>
            <input value={progressNote} onChange={e=>setProgressNote(e.target.value)}
              placeholder="예: 1~5권, 시즌 1까지 시청"
              className="w-full px-3 py-2.5 border border-border rounded-xl text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/25"/>
          </div>

          {/* Memo */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">메모 <span className="text-muted-foreground font-normal text-xs">(선택)</span></label>
            <textarea value={memo} onChange={e=>setMemo(e.target.value)} rows={2}
              placeholder="개인 메모"
              className="w-full px-3 py-2.5 border border-border rounded-xl text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/25 resize-none"/>
          </div>
        </div>

        <div className="px-5 py-4 border-t border-border flex gap-3 flex-shrink-0">
          <button onClick={onClose}
            className="flex-1 border border-border text-foreground py-2.5 rounded-xl font-medium hover:bg-muted transition-colors text-sm">취소</button>
          <button onClick={handleSave} disabled={!categoryId || !title.trim()}
            className="flex-1 bg-primary text-white py-2.5 rounded-xl font-semibold hover:bg-blue-700 transition-colors text-sm disabled:opacity-40 disabled:cursor-not-allowed">
            앞으로 볼 항목으로 등록
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Item Form Modal ──────────────────────────────────────────────────────────

function ItemFormModal({ editItem, onClose, onSave, showToast }: {
  editItem?: Item; onClose: () => void;
  onSave: () => void; showToast: (m: string) => void;
}) {
  const [title, setTitle]     = useState(editItem?.title || "");
  const [catId, setCatId]     = useState(editItem?.categoryId || "");
  const [status, setStatus]   = useState<Status>(editItem?.status || "PLANNED");
  const [rating, setRating]   = useState<number|undefined>(editItem?.rating);
  const [colId, setColId]     = useState<string|undefined>(editItem?.collectionId);
  const [prog, setProg]       = useState(editItem?.progressNote || "");
  const [memo, setMemo]       = useState(editItem?.memo || "");
  const [release, setRelease] = useState(editItem?.releaseDate || "");
  const isEdit = !!editItem;

  const handleSave = () => {
    if (!title.trim() || !catId) return;
    onSave();
    showToast(isEdit ? "항목이 수정되었습니다." : "항목이 등록되었습니다.");
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-stretch sm:items-center justify-center">
      <div className="bg-card w-full sm:max-w-lg sm:rounded-2xl flex flex-col max-h-screen sm:max-h-[90vh] shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border flex-shrink-0">
          <h2 className="font-bold text-foreground">{isEdit ? "항목 수정" : "직접 항목 등록"}</h2>
          <button onClick={onClose} className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors"><X size={18}/></button>
        </div>
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">제목 <span className="text-red-500">*</span></label>
            <input value={title} onChange={e=>setTitle(e.target.value)} placeholder="제목을 입력하세요"
              className="w-full px-3 py-2.5 border border-border rounded-xl text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/25"/>
          </div>

          {/* Category */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">Category <span className="text-red-500">*</span></label>
            <div className="grid grid-cols-2 gap-1.5">
              {CATEGORIES.map(cat => (
                <button key={cat.id} type="button" onClick={() => setCatId(cat.id)}
                  className={`flex items-center gap-1.5 p-2 rounded-lg border text-xs font-medium transition-colors ${catId===cat.id?"border-primary bg-blue-50 text-blue-700":"border-border hover:border-primary/30 text-foreground"}`}>
                  <span style={{ color: cat.color }}>{cat.icon}</span>{cat.name}
                </button>
              ))}
            </div>
          </div>

          {/* Status */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">상태</label>
            <div className="flex bg-muted rounded-xl p-0.5">
              {(["PLANNED","COMPLETED"] as Status[]).map(s => (
                <button key={s} type="button" onClick={() => setStatus(s)}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${status===s?"bg-card shadow text-foreground":"text-muted-foreground hover:text-foreground"}`}>
                  {s==="PLANNED"?"앞으로 볼 항목":"완료 항목"}
                </button>
              ))}
            </div>
          </div>

          {/* Rating */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">평점 <span className="text-muted-foreground font-normal text-xs">(선택 · 0.5점 단위)</span></label>
            <StarPicker value={rating} onChange={setRating} />
          </div>

          {/* Collection */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">Collection <span className="text-muted-foreground font-normal text-xs">(선택)</span></label>
            <select value={colId || ""} onChange={e => setColId(e.target.value || undefined)}
              className="w-full px-3 py-2.5 border border-border rounded-xl text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/25">
              <option value="">Collection 미지정</option>
              {COLLECTIONS.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>

          {/* Progress Note */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">Progress Note <span className="text-muted-foreground font-normal text-xs">(Collection과 구분됩니다)</span></label>
            <input value={prog} onChange={e=>setProg(e.target.value)}
              placeholder="예: 1~82, 84, 87~89 / 15권까지 읽음"
              className="w-full px-3 py-2.5 border border-border rounded-xl text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/25"/>
          </div>

          {/* Release date */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">출시·방영일 <span className="text-muted-foreground font-normal text-xs">(선택)</span></label>
            <input type="date" value={release} onChange={e=>setRelease(e.target.value)}
              className="w-full px-3 py-2.5 border border-border rounded-xl text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/25"/>
          </div>

          {/* Memo */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">메모 <span className="text-muted-foreground font-normal text-xs">(선택)</span></label>
            <textarea value={memo} onChange={e=>setMemo(e.target.value)} rows={2}
              placeholder="개인 메모"
              className="w-full px-3 py-2.5 border border-border rounded-xl text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/25 resize-none"/>
          </div>

          {/* Poster placeholder */}
          <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-xl">
            <Lock size={14} className="text-muted-foreground flex-shrink-0"/>
            <span className="text-xs text-muted-foreground">포스터 URL·이미지 업로드는 향후 제공 예정입니다.</span>
          </div>
        </div>
        <div className="px-5 py-4 border-t border-border flex gap-3 flex-shrink-0">
          <button onClick={onClose}
            className="flex-1 border border-border text-foreground py-2.5 rounded-xl font-medium hover:bg-muted transition-colors text-sm">취소</button>
          <button onClick={handleSave} disabled={!title.trim() || !catId}
            className="flex-1 bg-primary text-white py-2.5 rounded-xl font-semibold hover:bg-blue-700 transition-colors text-sm disabled:opacity-40 disabled:cursor-not-allowed">
            저장
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Item Detail Page ─────────────────────────────────────────────────────────

function ItemDetailPage({ itemId, onBack, showToast, backLabel = "목록으로" }: {
  itemId: string | null;
  onBack: () => void;
  showToast: (m: string) => void;
  backLabel?: string;
}) {
  const { item, isLoading, error, reload } = useItemDetail(itemId);

  if (!itemId) {
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6">
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5">
          <ChevronLeft size={16}/> {backLabel}
        </button>
        <div className="bg-card border border-border rounded-2xl p-8 text-center">
          <p className="font-medium text-foreground mb-4">선택된 항목이 없습니다.</p>
          <button onClick={onBack}
            className="inline-flex items-center gap-1.5 text-sm bg-primary text-white px-4 py-2 rounded-xl hover:bg-blue-700 transition-colors font-medium">
            {backLabel} 돌아가기
          </button>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6">
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5">
          <ChevronLeft size={16}/> {backLabel}
        </button>
        <div className="bg-card border border-border rounded-2xl p-6 mb-4">
          <div className="flex gap-5">
            <div className="w-32 h-48 rounded-2xl animate-pulse bg-muted flex-shrink-0"/>
            <div className="flex-1 min-w-0 space-y-3">
              <div className="h-4 w-24 animate-pulse rounded bg-muted"/>
              <div className="h-7 w-3/4 animate-pulse rounded bg-muted"/>
              <div className="h-4 w-32 animate-pulse rounded bg-muted"/>
              <div className="h-4 w-40 animate-pulse rounded bg-muted"/>
            </div>
          </div>
        </div>
        <div className="bg-card border border-border rounded-2xl p-5 mb-4 space-y-3">
          {[0,1,2,3].map(i => <div key={i} className="h-4 w-full animate-pulse rounded bg-muted"/>)}
        </div>
        <div className="space-y-2.5">
          {[0,1,2].map(i => <div key={i} className="h-12 w-full animate-pulse rounded-xl bg-muted"/>)}
        </div>
      </div>
    );
  }

  if (error) {
    const isNotFound = error.status === 404;
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6">
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5">
          <ChevronLeft size={16}/> {backLabel}
        </button>
        <div className="bg-card border border-border rounded-2xl p-8 text-center">
          <p className="font-medium text-foreground mb-2">
            {isNotFound ? "항목을 찾을 수 없습니다." : "항목 정보를 불러오지 못했습니다."}
          </p>
          {isNotFound && (
            <p className="text-sm text-muted-foreground mb-5">삭제되었거나 접근할 수 없는 항목입니다.</p>
          )}
          <div className="flex flex-wrap gap-2 justify-center">
            {!isNotFound && (
              <button onClick={reload}
                className="inline-flex items-center gap-1.5 text-sm bg-primary text-white px-4 py-2 rounded-xl hover:bg-blue-700 transition-colors font-medium">
                <RefreshCw size={14}/> 다시 시도
              </button>
            )}
            <button onClick={onBack}
              className="inline-flex items-center gap-1.5 text-sm border border-border text-foreground px-4 py-2 rounded-xl hover:bg-muted transition-colors font-medium">
              {backLabel} 돌아가기
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!item) {
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6">
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5">
          <ChevronLeft size={16}/> {backLabel}
        </button>
        <div className="bg-card border border-border rounded-2xl p-8 text-center">
          <p className="font-medium text-foreground mb-4">선택된 항목이 없습니다.</p>
          <button onClick={onBack}
            className="inline-flex items-center gap-1.5 text-sm bg-primary text-white px-4 py-2 rounded-xl hover:bg-blue-700 transition-colors font-medium">
            {backLabel} 돌아가기
          </button>
        </div>
      </div>
    );
  }

  const vm = mapApiItemDetailToViewModel(item);
  const Icon = vm.presentation.icon;
  const createdLabel = formatDate(vm.createdAt);
  const updatedLabel = formatDate(vm.updatedAt);

  const detailRows = [
    {
      label: "Progress Note",
      value: vm.progressNote ?? "등록된 진행 정보가 없습니다.",
      muted: !vm.progressNote,
    },
    {
      label: "메모",
      value: vm.memo ?? "등록된 메모가 없습니다.",
      muted: !vm.memo,
    },
    { label: "등록일", value: createdLabel || "—", muted: !createdLabel },
    { label: "수정일", value: updatedLabel || "—", muted: !updatedLabel },
  ];

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6">
      <button onClick={onBack} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5">
        <ChevronLeft size={16}/> {backLabel}
      </button>

      {/* Header */}
      <div className="bg-card border border-border rounded-2xl p-6 mb-4">
        <div className="flex gap-5">
          <div className="w-32 h-48 text-4xl rounded-2xl flex items-center justify-center flex-shrink-0 text-white font-bold"
            style={{ backgroundColor: vm.presentation.color }}>
            {vm.title.charAt(0)}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap gap-1.5 mb-2">
              <span className="inline-flex items-center gap-1 rounded font-medium text-xs px-2 py-0.5"
                style={{ backgroundColor: vm.presentation.bgColor, color: vm.presentation.color }}>
                <Icon size={14}/>{vm.categoryName}
              </span>
              <StatusBadge status={vm.status}/>
            </div>
            <h1 className="text-xl font-bold text-foreground leading-tight mb-1 break-words">{vm.title}</h1>
            <div className="mb-2"><StarRating rating={displayDetailRating(vm.rating)}/></div>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Layers size={12}/><span>Collection: </span>
              <span className="font-medium text-foreground">{vm.collectionName ?? "미지정"}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Details */}
      <div className="bg-card border border-border rounded-2xl overflow-hidden mb-4">
        {detailRows.map((row, i, arr) => (
          <div key={row.label} className={`flex gap-4 px-5 py-3 text-sm ${i < arr.length-1?"border-b border-border":""}`}>
            <span className="text-muted-foreground w-28 flex-shrink-0">{row.label}</span>
            <span className={`min-w-0 break-words ${row.muted ? "text-muted-foreground" : "text-foreground"}`}>{row.value}</span>
          </div>
        ))}
      </div>

      <div className="bg-card border border-border rounded-2xl p-5 mb-4">
        <h3 className="text-sm font-semibold text-foreground mb-2">줄거리</h3>
        <p className="text-sm text-muted-foreground leading-relaxed">등록된 상세 설명이 없습니다.</p>
      </div>

      {/* Actions — write APIs not connected */}
      <div className="space-y-2.5">
        <button onClick={() => showToast("항목 수정 기능은 다음 단계에서 제공됩니다.")}
          className="w-full flex items-center gap-2 justify-center border border-border bg-card text-foreground py-3 rounded-xl font-medium hover:bg-muted transition-colors text-sm">
          <Edit2 size={15}/> 수정
        </button>

        {vm.status === "PLANNED" ? (
          <button onClick={() => showToast("상태 변경 기능은 다음 단계에서 제공됩니다.")}
            className="w-full flex items-center gap-2 justify-center bg-emerald-600 text-white py-3 rounded-xl font-medium hover:bg-emerald-700 transition-colors text-sm">
            <Check size={15}/> 완료 처리
          </button>
        ) : (
          <button onClick={() => showToast("상태 변경 기능은 다음 단계에서 제공됩니다.")}
            className="w-full flex items-center gap-2 justify-center border border-border text-foreground py-3 rounded-xl font-medium hover:bg-muted transition-colors text-sm">
            <RefreshCw size={15}/> PLANNED로 되돌리기
          </button>
        )}

        <button onClick={() => showToast("항목 수정 기능은 다음 단계에서 제공됩니다.")}
          className="w-full flex items-center gap-2 justify-center border border-border text-foreground py-3 rounded-xl font-medium hover:bg-muted transition-colors text-sm">
          <Layers size={15}/> Collection 이동
        </button>

        <button onClick={() => showToast("항목 삭제 기능은 다음 단계에서 제공됩니다.")}
          className="w-full flex items-center gap-2 justify-center border border-red-200 text-red-600 py-3 rounded-xl font-medium hover:bg-red-50 transition-colors text-sm">
          <Trash2 size={15}/> 삭제
        </button>
      </div>
    </div>
  );
}

// ─── History Detail Page ──────────────────────────────────────────────────────

function HistoryDetailPage({ entry, onBack, showToast }: {
  entry: HistoryEntry; onBack: () => void; showToast: (m: string) => void;
}) {
  const [showDelete, setShowDelete] = useState(false);
  const item = entry.itemId ? ITEMS.find(i => i.id === entry.itemId) : null;
  const col  = entry.collectionId ? getCol(entry.collectionId) : null;
  const colItems = col ? ITEMS.filter(i => i.collectionId === col.id) : [];
  const statusChanged = entry.statusAtTime !== entry.currentStatus;

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6">
      <button onClick={onBack} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5">
        <ChevronLeft size={16}/> 추천 이력
      </button>
      <h1 className="text-xl font-bold text-foreground mb-5">추천 이력 상세</h1>

      <div className="bg-card border border-border rounded-2xl p-5 mb-4">
        <div className="flex flex-wrap gap-1.5 mb-3">
          <CategoryBadge categoryId={entry.categoryId}/>
          <span className={`text-xs px-2 py-0.5 rounded font-medium ${entry.type==="ITEM"?"bg-blue-100 text-blue-700":"bg-purple-100 text-purple-700"}`}>
            {entry.type==="ITEM"?"단일 항목":"Collection"}
          </span>
        </div>
        <h2 className="text-lg font-bold text-foreground mb-1">{entry.title}</h2>
        <p className="text-sm text-muted-foreground mb-3">{entry.selectedAt} 선택</p>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-xs text-muted-foreground mb-0.5">선택 당시 상태</p>
            <StatusBadge status={entry.statusAtTime}/>
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-0.5">현재 상태</p>
            <StatusBadge status={entry.currentStatus}/>
          </div>
        </div>
        {statusChanged && (
          <div className="mt-3 flex items-center gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
            <AlertTriangle size={12}/> 선택 이후 상태가 변경되었습니다.
          </div>
        )}
      </div>

      {/* Snapshot */}
      {entry.type === "ITEM" && item && (
        <div className="bg-card border border-border rounded-2xl overflow-hidden mb-4">
          <div className="px-4 py-3 border-b border-border bg-muted/30">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">선택 당시 Snapshot</p>
          </div>
          <div className="p-4 flex gap-4">
            <Poster title={item.title} categoryId={item.categoryId} size="sm"/>
            <div className="flex-1 min-w-0 text-sm space-y-1">
              <div className="font-medium text-foreground">{item.title}</div>
              {item.rating && <StarRating rating={item.rating} sm/>}
              {item.progressNote && <div className="text-xs text-muted-foreground">{item.progressNote}</div>}
              {item.releaseDate && <div className="text-xs text-muted-foreground">{item.releaseDate}</div>}
            </div>
          </div>
        </div>
      )}

      {entry.type === "COLLECTION" && col && (
        <div className="bg-card border border-border rounded-2xl overflow-hidden mb-4">
          <div className="px-4 py-3 border-b border-border bg-muted/30">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">당시 Collection 항목</p>
          </div>
          <div className="divide-y divide-border">
            {colItems.map(ci => (
              <div key={ci.id} className="flex items-center gap-3 px-4 py-3">
                <Poster title={ci.title} categoryId={ci.categoryId} size="sm"/>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-foreground truncate">{ci.title}</div>
                </div>
                <StatusBadge status={ci.status} sm/>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-muted/50 rounded-xl p-3 mb-5 text-xs text-muted-foreground">
        추천 이력을 삭제해도 실제 Item과 Collection은 삭제되지 않습니다.
      </div>

      <div className="flex gap-3">
        <button className="flex-1 border border-border text-foreground py-3 rounded-xl font-medium hover:bg-muted transition-colors text-sm">
          {entry.type==="ITEM"?"현재 항목 상세보기":"현재 Collection 상세보기"}
        </button>
        <button onClick={() => setShowDelete(true)}
          className="border border-red-200 text-red-600 px-5 py-3 rounded-xl font-medium hover:bg-red-50 transition-colors text-sm flex items-center gap-1.5">
          <Trash2 size={14}/> 이력 삭제
        </button>
      </div>

      {showDelete && (
        <ConfirmModal
          title="이력을 삭제할까요?"
          body="추천 이력을 삭제해도 실제 Item과 Collection은 삭제되지 않습니다."
          danger confirmLabel="이력 삭제"
          onConfirm={() => { setShowDelete(false); showToast("추천 이력이 삭제되었습니다."); onBack(); }}
          onClose={() => setShowDelete(false)}
        />
      )}
    </div>
  );
}

// ─── Category Manage Page ─────────────────────────────────────────────────────

function CategoryManagePage({ onBack, showToast }: { onBack: () => void; showToast: (m: string) => void }) {
  const [showAdd, setShowAdd]     = useState(false);
  const [editTarget, setEdit]     = useState<Category | null>(null);
  const [deleteTarget, setDelete] = useState<Category | null>(null);
  const [newName, setNewName]     = useState("");
  const [newColor, setNewColor]   = useState("#3B82F6");

  const COLORS = ["#3B82F6","#8B5CF6","#F97316","#EF4444","#EC4899","#6366F1","#D97706","#10B981","#F59E0B","#71717A"];
  const hasItems = (cat: Category) => cat.total > 0;

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6">
      <button onClick={onBack} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5">
        <ChevronLeft size={16}/> 설정
      </button>
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-xl font-bold text-foreground">Category 관리</h1>
        <button onClick={() => { setShowAdd(true); setNewName(""); setNewColor("#3B82F6"); }}
          className="inline-flex items-center gap-1.5 bg-primary text-white px-4 py-2 rounded-xl text-sm font-medium hover:bg-blue-700 transition-colors">
          <Plus size={14}/> 추가
        </button>
      </div>

      <p className="text-xs text-muted-foreground mb-4">드래그 핸들로 순서를 변경할 수 있습니다.</p>

      <div className="space-y-2">
        {CATEGORIES.map(cat => (
          <div key={cat.id} className="bg-card border border-border rounded-2xl p-4 flex items-center gap-3">
            <div className="text-muted-foreground cursor-grab flex-shrink-0"><GripVertical size={16}/></div>
            <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
              style={{ backgroundColor: cat.bgColor, color: cat.color }}>
              {cat.icon}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold text-foreground">{cat.name}</div>
              <div className="flex gap-3 text-[10px] text-muted-foreground mt-0.5">
                <span>전체 {cat.total.toLocaleString()}</span>
                <span className="text-blue-600">예정 {cat.planned.toLocaleString()}</span>
                <span className="text-emerald-600">완료 {cat.completed.toLocaleString()}</span>
              </div>
            </div>
            <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: cat.color }}/>
            <button onClick={() => setEdit(cat)}
              className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors flex-shrink-0">
              <Edit2 size={14}/>
            </button>
            <button onClick={() => setDelete(cat)}
              className="p-1.5 text-muted-foreground hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors flex-shrink-0">
              <Trash2 size={14}/>
            </button>
          </div>
        ))}
      </div>

      {/* Add / Edit modal */}
      {(showAdd || editTarget) && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-card rounded-2xl w-full max-w-sm p-6 shadow-2xl">
            <h3 className="font-bold text-foreground mb-4">{editTarget ? "Category 수정" : "Category 추가"}</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">이름 <span className="text-red-500">*</span></label>
                <input value={editTarget ? editTarget.name : newName}
                  onChange={e => editTarget ? null : setNewName(e.target.value)}
                  placeholder="Category 이름"
                  className="w-full px-3 py-2.5 border border-border rounded-xl text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/25"/>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">색상</label>
                <div className="flex flex-wrap gap-2">
                  {COLORS.map(c => (
                    <button key={c} type="button" onClick={() => setNewColor(c)}
                      className={`w-7 h-7 rounded-full transition-transform hover:scale-110 ${newColor===c?"ring-2 ring-offset-2 ring-gray-400 scale-110":""}`}
                      style={{ backgroundColor: c }}/>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">아이콘</label>
                <div className="flex gap-2">
                  {[<Film size={16}/>, <Tv size={16}/>, <Smile size={16}/>, <BookOpen size={16}/>, <Utensils size={16}/>].map((icon, i) => (
                    <button key={i} type="button"
                      className="p-2 border border-border rounded-lg text-muted-foreground hover:text-foreground hover:border-primary/40 transition-colors">
                      {icon}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex gap-3 mt-5">
              <button onClick={() => { setShowAdd(false); setEdit(null); }}
                className="flex-1 border border-border text-foreground py-2.5 rounded-xl font-medium hover:bg-muted transition-colors text-sm">취소</button>
              <button onClick={() => { setShowAdd(false); setEdit(null); showToast("Category가 저장되었습니다."); }}
                className="flex-1 bg-primary text-white py-2.5 rounded-xl font-medium hover:bg-blue-700 transition-colors text-sm">저장</button>
            </div>
          </div>
        </div>
      )}

      {/* Delete modal */}
      {deleteTarget && (
        hasItems(deleteTarget) ? (
          <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
            <div className="bg-card rounded-2xl w-full max-w-sm p-6 shadow-2xl">
              <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center mx-auto mb-3">
                <AlertTriangle size={20} className="text-amber-600"/>
              </div>
              <h3 className="font-bold text-foreground text-center mb-2">삭제할 수 없습니다</h3>
              <p className="text-sm text-muted-foreground text-center mb-1">
                이 Category에는 등록된 항목이 있습니다.
              </p>
              <p className="text-sm text-muted-foreground text-center mb-4">
                항목이 있는 Category는 삭제할 수 없습니다.
              </p>
              <div className="flex gap-3">
                <button className="flex-1 border border-border text-foreground py-2.5 rounded-xl text-sm font-medium hover:bg-muted transition-colors">
                  항목 보기
                </button>
                <button onClick={() => setDelete(null)}
                  className="flex-1 bg-primary text-white py-2.5 rounded-xl text-sm font-medium hover:bg-blue-700 transition-colors">
                  확인
                </button>
              </div>
            </div>
          </div>
        ) : (
          <ConfirmModal
            title="Category를 삭제할까요?"
            body={`"${deleteTarget.name}"을(를) 삭제합니다.`}
            danger confirmLabel="삭제"
            onConfirm={() => { setDelete(null); showToast("Category가 삭제되었습니다."); }}
            onClose={() => setDelete(null)}
          />
        )
      )}
    </div>
  );
}

// ─── Home Page ────────────────────────────────────────────────────────────────

function HomeSectionError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="bg-card border border-border rounded-xl p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
      <p className="text-sm text-muted-foreground">{message}</p>
      <button onClick={onRetry}
        className="inline-flex items-center justify-center gap-1.5 text-xs bg-primary text-white px-3 py-1.5 rounded-xl hover:bg-blue-700 transition-colors font-medium self-start sm:self-auto">
        <RefreshCw size={12}/> 다시 시도
      </button>
    </div>
  );
}

function HomePage({ setPage, navigateToRecommend, openAddItem, openItemDetail }: {
  setPage: (p: Page) => void;
  navigateToRecommend: (cats: string[]) => void;
  openAddItem: () => void;
  openItemDetail: (itemId: string) => void;
}) {
  // Hook lives in HomePage: App uses conditional page render, so data loads on Home entry
  // and refetches when returning to Home (no cache library in B-2a).
  const {
    summary,
    categories,
    recentItems,
    isSummaryLoading,
    isCategoriesLoading,
    isRecentItemsLoading,
    summaryError,
    categoriesError,
    recentItemsError,
    reloadSummary,
    reloadCategories,
    reloadRecentItems,
  } = useHomeReadData();

  const homeCategories = categories.map(mapApiCategoryToHomeCategory);
  const recent = recentItems.map(mapApiItemToHomeRecentItem);

  // Keep Mock slug IDs for RecommendPage compatibility (not API UUIDs).
  const quickRec = [
    { label:"영화 추천",  cats:["movie"] },
    { label:"드라마 추천", cats:["kdrama","jdrama","usdrama","cndrama"] },
    { label:"애니 추천",  cats:["anime","animemov"] },
    { label:"예능 추천",  cats:["variety"] },
    { label:"음식 추천",  cats:["food"] },
  ];

  const statDefs = [
    { label:"전체 항목",    key:"item_count" as const },
    { label:"앞으로 볼",    key:"planned_count" as const },
    { label:"완료 항목",    key:"completed_count" as const },
    { label:"Collection",  key:"collection_count" as const },
  ];

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 space-y-7">
      {/* Hero */}
      <div className="bg-card border border-border rounded-2xl p-6 sm:p-8">
        <p className="text-sm text-muted-foreground mb-1">안녕하세요, 박민준님 👋</p>
        <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-5">오늘은 무엇을 선택할까요?</h1>
        <div className="flex flex-wrap gap-3">
          <button onClick={() => navigateToRecommend([])}
            className="inline-flex items-center gap-2 bg-primary text-white px-5 py-2.5 rounded-xl font-medium hover:bg-blue-700 transition-colors">
            <Shuffle size={16}/> 랜덤 추천 시작
          </button>
          <button onClick={() => setPage("search")}
            className="inline-flex items-center gap-2 border border-border bg-card text-foreground px-5 py-2.5 rounded-xl font-medium hover:bg-muted transition-colors">
            <Search size={16}/> 콘텐츠 검색
          </button>
          <button onClick={openAddItem}
            className="inline-flex items-center gap-2 text-primary px-4 py-2.5 rounded-xl font-medium hover:bg-blue-50 transition-colors">
            <Plus size={16}/> 직접 항목 추가
          </button>
        </div>
      </div>

      {/* Stats — Backend Summary (no Mock fallback) */}
      <div>
        <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">요약 통계</h2>
        {summaryError && !isSummaryLoading ? (
          <HomeSectionError message="통계를 불러오지 못했습니다." onRetry={reloadSummary}/>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {statDefs.map(s => (
              <div key={s.label} className="bg-card border border-border rounded-2xl p-4">
                {isSummaryLoading || !summary ? (
                  <div className="h-8 w-20 animate-pulse rounded bg-muted"/>
                ) : (
                  <div className="text-2xl font-bold text-foreground">
                    {summary[s.key].toLocaleString("ko-KR")}
                  </div>
                )}
                <div className="text-xs text-muted-foreground mt-0.5">{s.label}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Quick Recommend — Mock recommend flow unchanged */}
      <div>
        <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">빠른 추천</h2>
        <div className="flex flex-wrap gap-2">
          {quickRec.map(q => {
            const firstCat = getCat(q.cats[0])!;
            return (
              <button key={q.label} onClick={() => navigateToRecommend(q.cats)}
                className="inline-flex items-center gap-1.5 border border-border bg-card px-4 py-2 rounded-xl text-sm font-medium hover:border-blue-300 hover:bg-blue-50 transition-colors">
                <span style={{ color: firstCat.color }}>{firstCat.icon}</span>{q.label}
              </button>
            );
          })}
        </div>
        <p className="text-xs text-muted-foreground mt-2">선택한 카테고리가 추천 설정에 미리 반영됩니다.</p>
      </div>

      <div className="grid sm:grid-cols-2 gap-6">
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">최근 등록</h2>
            <button onClick={() => setPage("items")} className="text-xs text-primary hover:underline">전체 보기</button>
          </div>
          {recentItemsError && !isRecentItemsLoading ? (
            <HomeSectionError message="최근 등록 항목을 불러오지 못했습니다." onRetry={reloadRecentItems}/>
          ) : isRecentItemsLoading ? (
            <div className="space-y-2">
              {[0,1,2,3,4].map(i => (
                <div key={i} className="bg-card border border-border rounded-xl p-3 flex items-center gap-3">
                  <div className="w-10 h-14 rounded-lg animate-pulse bg-muted flex-shrink-0"/>
                  <div className="flex-1 min-w-0 space-y-2">
                    <div className="h-4 w-3/4 animate-pulse rounded bg-muted"/>
                    <div className="h-3 w-1/3 animate-pulse rounded bg-muted"/>
                  </div>
                  <div className="h-4 w-10 animate-pulse rounded bg-muted flex-shrink-0"/>
                </div>
              ))}
            </div>
          ) : recent.length === 0 ? (
            <div className="bg-card border border-border rounded-xl p-4">
              <p className="text-sm text-muted-foreground">최근 등록된 항목이 없습니다.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {recent.map(item => {
                const Icon = item.presentation.icon;
                return (
                  <div key={item.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => openItemDetail(item.id)}
                    onKeyDown={e => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        openItemDetail(item.id);
                      }
                    }}
                    className="bg-card border border-border rounded-xl p-3 flex items-center gap-3 hover:border-primary/20 transition-colors cursor-pointer">
                    {/* Placeholder poster — Legacy items have no poster_path */}
                    <div className="w-10 h-14 text-base rounded-lg flex items-center justify-center flex-shrink-0 text-white font-bold"
                      style={{ backgroundColor: item.presentation.color }}>
                      {item.title.charAt(0)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-foreground truncate">{item.title}</div>
                      <div className="mt-0.5">
                        <span className="inline-flex items-center gap-1 rounded font-medium text-[10px] px-1.5 py-px"
                          style={{ backgroundColor: item.presentation.bgColor, color: item.presentation.color }}>
                          <Icon size={10}/>{item.categoryName}
                        </span>
                      </div>
                    </div>
                    <StatusBadge status={item.status} sm/>
                  </div>
                );
              })}
            </div>
          )}
        </div>
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">최근 선택 이력</h2>
            <button onClick={() => setPage("history")} className="text-xs text-primary hover:underline">전체 보기</button>
          </div>
          <div className="space-y-2">
            {HISTORY.map(h => (
              <div key={h.id} className="bg-card border border-border rounded-xl p-3 flex items-center gap-3">
                <div className="w-8 h-8 rounded-xl bg-blue-100 flex items-center justify-center flex-shrink-0">
                  {h.type==="COLLECTION" ? <Layers size={14} className="text-blue-600"/> : <Shuffle size={14} className="text-blue-600"/>}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-foreground truncate">{h.title}</div>
                  <div className="text-xs text-muted-foreground">{h.selectedAt}</div>
                </div>
                <StatusBadge status={h.currentStatus} sm/>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div>
        <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">카테고리별 현황</h2>
        {categoriesError && !isCategoriesLoading ? (
          <HomeSectionError message="카테고리를 불러오지 못했습니다." onRetry={reloadCategories}/>
        ) : isCategoriesLoading ? (
          <div className="grid sm:grid-cols-2 gap-2">
            {[0,1,2,3,4,5].map(i => (
              <div key={i} className="bg-card border border-border rounded-xl p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="h-4 w-24 animate-pulse rounded bg-muted"/>
                  <div className="h-3 w-12 animate-pulse rounded bg-muted"/>
                </div>
                <div className="h-1.5 w-full animate-pulse rounded-full bg-muted"/>
                <div className="flex justify-between">
                  <div className="h-3 w-16 animate-pulse rounded bg-muted"/>
                  <div className="h-3 w-16 animate-pulse rounded bg-muted"/>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 gap-2">
            {homeCategories.map(cat => {
              const Icon = cat.presentation.icon;
              const total = cat.itemCount;
              return (
                <div key={cat.id} className="bg-card border border-border rounded-xl p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span style={{ color: cat.presentation.color }}><Icon size={14}/></span>
                      <span className="text-sm font-medium text-foreground">{cat.name}</span>
                    </div>
                    <span className="text-xs text-muted-foreground">{total.toLocaleString("ko-KR")}개</span>
                  </div>
                  <ProgressBar value={total > 0 ? (cat.completedCount / total) * 100 : 0}/>
                  <div className="flex justify-between mt-1.5 text-xs">
                    <span className="text-blue-600">예정 {cat.plannedCount.toLocaleString("ko-KR")}</span>
                    <span className="text-emerald-600">완료 {cat.completedCount.toLocaleString("ko-KR")}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Search Page ──────────────────────────────────────────────────────────────

function SearchPage({ showToast }: { showToast: (m: string) => void }) {
  const [query, setQuery]         = useState("");
  const [active, setActive]       = useState("");
  const [typeF, setTypeF]         = useState<"all"|"MOVIE"|"TV">("all");
  const [detailItem, setDetailItem]   = useState<TMDBResult | null>(null);
  const [registerItem, setRegItem]    = useState<TMDBResult | null>(null);
  const [addedIds, setAddedIds]       = useState<Set<number>>(
    new Set(TMDB_RESULTS.filter(r => r.alreadyAdded).map(r => r.id))
  );

  const results = useMemo(() =>
    TMDB_RESULTS.filter(r =>
      (typeF==="all" || r.type===typeF) &&
      (active==="" || r.title.includes(active) || r.originalTitle.toLowerCase().includes(active.toLowerCase()))
    ), [active, typeF]);

  const handleRegister = (id: number) => {
    setAddedIds(prev => new Set([...prev, id]));
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6">
      <h1 className="text-xl font-bold text-foreground mb-5">영화·드라마 검색</h1>

      <div className="flex gap-2 mb-4">
        <div className="flex-1 relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"/>
          <input value={query} onChange={e=>setQuery(e.target.value)}
            onKeyDown={e=>e.key==="Enter"&&setActive(query)}
            placeholder="영화 또는 드라마 제목을 검색하세요"
            className="w-full pl-9 pr-4 py-2.5 border border-border rounded-xl bg-card text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/25 focus:border-primary"/>
        </div>
        <button onClick={() => setActive(query)}
          className="bg-primary text-white px-5 rounded-xl font-medium hover:bg-blue-700 transition-colors text-sm">검색</button>
      </div>

      <div className="flex gap-1.5 mb-5">
        {([["all","전체"],["MOVIE","영화"],["TV","TV·드라마"]] as const).map(([v,l]) => (
          <button key={v} onClick={() => setTypeF(v)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium border transition-colors ${typeF===v?"bg-primary text-white border-primary":"border-border bg-card text-foreground hover:border-primary/50"}`}>
            {l}
          </button>
        ))}
      </div>

      <p className="text-[10px] text-muted-foreground mb-4">{results.length}건 · This product uses the TMDB API but is not endorsed or certified by TMDB.</p>

      <div className="grid sm:grid-cols-2 gap-4">
        {results.map(item => {
          const isAdded = addedIds.has(item.id);
          return (
            <div key={item.id} className="bg-card border border-border rounded-2xl p-4 flex gap-4 hover:border-border/60 transition-colors">
              <Poster title={item.title} categoryId={item.type==="MOVIE"?"movie":"kdrama"} size="md" src={item.poster}/>
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-1.5 mb-1">
                  <div>
                    <div className="font-semibold text-foreground text-sm leading-snug">{item.title}</div>
                    <div className="text-[10px] text-muted-foreground">{item.originalTitle}</div>
                  </div>
                  {isAdded && (
                    <div className="flex-shrink-0 text-right">
                      <span className="text-[10px] bg-emerald-100 text-emerald-700 px-1.5 py-px rounded block">등록됨</span>
                    </div>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-1 mb-2">
                  <span className={`text-[10px] px-1.5 py-px rounded font-medium ${item.type==="MOVIE"?"bg-blue-100 text-blue-700":"bg-purple-100 text-purple-700"}`}>
                    {item.type==="MOVIE"?"영화":"TV"}
                  </span>
                  <span className="text-[10px] text-muted-foreground">{item.country} · {item.releaseDate.slice(0,4)}</span>
                  <span className="flex items-center gap-0.5 text-[10px] text-amber-600">
                    <Star size={9} className="fill-amber-400 text-amber-400"/>{item.rating}
                  </span>
                </div>
                {isAdded && (
                  <div className="text-[10px] text-muted-foreground mb-2">
                    현재 상태: <StatusBadge status="PLANNED" sm/>
                    <span className="ml-1">· {getCat(item.type==="MOVIE"?"movie":"kdrama")?.name}</span>
                  </div>
                )}
                <p className="text-[11px] text-muted-foreground line-clamp-2 mb-2.5 leading-relaxed">{item.overview}</p>
                <div className="flex gap-1.5">
                  <button onClick={() => setDetailItem(item)}
                    className="text-xs text-primary border border-primary/20 px-2.5 py-1 rounded-lg hover:bg-blue-50 transition-colors">
                    상세보기
                  </button>
                  {isAdded
                    ? <button className="text-xs text-muted-foreground border border-border px-2.5 py-1 rounded-lg">기존 항목 보기</button>
                    : <button onClick={() => setDetailItem(item)}
                        className="text-xs bg-primary text-white px-2.5 py-1 rounded-lg hover:bg-blue-700 transition-colors">등록</button>
                  }
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {detailItem && !registerItem && (
        <TMDBDetailPanel
          result={detailItem}
          addedIds={addedIds}
          onClose={() => setDetailItem(null)}
          onRegister={r => { setRegItem(r); setDetailItem(null); }}
        />
      )}
      {registerItem && (
        <TMDBRegisterForm
          result={registerItem}
          onClose={() => setRegItem(null)}
          onSave={handleRegister}
          showToast={showToast}
        />
      )}
    </div>
  );
}

// ─── Recommend Page ───────────────────────────────────────────────────────────

function RecommendPage({ preselectedCats, showToast }: { preselectedCats: string[]; showToast: (m: string) => void }) {
  const [step, setStep]       = useState<RecommendStep>("setup");
  const [selCats, setSelCats] = useState<string[]>(preselectedCats);
  const [statusF, setStatusF] = useState<"PLANNED"|"COMPLETED"|"all">("PLANNED");
  const [exclRecent, setExcl] = useState(false);
  const [result, setResult]   = useState<Candidate | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [spinning, setSpin]   = useState(false);

  const toggleCat = (id: string) =>
    setSelCats(p => p.includes(id) ? p.filter(c => c !== id) : [...p, id]);

  const buildPool = useCallback((): Candidate[] => {
    const itemCands: Candidate[] = ITEMS
      .filter(item => {
        if (item.collectionId) return false;
        if (statusF !== "all" && item.status !== statusF) return false;
        if (selCats.length > 0 && !selCats.includes(item.categoryId)) return false;
        if (exclRecent && HISTORY.slice(0,3).some(h => h.itemId===item.id)) return false;
        return true;
      })
      .map(item => ({ type:"ITEM" as const, data: item }));

    const colCands: Candidate[] = COLLECTIONS
      .filter(col => {
        if (selCats.length > 0 && !selCats.includes(col.categoryId)) return false;
        const colItems = ITEMS.filter(i => i.collectionId===col.id);
        if (colItems.length === 0) return false;
        if (statusF !== "all" && !colItems.some(i => i.status===statusF)) return false;
        return true;
      })
      .map(col => ({ type:"COLLECTION" as const, data: col }));

    return [...itemCands, ...colCands];
  }, [selCats, statusF, exclRecent]);

  const pool = buildPool();
  const standaloneCount   = pool.filter(c => c.type==="ITEM").length;
  const collectionCount   = pool.filter(c => c.type==="COLLECTION").length;

  const pick = (afterPick?: () => void) => {
    if (!pool.length) return;
    setSpin(true);
    setTimeout(() => {
      setResult(pool[Math.floor(Math.random() * pool.length)]);
      setSpin(false);
      afterPick?.();
    }, 700);
  };

  // Complete screen
  if (step === "complete" && result) {
    const name = result.type==="ITEM" ? result.data.title : result.data.name;
    const catId = result.type==="ITEM" ? result.data.categoryId : result.data.categoryId;
    return (
      <div className="max-w-md mx-auto px-4 py-12 text-center">
        <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-4">
          <CheckCircle size={30} className="text-emerald-600"/>
        </div>
        <h1 className="text-2xl font-bold text-foreground mb-2">오늘의 선택이 정해졌습니다.</h1>
        <p className="text-sm text-muted-foreground mb-7">추천 이력에 저장되었습니다.</p>
        <div className="bg-card border border-border rounded-2xl p-6 mb-6 flex flex-col items-center gap-4">
          <Poster title={name} categoryId={catId} size="lg"/>
          <div>
            <div className="flex justify-center flex-wrap gap-1.5 mb-1.5">
              <CategoryBadge categoryId={catId}/>
              {result.type==="COLLECTION" && <span className="text-[10px] bg-purple-100 text-purple-700 px-2 py-0.5 rounded flex items-center gap-1"><Layers size={9}/>Collection</span>}
            </div>
            <h2 className="text-xl font-bold text-foreground text-center">{name}</h2>
            {result.type==="ITEM" && <div className="mt-1.5 flex justify-center"><StatusBadge status={result.data.status}/></div>}
            {result.type==="COLLECTION" && (
              <p className="text-sm text-muted-foreground text-center mt-1">{result.data.itemCount}개 항목</p>
            )}
          </div>
        </div>
        {result.type==="COLLECTION" && (
          <div className="bg-card border border-border rounded-xl overflow-hidden mb-4">
            <div className="px-4 py-2 border-b border-border bg-muted/30 text-xs font-medium text-muted-foreground">Collection 내부 항목</div>
            {ITEMS.filter(i=>i.collectionId===result.data.id).map(ci=>(
              <div key={ci.id} className="flex items-center gap-2 px-4 py-2.5 border-b border-border last:border-0 text-sm">
                <Poster title={ci.title} categoryId={ci.categoryId} size="sm"/><span className="flex-1 truncate">{ci.title}</span>
                <StatusBadge status={ci.status} sm/>
              </div>
            ))}
          </div>
        )}
        <div className="space-y-2">
          <button className="w-full bg-primary text-white py-3 rounded-xl font-medium hover:bg-blue-700 transition-colors">완료 처리</button>
          <button className="w-full border border-border text-foreground py-3 rounded-xl font-medium hover:bg-muted transition-colors">상세보기</button>
          <button onClick={() => { setStep("setup"); setResult(null); }}
            className="w-full border border-border text-muted-foreground py-3 rounded-xl font-medium hover:bg-muted transition-colors">다시 추천</button>
        </div>
      </div>
    );
  }

  // Result screen
  if (step === "result" && result) {
    const isItem = result.type === "ITEM";
    const name   = isItem ? result.data.title : result.data.name;
    const catId  = isItem ? result.data.categoryId : result.data.categoryId;
    const colItems = !isItem ? ITEMS.filter(i => i.collectionId===result.data.id) : [];

    return (
      <div className="max-w-lg mx-auto px-4 py-6 pb-32 sm:pb-6">
        <button onClick={() => setStep("setup")} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5">
          <ChevronLeft size={16}/> 추천 설정
        </button>
        <h1 className="text-lg font-bold text-foreground mb-4">추천 결과</h1>

        <div className={`bg-card border-2 border-primary/20 rounded-2xl p-6 transition-all duration-300 mb-4 ${spinning?"opacity-40 scale-95":""}`}>
          <div className="text-center mb-4">
            <span className="text-xs font-semibold text-primary bg-blue-50 px-3 py-1 rounded-full">✨ PickNext 추천</span>
          </div>
          <div className="flex flex-col items-center gap-4">
            <Poster title={name} categoryId={catId} size="lg"/>
            <div className="text-center w-full">
              <div className="flex justify-center flex-wrap gap-1.5 mb-2">
                <CategoryBadge categoryId={catId}/>
                {!isItem && <span className="text-[10px] bg-purple-100 text-purple-700 px-2 py-0.5 rounded flex items-center gap-1"><Layers size={9}/>Collection</span>}
                {isItem && <StatusBadge status={result.data.status}/>}
              </div>
              <h2 className="text-2xl font-bold text-foreground mb-1">{name}</h2>
              {!isItem && <p className="text-sm text-muted-foreground">{result.data.itemCount}개 항목 · 예정 {result.data.plannedCount} · 완료 {result.data.completedCount}</p>}
              {isItem && result.data.releaseDate && <p className="text-xs text-muted-foreground">{result.data.releaseDate.slice(0,4)}년</p>}
              {isItem && result.data.progressNote && <p className="text-xs text-muted-foreground">진행: {result.data.progressNote}</p>}
              {isItem && result.data.rating && <div className="mt-1 flex justify-center"><StarRating rating={result.data.rating}/></div>}
            </div>
          </div>
        </div>

        {!isItem && (
          <div className="bg-card border border-border rounded-2xl overflow-hidden mb-4">
            <div className="px-4 py-2.5 border-b border-border bg-muted/30 flex items-center justify-between">
              <p className="text-xs font-medium text-foreground">내부 항목 목록</p>
              {statusF !== "all" && (
                <p className="text-[10px] text-primary">{statusF==="PLANNED"?"예정":"완료"} 항목 강조</p>
              )}
            </div>
            <div className="divide-y divide-border max-h-60 overflow-y-auto">
              {colItems.map(ci => {
                const isMatch = statusF==="all" || ci.status===statusF;
                return (
                  <div key={ci.id} className={`flex items-center gap-3 px-4 py-3 transition-opacity ${isMatch?"":"opacity-35"}`}>
                    <Poster title={ci.title} categoryId={ci.categoryId} size="sm"/>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-foreground truncate">{ci.title}</div>
                      {ci.progressNote && <p className="text-[10px] text-muted-foreground">{ci.progressNote}</p>}
                    </div>
                    <StatusBadge status={ci.status} sm/>
                    {ci.rating && <StarRating rating={ci.rating} sm/>}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Sticky action bar on mobile, normal on desktop */}
        <div className="fixed bottom-16 left-0 right-0 sm:static sm:bottom-auto px-4 sm:px-0 pb-2 sm:pb-0 bg-background sm:bg-transparent">
          <div className="flex flex-col gap-2.5">
            <button onClick={() => setConfirm(true)}
              className="w-full bg-primary text-white py-4 rounded-xl font-semibold hover:bg-blue-700 transition-colors">
              {isItem ? "이걸로 선택" : "이 Collection으로 선택"}
            </button>
            <div className="flex gap-2">
              <button onClick={() => pick()} disabled={spinning}
                className="flex-1 border border-border bg-card text-foreground py-3 rounded-xl font-medium hover:bg-muted transition-colors flex items-center justify-center gap-2 text-sm">
                <RefreshCw size={14} className={spinning?"animate-spin":""}/> {spinning?"추천 중...":"다시 추천"}
              </button>
              <button className="flex-1 border border-border text-muted-foreground py-3 rounded-xl font-medium hover:bg-muted transition-colors text-sm">
                {isItem ? "상세보기" : "Collection 상세보기"}
              </button>
            </div>
          </div>
        </div>

        {confirm && (
          <ConfirmModal
            title="선택을 확정하시겠습니까?"
            body="선택 결과가 추천 이력에 저장됩니다."
            confirmLabel="선택 확정"
            onConfirm={() => { setConfirm(false); setStep("complete"); showToast("추천 이력에 저장되었습니다."); }}
            onClose={() => setConfirm(false)}>
            <div className="bg-muted rounded-xl p-3 text-sm font-medium text-foreground">{name}</div>
          </ConfirmModal>
        )}
      </div>
    );
  }

  // Setup screen
  return (
    <div className="max-w-xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold text-foreground mb-6">랜덤 추천</h1>

      <div className="bg-card border border-border rounded-2xl p-5 mb-4">
        <h3 className="text-sm font-semibold text-foreground mb-3">상태 필터</h3>
        <div className="flex bg-muted rounded-xl p-0.5">
          {([["PLANNED","앞으로 볼 항목"],["COMPLETED","완료 항목"],["all","전체"]] as const).map(([v,l]) => (
            <button key={v} onClick={() => setStatusF(v)}
              className={`flex-1 py-2 rounded-lg text-xs font-medium transition-colors ${statusF===v?"bg-card shadow text-foreground":"text-muted-foreground hover:text-foreground"}`}>
              {l}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-card border border-border rounded-2xl p-5 mb-4">
        <h3 className="text-sm font-semibold text-foreground mb-3">
          카테고리 <span className="text-muted-foreground font-normal text-xs">(미선택 시 전체)</span>
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {CATEGORIES.map(cat => (
            <button key={cat.id} onClick={() => toggleCat(cat.id)}
              className={`flex items-center gap-2 p-2.5 rounded-xl border text-xs font-medium transition-colors ${selCats.includes(cat.id)?"border-primary bg-blue-50 text-blue-700":"border-border bg-background text-foreground hover:border-primary/30"}`}>
              <span style={{ color: cat.color }}>{cat.icon}</span>
              <span className="flex-1 text-left">{cat.name}</span>
              <span className="text-[10px] text-muted-foreground">{cat.planned}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="bg-card border border-border rounded-2xl p-5 mb-4">
        <h3 className="text-sm font-semibold text-foreground mb-3">추가 옵션</h3>
        <label className="flex items-center gap-3 cursor-pointer">
          <div className={`w-9 h-5 rounded-full relative transition-colors ${exclRecent?"bg-primary":"bg-gray-300"}`}
            onClick={() => setExcl(!exclRecent)}>
            <div className={`w-3.5 h-3.5 bg-white rounded-full absolute top-[3px] shadow transition-transform ${exclRecent?"translate-x-[18px]":"translate-x-[3px]"}`}/>
          </div>
          <span className="text-sm text-foreground">최근 선택 항목 제외</span>
        </label>
      </div>

      {/* Pool info box */}
      <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 mb-5 text-sm text-blue-700">
        <p className="font-semibold mb-1">현재 조건 후보: {pool.length}개</p>
        <div className="text-xs text-blue-600 space-y-0.5">
          <p>· 개별 항목: {standaloneCount}개</p>
          <p>· Collection: {collectionCount}개</p>
        </div>
        <div className="mt-2 pt-2 border-t border-blue-100 text-xs text-blue-500">
          <p>Collection에 항목이 여러 개 있어도 랜덤 추천에서는 하나의 후보로 계산됩니다.</p>
          <p className="mt-1 font-medium">예) 개별 항목 {standaloneCount}개 + Collection {collectionCount}개 = 총 후보 {pool.length}개</p>
        </div>
      </div>

      <button onClick={() => pick(() => setStep("result"))} disabled={pool.length===0 || spinning}
        className="w-full bg-primary text-white py-4 rounded-xl font-semibold hover:bg-blue-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2">
        {spinning ? <><RefreshCw size={18} className="animate-spin"/> 추천 중...</> : <><Shuffle size={18}/> 추천 결과 보기</>}
      </button>
      {pool.length===0 && <p className="text-center text-sm text-muted-foreground mt-3">선택한 조건에 맞는 항목이 없습니다.</p>}
    </div>
  );
}

// ─── Items Page ───────────────────────────────────────────────────────────────

function ItemsPage({
  showToast,
  openAddItem,
  openItemDetail,
  initialSnapshot,
  onSnapshotChange,
}: {
  showToast: (m: string) => void;
  openAddItem: () => void;
  openItemDetail: (itemId: string) => void;
  initialSnapshot?: ItemsPageStateSnapshot | null;
  onSnapshotChange?: (snapshot: ItemsPageStateSnapshot) => void;
}) {
  const [tableView, setTableV] = useState(
    () => (initialSnapshot?.viewMode ?? "card") === "table",
  );
  const viewModeRef = useRef<ItemsViewMode>(
    initialSnapshot?.viewMode ?? "card",
  );
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const onSnapshotChangeRef = useRef(onSnapshotChange);
  onSnapshotChangeRef.current = onSnapshotChange;

  const {
    categories,
    items,
    page,
    pageSize,
    total,
    totalPages,
    hasNext,
    hasPrevious,
    searchInput,
    appliedSearch,
    categoryId,
    status,
    sort,
    order,
    isItemsLoading,
    isCategoriesLoading,
    itemsError,
    categoriesError,
    setSearchInput,
    applySearchNow,
    setCategoryId,
    setStatus,
    setSortPair,
    setPage,
    setPageSize,
    resetFilters,
    reloadItems,
    reloadCategories,
  } = useItemsReadData({
    initialState: initialSnapshot,
    onQueryChange: (query: ItemsQuerySnapshot) => {
      onSnapshotChangeRef.current?.({
        ...query,
        viewMode: viewModeRef.current,
      });
    },
  });

  const setViewMode = (mode: ItemsViewMode) => {
    viewModeRef.current = mode;
    setTableV(mode === "table");
    onSnapshotChangeRef.current?.({
      searchInput,
      appliedSearch,
      categoryId,
      status,
      sort,
      order,
      page,
      pageSize,
      viewMode: mode,
    });
  };

  const listItems = items.map(mapApiItemToItemsListViewModel);
  const hasActiveFilters =
    Boolean(appliedSearch) ||
    categoryId !== null ||
    status !== "ALL" ||
    sort !== "updated_at" ||
    order !== "desc";

  const sortSelectValue =
    sort === "title" && order === "asc"
      ? "title"
      : sort === "rating" && order === "desc"
        ? "rating"
        : "updatedAt";

  const onSortChange = (value: string) => {
    if (value === "title") setSortPair("title", "asc");
    else if (value === "rating") setSortPair("rating", "desc");
    else setSortPair("updated_at", "desc");
  };

  // Clear selection when the visible page of results changes.
  useEffect(() => {
    setSelected(new Set());
  }, [page, pageSize, appliedSearch, categoryId, status, sort, order, items]);

  const toggleSelect = (id: string) =>
    setSelected(prev => { const s=new Set(prev); s.has(id)?s.delete(id):s.add(id); return s; });
  const toggleAll = () =>
    setSelected(prev => prev.size===listItems.length ? new Set() : new Set(listItems.map(i=>i.id)));

  const onItemActivate = (itemId: string) => {
    openItemDetail(itemId);
  };

  const onBulkAction = () => {
    showToast("일괄 작업 API는 아직 연결되지 않았습니다.");
  };

  const rangeStart = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const rangeEnd = Math.min(page * pageSize, total);

  const Card = ({ item }: { item: ReturnType<typeof mapApiItemToItemsListViewModel> }) => {
    const Icon = item.presentation.icon;
    return (
      <div className="bg-card border border-border rounded-2xl p-4 flex items-center gap-3 hover:border-primary/20 transition-colors cursor-pointer group"
        role="button"
        tabIndex={0}
        aria-label={`${item.title} 상세 보기`}
        onClick={() => onItemActivate(item.id)}
        onKeyDown={e => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onItemActivate(item.id);
          }
        }}>
        <input type="checkbox" checked={selected.has(item.id)}
          onClick={e => { e.stopPropagation(); toggleSelect(item.id); }}
          className="w-3.5 h-3.5 flex-shrink-0 cursor-pointer accent-primary"/>
        <div className="w-10 h-14 text-base rounded-lg flex items-center justify-center flex-shrink-0 text-white font-bold"
          style={{ backgroundColor: item.presentation.color }}>
          {item.title.charAt(0)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="font-medium text-foreground text-sm leading-snug truncate group-hover:text-primary transition-colors">{item.title}</div>
            <button onClick={e=>{ e.stopPropagation(); }} className="text-muted-foreground flex-shrink-0 hover:text-foreground">
              <MoreVertical size={14}/>
            </button>
          </div>
          <div className="flex flex-wrap gap-1 mt-1.5">
            <span className="inline-flex items-center gap-1 rounded font-medium text-[10px] px-1.5 py-px"
              style={{ backgroundColor: item.presentation.bgColor, color: item.presentation.color }}>
              <Icon size={10}/>{item.categoryName}
            </span>
            <StatusBadge status={item.status} sm/>
          </div>
          {item.collectionName && <div className="text-[10px] text-muted-foreground mt-1 flex items-center gap-0.5"><Layers size={9}/>{item.collectionName}</div>}
          {item.progressNote && <div className="text-[10px] text-muted-foreground">{item.progressNote}</div>}
          <div className="mt-1"><StarRating rating={displayItemRating(item.rating)} sm/></div>
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-xl font-bold text-foreground">전체 항목</h1>
        <button onClick={openAddItem}
          className="inline-flex items-center gap-1.5 bg-primary text-white px-4 py-2 rounded-xl text-sm font-medium hover:bg-blue-700 transition-colors">
          <Plus size={14}/> 신규 항목 추가
        </button>
      </div>

      {/* Bulk action bar — visual only; write APIs not connected */}
      {selected.size > 0 && (
        <div className="bg-primary/10 border border-primary/20 rounded-2xl px-4 py-3 mb-4 flex items-center gap-3 flex-wrap">
          <span className="text-sm font-medium text-primary">{selected.size}개 항목 선택됨</span>
          <div className="flex gap-2 ml-2">
            {["완료 처리","Category 이동","Collection 지정","삭제"].map(a => (
              <button key={a} onClick={onBulkAction}
                className={`text-xs px-3 py-1.5 rounded-lg border font-medium transition-colors ${a==="삭제"?"border-red-200 text-red-600 hover:bg-red-50":"border-border text-foreground hover:bg-muted"}`}>
                {a}
              </button>
            ))}
          </div>
          <button onClick={() => setSelected(new Set())} className="ml-auto text-muted-foreground hover:text-foreground">
            <X size={16}/>
          </button>
        </div>
      )}

      {/* Toolbar */}
      <div className="bg-card border border-border rounded-2xl p-4 mb-4 space-y-3">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"/>
            <input value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") applySearchNow(); }}
              placeholder="제목 검색"
              className="w-full pl-8 pr-3 py-2 border border-border rounded-xl text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/25"/>
          </div>
          <div className="hidden sm:flex gap-1">
            <button onClick={() => setViewMode("card")}
              className={`p-2 rounded-lg border transition-colors ${!tableView?"border-primary bg-blue-50 text-primary":"border-border text-muted-foreground hover:text-foreground"}`}>
              <AlignJustify size={15}/>
            </button>
            <button onClick={() => setViewMode("table")}
              className={`p-2 rounded-lg border transition-colors ${tableView?"border-primary bg-blue-50 text-primary":"border-border text-muted-foreground hover:text-foreground"}`}>
              <Grid size={15}/>
            </button>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {categoriesError && !isCategoriesLoading ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>카테고리를 불러오지 못했습니다.</span>
              <button onClick={reloadCategories}
                className="inline-flex items-center gap-1 text-xs bg-primary text-white px-2.5 py-1 rounded-lg hover:bg-blue-700 transition-colors font-medium">
                <RefreshCw size={11}/> 다시 시도
              </button>
            </div>
          ) : (
            <select
              value={categoryId ?? "all"}
              onChange={e => setCategoryId(e.target.value === "all" ? null : e.target.value)}
              disabled={isCategoriesLoading}
              className="text-xs border border-border rounded-lg px-3 py-1.5 bg-background focus:outline-none focus:ring-2 focus:ring-primary/25">
              <option value="all">전체 카테고리</option>
              {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          )}
          <select
            value={status === "ALL" ? "all" : status}
            onChange={e => {
              const v = e.target.value;
              setStatus(v === "all" ? "ALL" : (v as "PLANNED" | "COMPLETED"));
            }}
            className="text-xs border border-border rounded-lg px-3 py-1.5 bg-background focus:outline-none focus:ring-2 focus:ring-primary/25">
            <option value="all">전체 상태</option><option value="PLANNED">예정</option><option value="COMPLETED">완료</option>
          </select>
          <select value={sortSelectValue} onChange={e => onSortChange(e.target.value)}
            className="text-xs border border-border rounded-lg px-3 py-1.5 bg-background focus:outline-none focus:ring-2 focus:ring-primary/25">
            <option value="updatedAt">최근 수정순</option><option value="title">제목순</option><option value="rating">평점 높은 순</option>
          </select>
          <select value={pageSize} onChange={e => setPageSize(Number(e.target.value))}
            className="text-xs border border-border rounded-lg px-3 py-1.5 bg-background focus:outline-none focus:ring-2 focus:ring-primary/25">
            <option value={25}>25개씩</option><option value={50}>50개씩</option><option value={100}>100개씩</option>
          </select>
        </div>
      </div>

      <p className="text-xs text-muted-foreground mb-3">
        {isItemsLoading && items.length === 0
          ? "불러오는 중…"
          : `${total.toLocaleString("ko-KR")}건 · ${page}/${Math.max(totalPages, 1)} 페이지`}
      </p>

      {itemsError && !isItemsLoading ? (
        <div className="bg-card border border-border rounded-2xl p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
          <p className="text-sm text-muted-foreground">항목 목록을 불러오지 못했습니다.</p>
          <button onClick={reloadItems}
            className="inline-flex items-center justify-center gap-1.5 text-xs bg-primary text-white px-3 py-1.5 rounded-xl hover:bg-blue-700 transition-colors font-medium self-start sm:self-auto">
            <RefreshCw size={12}/> 다시 시도
          </button>
        </div>
      ) : isItemsLoading && items.length === 0 ? (
        <>
          {tableView && (
            <div className="hidden sm:block bg-card border border-border rounded-2xl overflow-hidden mb-4">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40">
                    <th className="px-3 py-3 w-8"/>
                    {["","제목","카테고리","Collection","상태","평점","Progress Note","수정일",""].map((h,i) => (
                      <th key={i} className="text-left px-3 py-3 text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="border-b border-border">
                      <td className="px-3 py-3" colSpan={10}>
                        <div className="h-10 animate-pulse rounded bg-muted"/>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className={tableView?"sm:hidden space-y-2":"space-y-2"}>
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-card border border-border rounded-2xl p-4 flex items-center gap-3">
                <div className="w-3.5 h-3.5 rounded animate-pulse bg-muted flex-shrink-0"/>
                <div className="w-10 h-14 rounded-lg animate-pulse bg-muted flex-shrink-0"/>
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-2/3 animate-pulse rounded bg-muted"/>
                  <div className="h-3 w-1/3 animate-pulse rounded bg-muted"/>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : listItems.length === 0 ? (
        <div className="bg-card border border-border rounded-2xl text-center py-16">
          <Search size={28} className="text-muted-foreground mx-auto mb-3"/>
          <p className="font-medium text-foreground">
            {hasActiveFilters ? "조건에 맞는 항목이 없습니다." : "등록된 항목이 없습니다."}
          </p>
          <p className="text-sm text-muted-foreground mt-1">
            {hasActiveFilters ? "다른 검색어 또는 필터를 시도해 보세요" : "신규 항목을 추가해 보세요"}
          </p>
          {hasActiveFilters && (
            <button onClick={resetFilters}
              className="mt-4 inline-flex items-center gap-1.5 text-xs bg-primary text-white px-3 py-1.5 rounded-xl hover:bg-blue-700 transition-colors font-medium">
              필터 초기화
            </button>
          )}
        </div>
      ) : (
        <>
          {/* Desktop table */}
          {tableView && (
            <div className="hidden sm:block bg-card border border-border rounded-2xl overflow-hidden mb-4 relative">
              {isItemsLoading && (
                <div className="absolute inset-0 bg-card/40 pointer-events-none z-10"/>
              )}
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40">
                    <th className="px-3 py-3 w-8">
                      <input type="checkbox" onChange={toggleAll} checked={selected.size===listItems.length&&listItems.length>0} className="accent-primary"/>
                    </th>
                    {["","제목","카테고리","Collection","상태","평점","Progress Note","수정일",""].map((h,i) => (
                      <th key={i} className="text-left px-3 py-3 text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {listItems.map((item,i) => {
                    const Icon = item.presentation.icon;
                    return (
                      <tr key={item.id}
                        onClick={() => onItemActivate(item.id)}
                        onKeyDown={e => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            onItemActivate(item.id);
                          }
                        }}
                        tabIndex={0}
                        aria-label={`${item.title} 상세 보기`}
                        className={`border-b border-border hover:bg-muted/20 transition-colors cursor-pointer ${i%2===1?"bg-muted/5":""} ${selected.has(item.id)?"bg-blue-50/50":""}`}>
                        <td className="px-3 py-3" onClick={e=>e.stopPropagation()}>
                          <input type="checkbox" checked={selected.has(item.id)} onChange={()=>toggleSelect(item.id)} className="accent-primary"/>
                        </td>
                        <td className="px-3 py-3 w-12">
                          <div className="w-10 h-14 text-base rounded-lg flex items-center justify-center flex-shrink-0 text-white font-bold"
                            style={{ backgroundColor: item.presentation.color }}>
                            {item.title.charAt(0)}
                          </div>
                        </td>
                        <td className="px-3 py-3 font-medium text-foreground max-w-xs">
                          <div className="truncate">{item.title}</div>
                        </td>
                        <td className="px-3 py-3">
                          <span className="inline-flex items-center gap-1 rounded font-medium text-[10px] px-1.5 py-px"
                            style={{ backgroundColor: item.presentation.bgColor, color: item.presentation.color }}>
                            <Icon size={10}/>{item.categoryName}
                          </span>
                        </td>
                        <td className="px-3 py-3 text-xs text-muted-foreground">{item.collectionName || "—"}</td>
                        <td className="px-3 py-3"><StatusBadge status={item.status} sm/></td>
                        <td className="px-3 py-3"><StarRating rating={displayItemRating(item.rating)} sm/></td>
                        <td className="px-3 py-3 text-xs text-muted-foreground max-w-[120px] truncate">{item.progressNote||"—"}</td>
                        <td className="px-3 py-3 text-xs text-muted-foreground whitespace-nowrap">{formatDate(item.updatedAt) || "—"}</td>
                        <td className="px-3 py-3" onClick={e=>e.stopPropagation()}>
                          <button className="text-muted-foreground hover:text-foreground"><MoreVertical size={14}/></button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Card list */}
          <div className={`relative ${tableView?"sm:hidden space-y-2":"space-y-2"}`}>
            {isItemsLoading && (
              <div className="absolute inset-0 bg-background/30 pointer-events-none z-10 rounded-2xl"/>
            )}
            {listItems.map(item => <Card key={item.id} item={item}/>)}
          </div>
        </>
      )}

      {/* Pagination */}
      {!itemsError && totalPages > 1 && (
        <div className="flex items-center justify-between mt-5">
          <p className="text-xs text-muted-foreground">
            {rangeStart}–{rangeEnd} / {total.toLocaleString("ko-KR")}건
          </p>
          <div className="flex items-center gap-1">
            <button onClick={() => setPage(1)} disabled={!hasPrevious}
              className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors">
              <ChevronsLeft size={14}/>
            </button>
            <button onClick={() => setPage(page - 1)} disabled={!hasPrevious}
              className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors">
              <ChevronLeft size={14}/>
            </button>
            {Array.from({length:Math.min(5,totalPages)},(_,i) => {
              const p = Math.min(Math.max(page-2,1)+i, totalPages);
              return (
                <button key={`${p}-${i}`} onClick={() => setPage(p)}
                  className={`w-7 h-7 rounded-lg text-xs font-medium border transition-colors ${page===p?"border-primary bg-primary text-white":"border-border text-foreground hover:bg-muted"}`}>
                  {p}
                </button>
              );
            })}
            <button onClick={() => setPage(page + 1)} disabled={!hasNext}
              className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors">
              <ChevronRight size={14}/>
            </button>
            <button onClick={() => setPage(totalPages)} disabled={!hasNext}
              className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors">
              <ChevronsRight size={14}/>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Collections Page ─────────────────────────────────────────────────────────

interface CollectionDetailSelection {
  collectionId: string;
  itemsPage: number;
}

function CollectionCategoryBadges({
  categories,
  sm,
}: {
  categories: CollectionListItemViewModel["categories"];
  sm?: boolean;
}) {
  if (categories.length === 0) {
    return (
      <span className={`inline-flex items-center rounded font-medium text-muted-foreground bg-muted ${sm?"text-[10px] px-1.5 py-px":"text-xs px-2 py-0.5"}`}>
        카테고리 없음
      </span>
    );
  }
  return (
    <div className="flex flex-wrap gap-1">
      {categories.map((category) => {
        const Icon = category.presentation.icon;
        return (
          <span
            key={category.id}
            title={`${category.name} ${category.itemCount}개`}
            className={`inline-flex items-center gap-1 rounded font-medium ${sm?"text-[10px] px-1.5 py-px":"text-xs px-2 py-0.5"}`}
            style={{
              backgroundColor: category.presentation.bgColor,
              color: category.presentation.color,
            }}
          >
            <Icon size={sm ? 10 : 12}/>{category.name}
          </span>
        );
      })}
    </div>
  );
}

function CollectionsPage({
  showToast,
  initialSnapshot,
  onSnapshotChange,
  selection,
  onSelectionChange,
  openItemDetail,
}: {
  showToast: (m: string) => void;
  initialSnapshot?: CollectionsQuerySnapshot | null;
  onSnapshotChange?: (snapshot: CollectionsQuerySnapshot) => void;
  selection: CollectionDetailSelection | null;
  onSelectionChange: (selection: CollectionDetailSelection | null) => void;
  openItemDetail: (
    itemId: string,
    context: { collectionId: string; collectionItemsPage: number },
  ) => void;
}) {
  const onSnapshotChangeRef = useRef(onSnapshotChange);
  onSnapshotChangeRef.current = onSnapshotChange;

  const {
    collections,
    page,
    pageSize,
    total,
    totalPages,
    hasNext,
    hasPrevious,
    searchInput,
    appliedSearch,
    isLoading,
    error,
    setSearchInput,
    applySearchNow,
    clearSearch,
    setPage,
    reload,
  } = useCollectionsReadData({
    initialState: initialSnapshot,
    onQueryChange: (query) => {
      onSnapshotChangeRef.current?.(query);
    },
  });

  const listItems = useMemo(
    () => collections.map(mapApiCollectionToListItem),
    [collections],
  );

  const rangeStart = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const rangeEnd = Math.min(page * pageSize, total);

  if (selection) {
    return (
      <CollectionDetailInline
        collectionId={selection.collectionId}
        itemsPage={selection.itemsPage}
        onItemsPageChange={(itemsPage) =>
          onSelectionChange({ collectionId: selection.collectionId, itemsPage })
        }
        onBack={() => onSelectionChange(null)}
        openItemDetail={openItemDetail}
        showToast={showToast}
      />
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6">
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-xl font-bold text-foreground">Collection</h1>
        <button
          type="button"
          onClick={() => showToast("Collection 추가 API는 아직 연결되지 않았습니다.")}
          className="inline-flex items-center gap-1.5 bg-primary text-white px-4 py-2 rounded-xl text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          <Plus size={14}/> 추가
        </button>
      </div>
      <div className="relative mb-4">
        <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"/>
        <input
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") applySearchNow();
          }}
          placeholder="Collection 이름 검색"
          aria-label="Collection 이름 검색"
          className="w-full pl-8 pr-4 py-2 border border-border rounded-xl text-sm bg-card focus:outline-none focus:ring-2 focus:ring-primary/25"
        />
      </div>

      {error ? (
        <div className="bg-card border border-border rounded-2xl p-8 text-center">
          <p className="text-sm text-foreground mb-1">Collection 목록을 불러오지 못했습니다.</p>
          <p className="text-xs text-muted-foreground mb-4">잠시 후 다시 시도해 주세요.</p>
          <button
            type="button"
            onClick={() => void reload()}
            className="inline-flex items-center gap-1.5 text-sm text-primary border border-primary/25 px-4 py-2 rounded-xl hover:bg-blue-50 transition-colors"
          >
            <RefreshCw size={14}/> 다시 시도
          </button>
        </div>
      ) : isLoading && listItems.length === 0 ? (
        <div className="bg-card border border-border rounded-2xl py-16 text-center text-sm text-muted-foreground">
          Collection을 불러오는 중…
        </div>
      ) : total === 0 ? (
        <div className="bg-card border border-border rounded-2xl p-8 text-center">
          {appliedSearch ? (
            <>
              <p className="text-sm text-foreground mb-1">검색 결과가 없습니다.</p>
              <p className="text-xs text-muted-foreground mb-4">다른 Collection 이름으로 검색해 보세요.</p>
              <button
                type="button"
                onClick={clearSearch}
                className="text-sm text-primary hover:underline"
              >
                검색어 지우기
              </button>
            </>
          ) : (
            <>
              <p className="text-sm text-foreground mb-1">등록된 Collection이 없습니다.</p>
              <p className="text-xs text-muted-foreground">Collection 추가는 이후 단계에서 연결됩니다.</p>
            </>
          )}
        </div>
      ) : (
        <>
          <p className="text-xs text-muted-foreground mb-4">
            {total.toLocaleString("ko-KR")}개
            {appliedSearch ? ` · “${appliedSearch}” 검색` : ""}
            {isLoading ? " · 갱신 중…" : ""}
          </p>
          <div className={`relative grid sm:grid-cols-2 gap-4 ${isLoading ? "opacity-70" : ""}`}>
            {listItems.map((col) => (
              <button
                key={col.id}
                type="button"
                onClick={() =>
                  onSelectionChange({ collectionId: col.id, itemsPage: 1 })
                }
                className="bg-card border border-border rounded-2xl p-5 text-left hover:border-primary/30 hover:shadow-sm transition-all"
              >
                <div className="flex items-start justify-between mb-2 gap-2">
                  <div className="min-w-0">
                    <CollectionCategoryBadges categories={col.categories} sm/>
                    <h3 className="font-semibold text-foreground mt-2 text-sm truncate">{col.name}</h3>
                  </div>
                  <ChevronRight size={15} className="text-muted-foreground mt-1 flex-shrink-0"/>
                </div>
                <p className="text-xs text-muted-foreground mb-3">
                  {col.itemCount}개 · 예정 {col.plannedCount} · 완료 {col.completedCount}
                </p>
                <ProgressBar value={col.progressPercent} className="mb-1.5"/>
                <div className="flex justify-between text-[10px] text-muted-foreground">
                  <span>진행률 {col.progressPercent}%</span>
                  <span className="flex items-center gap-0.5">
                    <Star size={9} className="text-muted-foreground"/>—
                  </span>
                </div>
              </button>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-5">
              <p className="text-xs text-muted-foreground">
                {rangeStart}–{rangeEnd} / {total.toLocaleString("ko-KR")}개
                {totalPages > 0 ? ` · ${page}/${totalPages}페이지` : ""}
              </p>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setPage(1)}
                  disabled={!hasPrevious}
                  aria-label="첫 페이지"
                  className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
                >
                  <ChevronsLeft size={14}/>
                </button>
                <button
                  type="button"
                  onClick={() => setPage(page - 1)}
                  disabled={!hasPrevious}
                  aria-label="이전 페이지"
                  className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
                >
                  <ChevronLeft size={14}/>
                </button>
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  const p = Math.min(Math.max(page - 2, 1) + i, totalPages);
                  return (
                    <button
                      key={`${p}-${i}`}
                      type="button"
                      onClick={() => setPage(p)}
                      aria-label={`${p}페이지`}
                      aria-current={page === p ? "page" : undefined}
                      className={`w-7 h-7 rounded-lg text-xs font-medium border transition-colors ${page === p ? "border-primary bg-primary text-white" : "border-border text-foreground hover:bg-muted"}`}
                    >
                      {p}
                    </button>
                  );
                })}
                <button
                  type="button"
                  onClick={() => setPage(page + 1)}
                  disabled={!hasNext}
                  aria-label="다음 페이지"
                  className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
                >
                  <ChevronRight size={14}/>
                </button>
                <button
                  type="button"
                  onClick={() => setPage(totalPages)}
                  disabled={!hasNext}
                  aria-label="마지막 페이지"
                  className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
                >
                  <ChevronsRight size={14}/>
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function CollectionDetailInline({
  collectionId,
  itemsPage,
  onItemsPageChange,
  onBack,
  openItemDetail,
  showToast,
}: {
  collectionId: string;
  itemsPage: number;
  onItemsPageChange: (page: number) => void;
  onBack: () => void;
  openItemDetail: (
    itemId: string,
    context: { collectionId: string; collectionItemsPage: number },
  ) => void;
  showToast: (m: string) => void;
}) {
  const {
    collection,
    isLoading: isDetailLoading,
    error: detailError,
    isNotFound,
    reload: reloadDetail,
  } = useCollectionDetail(collectionId);

  const detailReady = Boolean(collection) && !detailError;
  const {
    items,
    page,
    pageSize,
    total,
    totalPages,
    hasNext,
    hasPrevious,
    isLoading: isItemsLoading,
    error: itemsError,
    setPage,
    reload: reloadItems,
  } = useCollectionItemsReadData(collectionId, {
    enabled: detailReady,
    page: itemsPage,
    onPageChange: onItemsPageChange,
  });

  const detailVm = useMemo(
    () => (collection ? mapApiCollectionToDetail(collection) : null),
    [collection],
  );
  const listItems = useMemo(
    () => items.map(mapApiItemToItemsListViewModel),
    [items],
  );

  const rangeStart = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const rangeEnd = Math.min(page * pageSize, total);

  if (isDetailLoading && !detailVm) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6">
        <button
          type="button"
          onClick={onBack}
          aria-label="Collection 목록으로"
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5"
        >
          <ChevronLeft size={16}/> Collection 목록
        </button>
        <div className="bg-card border border-border rounded-2xl p-6 mb-5 space-y-3">
          <div className="h-4 w-32 animate-pulse rounded bg-muted"/>
          <div className="h-8 w-2/3 animate-pulse rounded bg-muted"/>
          <div className="h-3 w-full animate-pulse rounded bg-muted"/>
        </div>
        <div className="bg-card border border-border rounded-2xl py-12 text-center text-sm text-muted-foreground">
          Collection을 불러오는 중…
        </div>
      </div>
    );
  }

  if (detailError || !detailVm) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6">
        <button
          type="button"
          onClick={onBack}
          aria-label="Collection 목록으로"
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5"
        >
          <ChevronLeft size={16}/> Collection 목록
        </button>
        <div className="bg-card border border-border rounded-2xl p-8 text-center">
          <p className="font-medium text-foreground mb-2">
            {isNotFound
              ? "Collection을 찾을 수 없습니다."
              : "Collection 정보를 불러오지 못했습니다."}
          </p>
          {isNotFound && (
            <p className="text-sm text-muted-foreground mb-5">
              삭제되었거나 접근할 수 없는 Collection입니다.
            </p>
          )}
          <div className="flex flex-wrap gap-2 justify-center">
            {!isNotFound && (
              <button
                type="button"
                onClick={() => void reloadDetail()}
                className="inline-flex items-center gap-1.5 text-sm bg-primary text-white px-4 py-2 rounded-xl hover:bg-blue-700 transition-colors font-medium"
              >
                <RefreshCw size={14}/> 다시 시도
              </button>
            )}
            <button
              type="button"
              onClick={onBack}
              className="inline-flex items-center gap-1.5 text-sm border border-border text-foreground px-4 py-2 rounded-xl hover:bg-muted transition-colors font-medium"
            >
              목록으로 돌아가기
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6">
      <button
        type="button"
        onClick={onBack}
        aria-label="Collection 목록으로"
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5"
      >
        <ChevronLeft size={16}/> Collection 목록
      </button>

      <div className="bg-card border border-border rounded-2xl p-6 mb-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <CollectionCategoryBadges categories={detailVm.categories}/>
              <span className="text-[10px] bg-purple-100 text-purple-700 px-2 py-px rounded">Collection</span>
            </div>
            <h1 className="text-2xl font-bold text-foreground break-words">{detailVm.name}</h1>
            <p className="text-sm text-muted-foreground mt-0.5">{detailVm.itemCount}개 항목</p>
          </div>
          <div className="flex gap-2 flex-shrink-0">
            <button
              type="button"
              onClick={() => showToast("추천 API는 아직 연결되지 않았습니다.")}
              className="p-2 border border-border rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              title="이 Collection에서 추천"
            >
              <Shuffle size={15}/>
            </button>
            <button
              type="button"
              onClick={() => showToast("Collection 수정 API는 아직 연결되지 않았습니다.")}
              className="p-2 border border-border rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              title="수정"
            >
              <Edit2 size={15}/>
            </button>
            <button
              type="button"
              onClick={() => showToast("Collection 삭제 API는 아직 연결되지 않았습니다.")}
              className="p-2 border border-red-200 rounded-xl text-red-500 hover:bg-red-50 transition-colors"
              title="삭제"
            >
              <Trash2 size={15}/>
            </button>
          </div>
        </div>
        <div className="mt-4">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-muted-foreground">진행률</span>
            <span className="font-semibold">{detailVm.progressPercent}%</span>
          </div>
          <ProgressBar value={detailVm.progressPercent}/>
          <div className="flex gap-4 mt-2 text-xs">
            <span className="text-blue-600">예정 {detailVm.plannedCount}</span>
            <span className="text-emerald-600">완료 {detailVm.completedCount}</span>
            <span className="flex items-center gap-0.5 text-muted-foreground">
              <Star size={10}/>—
            </span>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-foreground">항목 목록</h2>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => showToast("TMDB 연동은 아직 연결되지 않았습니다.")}
            className="text-xs text-primary border border-primary/25 px-3 py-1.5 rounded-lg hover:bg-blue-50 transition-colors flex items-center gap-1"
          >
            <Search size={12}/> TMDB 검색 후 추가
          </button>
          <button
            type="button"
            onClick={() => showToast("Item 추가 API는 아직 연결되지 않았습니다.")}
            className="text-xs text-primary border border-primary/25 px-3 py-1.5 rounded-lg hover:bg-blue-50 transition-colors flex items-center gap-1"
          >
            <Plus size={12}/> 직접 추가
          </button>
        </div>
      </div>

      {itemsError ? (
        <div className="bg-card border border-border rounded-2xl p-8 text-center">
          <p className="text-sm text-foreground mb-1">소속 Item을 불러오지 못했습니다.</p>
          <p className="text-xs text-muted-foreground mb-4">Collection 정보는 유지됩니다.</p>
          <button
            type="button"
            onClick={() => void reloadItems()}
            className="inline-flex items-center gap-1.5 text-sm text-primary border border-primary/25 px-4 py-2 rounded-xl hover:bg-blue-50 transition-colors"
          >
            <RefreshCw size={14}/> 다시 시도
          </button>
        </div>
      ) : isItemsLoading && listItems.length === 0 ? (
        <div className="bg-card border border-border rounded-2xl py-10 text-center text-sm text-muted-foreground">
          항목을 불러오는 중…
        </div>
      ) : total === 0 ? (
        <div className="bg-card border border-border rounded-2xl py-10 text-center text-sm text-muted-foreground">
          이 Collection에 등록된 항목이 없습니다.
        </div>
      ) : (
        <>
          <div className={`space-y-2 ${isItemsLoading ? "opacity-70" : ""}`}>
            {listItems.map((item) => {
              const Icon = item.presentation.icon;
              return (
                <div
                  key={item.id}
                  role="button"
                  tabIndex={0}
                  aria-label={`${item.title} 상세 보기`}
                  onClick={() =>
                    openItemDetail(item.id, {
                      collectionId,
                      collectionItemsPage: page,
                    })
                  }
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      openItemDetail(item.id, {
                        collectionId,
                        collectionItemsPage: page,
                      });
                    }
                  }}
                  className="bg-card border border-border rounded-xl p-4 flex items-center gap-3 hover:border-primary/20 transition-colors cursor-pointer"
                >
                  <div
                    className="w-10 h-14 text-base rounded-lg flex items-center justify-center flex-shrink-0 text-white font-bold"
                    style={{ backgroundColor: item.presentation.color }}
                  >
                    {item.title.charAt(0)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-foreground text-sm truncate">{item.title}</div>
                    <div className="flex flex-wrap items-center gap-1.5 mt-1">
                      <span
                        className="inline-flex items-center gap-1 rounded font-medium text-[10px] px-1.5 py-px"
                        style={{
                          backgroundColor: item.presentation.bgColor,
                          color: item.presentation.color,
                        }}
                      >
                        <Icon size={10}/>{item.categoryName}
                      </span>
                      <StatusBadge status={item.status} sm/>
                      {item.progressNote && (
                        <span className="text-[10px] text-muted-foreground truncate max-w-[140px]">
                          {item.progressNote}
                        </span>
                      )}
                    </div>
                    <div className="mt-0.5">
                      <StarRating rating={displayItemRating(item.rating)} sm/>
                    </div>
                  </div>
                  <div className="flex gap-1.5 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      onClick={() => showToast("상태 변경 기능은 다음 단계에서 제공됩니다.")}
                      className="text-[10px] border border-emerald-200 text-emerald-700 px-2 py-1 rounded-lg hover:bg-emerald-50 transition-colors"
                    >
                      완료
                    </button>
                    <button
                      type="button"
                      onClick={() => showToast("Collection에서 제거는 다음 단계에서 제공됩니다.")}
                      className="text-[10px] border border-border text-muted-foreground px-2 py-1 rounded-lg hover:bg-muted transition-colors"
                    >
                      제거
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-5">
              <p className="text-xs text-muted-foreground">
                {rangeStart}–{rangeEnd} / {total.toLocaleString("ko-KR")}건
                {totalPages > 0 ? ` · ${page}/${totalPages}페이지` : ""}
              </p>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setPage(1)}
                  disabled={!hasPrevious}
                  aria-label="첫 페이지"
                  className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
                >
                  <ChevronsLeft size={14}/>
                </button>
                <button
                  type="button"
                  onClick={() => setPage(page - 1)}
                  disabled={!hasPrevious}
                  aria-label="이전 페이지"
                  className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
                >
                  <ChevronLeft size={14}/>
                </button>
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  const p = Math.min(Math.max(page - 2, 1) + i, totalPages);
                  return (
                    <button
                      key={`${p}-${i}`}
                      type="button"
                      onClick={() => setPage(p)}
                      aria-label={`${p}페이지`}
                      aria-current={page === p ? "page" : undefined}
                      className={`w-7 h-7 rounded-lg text-xs font-medium border transition-colors ${page === p ? "border-primary bg-primary text-white" : "border-border text-foreground hover:bg-muted"}`}
                    >
                      {p}
                    </button>
                  );
                })}
                <button
                  type="button"
                  onClick={() => setPage(page + 1)}
                  disabled={!hasNext}
                  aria-label="다음 페이지"
                  className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
                >
                  <ChevronRight size={14}/>
                </button>
                <button
                  type="button"
                  onClick={() => setPage(totalPages)}
                  disabled={!hasNext}
                  aria-label="마지막 페이지"
                  className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
                >
                  <ChevronsRight size={14}/>
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ─── History Page ─────────────────────────────────────────────────────────────

function HistoryPage({ navigateToHistory }: { navigateToHistory: (h: HistoryEntry) => void }) {
  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6">
      <h1 className="text-xl font-bold text-foreground mb-5">추천 이력</h1>
      <div className="space-y-3">
        {HISTORY.map(h => (
          <div key={h.id} className="bg-card border border-border rounded-2xl p-4 flex items-center gap-4 hover:border-primary/20 transition-colors">
            <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center flex-shrink-0">
              {h.type==="COLLECTION" ? <Layers size={17} className="text-blue-600"/> : <Shuffle size={17} className="text-blue-600"/>}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-0.5">
                <CategoryBadge categoryId={h.categoryId} sm/>
                <span className={`text-[10px] px-1.5 py-px rounded font-medium ${h.type==="ITEM"?"bg-blue-100 text-blue-700":"bg-purple-100 text-purple-700"}`}>
                  {h.type==="ITEM"?"단일 항목":"Collection"}
                </span>
              </div>
              <div className="font-medium text-foreground text-sm">{h.title}</div>
              <div className="text-xs text-muted-foreground mt-0.5">{h.selectedAt}</div>
            </div>
            <div className="flex flex-col items-end gap-2">
              <StatusBadge status={h.currentStatus} sm/>
              {h.statusAtTime !== h.currentStatus && (
                <span className="text-[10px] text-amber-600">상태 변경됨</span>
              )}
              <button onClick={() => navigateToHistory(h)} className="text-[10px] text-primary hover:underline">상세보기</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Data Page (with import flow) ────────────────────────────────────────────


function DataPage() {
  const [importStep, setImportStep] = useState<ImportStep>("select");
  const [confirmText, setConfirmText] = useState("");
  const [fileSelected, setFileSelected] = useState(false);
  const total = CATEGORIES.reduce((s,c)=>s+c.total,0);

  if (importStep !== "select") {
    return (
      <div className="max-w-xl mx-auto px-4 sm:px-6 py-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-bold text-foreground">데이터 가져오기</h1>
          <button onClick={() => { setImportStep("select"); setFileSelected(false); setConfirmText(""); }}
            className="text-sm text-muted-foreground hover:text-foreground">취소</button>
        </div>
        {/* Step indicator */}
        <div className="flex items-center mb-6">
          {(["파일 선택","검증","미리보기","복원 확인","완료"] as const).map((label, i) => {
            const steps: ImportStep[] = ["select","validate","preview","confirm","result"];
            const idx = steps.indexOf(importStep);
            const done = i < idx; const active = i === idx;
            return (
              <div key={label} className="flex items-center flex-1">
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${done?"bg-emerald-500 text-white":active?"bg-primary text-white":"bg-muted text-muted-foreground"}`}>
                  {done ? <Check size={12}/> : i+1}
                </div>
                {i < 4 && <div className={`flex-1 h-px mx-1 ${done?"bg-emerald-400":"bg-border"}`}/>}
              </div>
            );
          })}
        </div>

        {importStep === "validate" && (
          <div className="space-y-4">
            <div className="bg-card border border-border rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-4">
                <FileText size={20} className="text-primary"/>
                <div>
                  <p className="font-semibold text-foreground text-sm">{MOCK_FILE.filename}</p>
                  <p className="text-xs text-muted-foreground">{MOCK_FILE.size}</p>
                </div>
                <div className="ml-auto flex items-center gap-1.5 text-emerald-600 text-sm font-medium">
                  <CheckCircle size={16}/> 검증 완료
                </div>
              </div>
              <div className="space-y-2 text-sm">
                {[["내보내기 일시",MOCK_FILE.exportedAt],["App Version",MOCK_FILE.appVersion],["Schema Version",MOCK_FILE.schemaVersion],["사용자",MOCK_FILE.user]].map(([k,v]) => (
                  <div key={k} className="flex justify-between"><span className="text-muted-foreground">{k}</span><span>{v}</span></div>
                ))}
              </div>
            </div>
            <button onClick={() => setImportStep("preview")}
              className="w-full bg-primary text-white py-3 rounded-xl font-medium hover:bg-blue-700 transition-colors">
              포함 데이터 확인 →
            </button>
          </div>
        )}

        {importStep === "preview" && (
          <div className="space-y-4">
            <div className="bg-card border border-border rounded-2xl p-5">
              <h3 className="font-semibold text-foreground mb-3">포함 데이터</h3>
              <div className="space-y-2 text-sm">
                {[["Category",`${MOCK_FILE.categories}개`],["Collection",`${MOCK_FILE.collections}개`],["전체 항목",`${MOCK_FILE.items.toLocaleString()}건`],["추천 이력",`${MOCK_FILE.history}건`]].map(([k,v]) => (
                  <div key={k} className="flex justify-between py-1.5 border-b border-border last:border-0">
                    <span className="text-muted-foreground">{k}</span><span className="font-medium">{v}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="bg-muted/50 rounded-xl p-4 text-xs text-muted-foreground space-y-1">
              <p className="font-medium text-foreground">복원 방식: 전체 교체 (RESTORE)</p>
              <p>· 현재 데이터가 모두 백업 파일의 데이터로 교체됩니다.</p>
              <p>· MERGE(병합)는 추후 제공 예정입니다.</p>
            </div>
            <button onClick={() => setImportStep("confirm")}
              className="w-full bg-primary text-white py-3 rounded-xl font-medium hover:bg-blue-700 transition-colors">
              복원 경고 확인 →
            </button>
          </div>
        )}

        {importStep === "confirm" && (
          <div className="space-y-4">
            <div className="bg-red-50 border border-red-200 rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <ShieldAlert size={20} className="text-red-600"/>
                <h3 className="font-bold text-red-700">전체 복원 경고</h3>
              </div>
              <p className="text-sm text-red-700 mb-1">전체 복원은 현재 데이터를 백업 파일의 상태로 교체합니다.</p>
              <p className="text-sm text-red-700 font-semibold">이 작업은 되돌릴 수 없습니다.</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1.5">
                복원을 진행하려면 <code className="bg-muted px-1 py-0.5 rounded text-primary font-mono">RESTORE</code>를 입력하세요.
              </label>
              <input value={confirmText} onChange={e=>setConfirmText(e.target.value)}
                placeholder="RESTORE"
                className="w-full px-3 py-2.5 border border-border rounded-xl text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/25 font-mono"/>
            </div>
            <div className="flex gap-3">
              <button onClick={() => setImportStep("preview")}
                className="flex-1 border border-border text-foreground py-3 rounded-xl font-medium hover:bg-muted transition-colors text-sm">이전</button>
              <button onClick={() => setImportStep("result")} disabled={confirmText!=="RESTORE"}
                className="flex-1 bg-red-500 text-white py-3 rounded-xl font-semibold hover:bg-red-600 transition-colors text-sm disabled:opacity-40 disabled:cursor-not-allowed">
                전체 복원
              </button>
            </div>
            <button className="w-full border border-muted text-muted-foreground py-2.5 rounded-xl text-sm cursor-not-allowed flex items-center justify-center gap-2">
              <Lock size={13}/> MERGE — 추후 제공 예정
            </button>
          </div>
        )}

        {importStep === "result" && (
          <div className="text-center py-8">
            <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-4">
              <CheckCircle size={30} className="text-emerald-600"/>
            </div>
            <h2 className="text-xl font-bold text-foreground mb-2">복원이 완료되었습니다.</h2>
            <p className="text-sm text-muted-foreground mb-6">{MOCK_FILE.items.toLocaleString()}개 항목이 복원되었습니다.</p>
            <button onClick={() => { setImportStep("select"); setFileSelected(false); setConfirmText(""); }}
              className="bg-primary text-white px-6 py-3 rounded-xl font-medium hover:bg-blue-700 transition-colors">
              완료
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto px-4 sm:px-6 py-6 space-y-4">
      <h1 className="text-xl font-bold text-foreground mb-5">데이터 관리</h1>
      <div className="bg-card border border-border rounded-2xl p-6">
        <h2 className="text-base font-semibold text-foreground mb-1">데이터 내보내기</h2>
        <p className="text-sm text-muted-foreground mb-4">개인 데이터 백업용입니다.</p>
        <div className="space-y-2 text-sm mb-5">
          {[["전체 항목",`${total.toLocaleString()}건`],["Collection",`${COLLECTIONS.length}개`],["추천 이력",`${HISTORY.length}건`],["파일 형식","JSON"],["Schema 버전","v2.1"],["마지막 내보내기","2024-03-01"]].map(([k,v])=>(
            <div key={k} className="flex justify-between"><span className="text-muted-foreground">{k}</span><span>{v}</span></div>
          ))}
        </div>
        <button className="inline-flex items-center gap-2 bg-primary text-white px-5 py-2.5 rounded-xl font-medium hover:bg-blue-700 transition-colors text-sm">
          <Download size={15}/> 데이터 내보내기
        </button>
      </div>

      <div className="bg-card border border-border rounded-2xl p-6">
        <h2 className="text-base font-semibold text-foreground mb-1">데이터 가져오기</h2>
        <p className="text-sm text-muted-foreground mb-4">백업 파일로 데이터를 복원합니다.</p>
        {!fileSelected ? (
          <div onClick={() => setFileSelected(true)}
            className="border-2 border-dashed border-border rounded-xl p-8 text-center mb-4 hover:border-primary/30 transition-colors cursor-pointer">
            <Upload size={22} className="text-muted-foreground mx-auto mb-2"/>
            <p className="text-sm font-medium text-foreground mb-0.5">백업 파일 선택</p>
            <p className="text-xs text-muted-foreground">JSON 파일을 선택하거나 드래그해 주세요</p>
          </div>
        ) : (
          <div className="border border-border rounded-xl p-4 mb-4 flex items-center gap-3">
            <FileText size={18} className="text-primary flex-shrink-0"/>
            <div className="flex-1">
              <p className="text-sm font-medium text-foreground">{MOCK_FILE.filename}</p>
              <p className="text-xs text-muted-foreground">{MOCK_FILE.size}</p>
            </div>
            <button onClick={() => setFileSelected(false)} className="text-muted-foreground hover:text-foreground"><X size={15}/></button>
          </div>
        )}
        <div className="flex gap-3">
          <button onClick={() => fileSelected && setImportStep("validate")}
            disabled={!fileSelected}
            className="flex-1 bg-primary text-white py-2.5 rounded-xl font-medium hover:bg-blue-700 transition-colors text-sm disabled:opacity-40 disabled:cursor-not-allowed">
            파일 검증 →
          </button>
        </div>
        <div className="mt-3 flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-800">
          <AlertTriangle size={13} className="flex-shrink-0 mt-0.5"/>
          <p>복원 시 기존 데이터가 모두 대체됩니다. 먼저 현재 데이터를 내보내 주세요.</p>
        </div>
      </div>

      <div className="bg-muted/60 border border-border rounded-xl p-4 text-xs text-muted-foreground">
        <p className="font-medium text-foreground mb-1">서버 이전 안내</p>
        <p>애플리케이션 Export는 사용자 데이터 백업용입니다.</p>
        <p>서버 전체 이전은 PostgreSQL 백업과 복원을 사용해야 합니다.</p>
      </div>
    </div>
  );
}

// ─── Settings Page ────────────────────────────────────────────────────────────

function SettingsPage({ setPage }: { setPage: (p: Page) => void }) {
  return (
    <div className="max-w-xl mx-auto px-4 sm:px-6 py-6 space-y-4">
      <h1 className="text-xl font-bold text-foreground mb-5">설정</h1>
      {[
        { title:"일반", items:[
          { label:"앱 표시 이름", value:"박민준" },
          { label:"기본 추천 상태", value:"앞으로 볼 항목" },
          { label:"기본 카테고리", value:"전체" },
          { label:"목록 기본 정렬", value:"최근 수정순" },
          { label:"페이지당 표시 개수", value:"25개" },
        ]},
        { title:"화면", items:[
          { label:"테마", value:"라이트" },
          { label:"목록 밀도", value:"보통" },
        ]},
        { title:"외부 콘텐츠", items:[
          { label:"TMDB 연동 상태", value:"연동됨" },
          { label:"기본 검색 언어", value:"한국어" },
          { label:"성인 콘텐츠 제외", value:"켜짐" },
        ]},
        { title:"데이터", items:[
          { label:"데이터 내보내기·가져오기", value:"" },
          { label:"App Version", value:"1.0.0" },
          { label:"Schema Version", value:"v2.1" },
        ]},
        { title:"계정", items:[
          { label:"이메일", value:"minjun@example.com" },
          { label:"표시 이름", value:"박민준" },
          { label:"비밀번호 변경", value:"" },
        ]},
      ].map(sec => (
        <div key={sec.title} className="bg-card border border-border rounded-2xl overflow-hidden">
          <div className="px-5 py-3 border-b border-border">
            <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{sec.title}</h2>
          </div>
          {sec.items.map((item, i) => (
            <button key={item.label}
              className={`w-full flex items-center justify-between px-5 py-3.5 hover:bg-muted/40 transition-colors ${i<sec.items.length-1?"border-b border-border":""}`}>
              <span className="text-sm text-foreground">{item.label}</span>
              <div className="flex items-center gap-2">
                {item.value && <span className="text-xs text-muted-foreground">{item.value}</span>}
                <ChevronRight size={14} className="text-muted-foreground"/>
              </div>
            </button>
          ))}
        </div>
      ))}

      {/* Category Management Link */}
      <div className="bg-card border border-border rounded-2xl overflow-hidden">
        <button onClick={() => setPage("category-manage")}
          className="w-full flex items-center justify-between px-5 py-4 hover:bg-muted/40 transition-colors">
          <div className="flex items-center gap-3">
            <Palette size={16} className="text-muted-foreground"/>
            <span className="text-sm font-medium text-foreground">Category 관리</span>
          </div>
          <ChevronRight size={14} className="text-muted-foreground"/>
        </button>
      </div>

      <div className="bg-card border border-border rounded-2xl overflow-hidden">
        <button className="w-full flex items-center gap-3 px-5 py-4 text-red-500 hover:bg-red-50 transition-colors">
          <LogOut size={15}/><span className="text-sm font-medium">로그아웃</span>
        </button>
      </div>
      <p className="text-[10px] text-muted-foreground text-center">PickNext v1.0.0 · Schema v2.1</p>
    </div>
  );
}

// ─── App ──────────────────────────────────────────────────────────────────────

type ItemDetailOrigin = "items" | "home" | "collections";

interface ItemDetailSelection {
  itemId: string;
  origin: ItemDetailOrigin;
  collectionId?: string;
  collectionItemsPage?: number;
}

export default function App() {
  const [page, setPage]               = useState<Page>("home");
  const [itemDetailSelection, setItemDetailSelection] =
    useState<ItemDetailSelection | null>(null);
  const [itemsSnapshot, setItemsSnapshot] =
    useState<ItemsPageStateSnapshot | null>(null);
  const [collectionsSnapshot, setCollectionsSnapshot] =
    useState<CollectionsQuerySnapshot | null>(null);
  const [collectionDetailSelection, setCollectionDetailSelection] =
    useState<CollectionDetailSelection | null>(null);
  const [selectedHistory, setSelectedHistory] = useState<HistoryEntry | null>(null);
  const [recommendCats, setRecommendCats]     = useState<string[]>([]);
  const [toast, setToast]                     = useState<string | null>(null);
  const [addItemOpen, setAddItemOpen]         = useState(false);
  const [editItemTarget, setEditItemTarget]   = useState<Item | null>(null);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2800);
  }, []);

  const openItemDetail = useCallback((
    itemId: string,
    origin: ItemDetailOrigin,
    extras?: { collectionId?: string; collectionItemsPage?: number },
  ) => {
    setItemDetailSelection({
      itemId,
      origin,
      collectionId: extras?.collectionId,
      collectionItemsPage: extras?.collectionItemsPage,
    });
    setPage("item-detail");
  }, []);

  const closeItemDetail = useCallback(() => {
    const selection = itemDetailSelection;
    if (selection?.origin === "collections" && selection.collectionId) {
      setCollectionDetailSelection({
        collectionId: selection.collectionId,
        itemsPage: selection.collectionItemsPage ?? 1,
      });
      setPage("collections");
      setItemDetailSelection(null);
      return;
    }
    const destination = selection?.origin ?? "items";
    setPage(destination === "collections" ? "collections" : destination);
    setItemDetailSelection(null);
  }, [itemDetailSelection]);

  const navigateFromLayout = useCallback((next: Page) => {
    if (next !== "item-detail") {
      setItemDetailSelection(null);
    }
    if (next !== "collections") {
      setCollectionDetailSelection(null);
    }
    setPage(next);
  }, []);

  const navigateToHistory = (h: HistoryEntry) => { setSelectedHistory(h); setPage("history-detail"); };
  const navigateToRecommend = (cats: string[]) => { setRecommendCats(cats); setPage("recommend"); };
  const openAddItem = () => { setEditItemTarget(null); setAddItemOpen(true); };

  const renderPage = () => {
    switch (page) {
      case "home":
        return (
          <HomePage
            setPage={setPage}
            navigateToRecommend={navigateToRecommend}
            openAddItem={openAddItem}
            openItemDetail={(id) => openItemDetail(id, "home")}
          />
        );
      case "search":         return <SearchPage showToast={showToast}/>;
      case "recommend":      return <RecommendPage key={recommendCats.join(",")} preselectedCats={recommendCats} showToast={showToast}/>;
      case "items":
        return (
          <ItemsPage
            showToast={showToast}
            openAddItem={openAddItem}
            openItemDetail={(id) => openItemDetail(id, "items")}
            initialSnapshot={itemsSnapshot}
            onSnapshotChange={setItemsSnapshot}
          />
        );
      case "collections":
        return (
          <CollectionsPage
            showToast={showToast}
            initialSnapshot={collectionsSnapshot}
            onSnapshotChange={setCollectionsSnapshot}
            selection={collectionDetailSelection}
            onSelectionChange={setCollectionDetailSelection}
            openItemDetail={(itemId, context) =>
              openItemDetail(itemId, "collections", context)
            }
          />
        );
      case "history":        return <HistoryPage navigateToHistory={navigateToHistory}/>;
      case "data":           return <DataPage/>;
      case "settings":       return <SettingsPage setPage={setPage}/>;
      case "item-detail":
        return (
          <ItemDetailPage
            itemId={itemDetailSelection?.itemId ?? null}
            onBack={closeItemDetail}
            showToast={showToast}
            backLabel={
              itemDetailSelection?.origin === "collections"
                ? "Collection으로"
                : "목록으로"
            }
          />
        );
      case "history-detail": return selectedHistory ? <HistoryDetailPage entry={selectedHistory} onBack={() => setPage("history")} showToast={showToast}/> : null;
      case "category-manage":return <CategoryManagePage onBack={() => setPage("settings")} showToast={showToast}/>;
    }
  };

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <AppLayout currentPage={page} onNavigate={navigateFromLayout} onAddItem={openAddItem}>
        {renderPage()}
      </AppLayout>

      {/* Global: Item Form Modal */}
      {addItemOpen && (
        <ItemFormModal
          editItem={editItemTarget || undefined}
          onClose={() => { setAddItemOpen(false); setEditItemTarget(null); }}
          onSave={() => {}}
          showToast={showToast}
        />
      )}

      {/* Global toast */}
      {toast && <Toast msg={toast}/>}
    </div>
  );
}
