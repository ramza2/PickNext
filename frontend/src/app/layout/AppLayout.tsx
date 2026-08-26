import { useState, type ReactNode } from "react";
import {
  Home, Search, List, Folder, Settings, Shuffle, Clock,
  Plus, Target, MoreHorizontal, ChevronRight,
} from "lucide-react";
import type { Page } from "../pageTypes";

const NAV: { id: Page; label: string; icon: ReactNode }[] = [
  { id: "home", label: "홈", icon: <Home size={17} /> },
  { id: "recommend", label: "랜덤 추천", icon: <Shuffle size={17} /> },
  { id: "items", label: "전체 항목", icon: <List size={17} /> },
  { id: "search", label: "콘텐츠 검색", icon: <Search size={17} /> },
  { id: "collections", label: "Collection", icon: <Folder size={17} /> },
  { id: "history", label: "추천 이력", icon: <Clock size={17} /> },
  { id: "settings", label: "설정", icon: <Settings size={17} /> },
];

const MOBILE_PRIMARY = NAV.filter((item) =>
  item.id === "home" || item.id === "recommend" || item.id === "items",
);
const MORE_NAV = NAV.filter((item) =>
  item.id === "search" ||
  item.id === "collections" ||
  item.id === "history" ||
  item.id === "settings",
);

interface AppLayoutProps {
  /** Sidebar / bottom-nav highlight (detail routes map to parent). */
  activeNavId: Page | null;
  title: string;
  onNavigate: (page: Page) => void;
  onAddItem: () => void;
  children: ReactNode;
  loginId?: string | null;
  onLogout?: () => void;
}

export default function AppLayout({
  activeNavId,
  title,
  onNavigate,
  onAddItem,
  children,
  loginId,
  onLogout,
}: AppLayoutProps) {
  const [moreOpen, setMoreOpen] = useState(false);
  const navTo = (p: Page) => {
    onNavigate(p);
    setMoreOpen(false);
  };

  return (
    <>
      <aside className="hidden lg:flex flex-col w-56 bg-sidebar border-r border-sidebar-border flex-shrink-0">
        <div className="px-4 py-5 border-b border-sidebar-border">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-primary rounded-xl flex items-center justify-center flex-shrink-0">
              <Target size={15} className="text-white" />
            </div>
            <div>
              <div className="font-bold text-sidebar-foreground text-sm leading-tight">PickNext</div>
              <div className="text-[10px] text-muted-foreground leading-tight">고민하지 말고, 다음 선택은</div>
            </div>
          </div>
          {loginId && (
            <div className="mt-3 text-xs text-muted-foreground truncate" title={loginId}>
              {loginId}
            </div>
          )}
        </div>
        <nav className="flex-1 px-3 py-3 space-y-0.5 overflow-y-auto">
          {NAV.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => navTo(item.id)}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                activeNavId === item.id
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground hover:bg-sidebar-accent/50"
              }`}
            >
              <span className={activeNavId === item.id ? "text-primary" : "text-muted-foreground"}>
                {item.icon}
              </span>
              {item.label}
            </button>
          ))}
        </nav>
        {onLogout && (
          <div className="px-3 py-3 border-t border-sidebar-border">
            <button
              type="button"
              onClick={onLogout}
              className="w-full text-left text-xs text-muted-foreground hover:text-foreground px-3 py-2 rounded-xl hover:bg-sidebar-accent/50"
            >
              로그아웃
            </button>
          </div>
        )}
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="flex items-center justify-between px-4 sm:px-6 py-3 bg-card border-b border-border flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="lg:hidden flex items-center gap-2">
              <div className="w-7 h-7 bg-primary rounded-lg flex items-center justify-center">
                <Target size={13} className="text-white" />
              </div>
              <span className="font-bold text-foreground text-sm">PickNext</span>
            </div>
            <h1 className="text-sm font-semibold text-foreground lg:block hidden">{title}</h1>
            <span className="lg:hidden text-sm font-semibold text-foreground">{title}</span>
          </div>
          <div className="flex items-center gap-2">
            {loginId && (
              <span className="hidden sm:inline text-xs text-muted-foreground max-w-[8rem] truncate">
                {loginId}
              </span>
            )}
            <button
              type="button"
              onClick={() => navTo("search")}
              className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-xl transition-colors"
              aria-label="콘텐츠 검색"
            >
              <Search size={15} />
            </button>
            <button
              type="button"
              onClick={onAddItem}
              className="hidden sm:inline-flex items-center gap-1.5 text-xs bg-primary text-white px-3 py-1.5 rounded-xl hover:bg-blue-700 transition-colors font-medium"
            >
              <Plus size={13} /> 항목 추가
            </button>
          </div>
        </header>

        <main
          data-picknext-scroll-root
          className="flex-1 overflow-y-auto pb-20 lg:pb-0 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        >
          {children}
        </main>

        <nav className="lg:hidden fixed bottom-0 left-0 right-0 bg-card border-t border-border px-1 py-1.5 z-40">
          <div className="flex">
            {MOBILE_PRIMARY.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => navTo(item.id)}
                className={`flex-1 flex flex-col items-center gap-0.5 py-1 rounded-xl transition-colors ${
                  activeNavId === item.id && !moreOpen ? "text-primary" : "text-muted-foreground"
                }`}
              >
                {item.icon}
                <span className="text-[9px] font-medium">
                  {item.id === "recommend"
                    ? "추천"
                    : item.id === "items"
                      ? "항목"
                      : item.label}
                </span>
              </button>
            ))}
            <button
              type="button"
              onClick={() => setMoreOpen(!moreOpen)}
              className={`flex-1 flex flex-col items-center gap-0.5 py-1 rounded-xl transition-colors ${
                moreOpen ? "text-primary" : "text-muted-foreground"
              }`}
            >
              <MoreHorizontal size={20} />
              <span className="text-[9px] font-medium">더보기</span>
            </button>
          </div>
        </nav>

        {moreOpen && (
          <div className="lg:hidden fixed inset-0 z-50" onClick={() => setMoreOpen(false)}>
            <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
            <div
              className="absolute bottom-0 left-0 right-0 bg-card rounded-t-2xl shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="w-8 h-1 bg-border rounded-full mx-auto mt-3 mb-4" />
              <div className="px-3 pb-8 space-y-0.5">
                {MORE_NAV.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => navTo(item.id)}
                    className="w-full flex items-center gap-3 px-4 py-3.5 rounded-xl hover:bg-muted transition-colors"
                  >
                    <span className="text-muted-foreground">{item.icon}</span>
                    <span className="text-sm font-medium text-foreground">{item.label}</span>
                    <ChevronRight size={14} className="text-muted-foreground ml-auto" />
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
