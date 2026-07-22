import type { ReactNode } from "react";

export type Status = "PLANNED" | "COMPLETED";
export type RecommendStep = "setup" | "result" | "complete";
export type ImportStep = "select" | "validate" | "preview" | "confirm" | "result";

export interface Category {
  id: string;
  name: string;
  icon: ReactNode;
  color: string;
  bgColor: string;
  total: number;
  planned: number;
  completed: number;
}

export interface Item {
  id: string;
  title: string;
  categoryId: string;
  collectionId?: string;
  status: Status;
  rating?: number;
  progressNote?: string;
  memo?: string;
  sourceType?: "MOVIE" | "TV";
  sourceFrom?: "TMDB";
  releaseDate?: string;
  overview?: string;
  registeredAt: string;
  updatedAt: string;
}

export interface Collection {
  id: string;
  name: string;
  categoryId: string;
  itemCount: number;
  plannedCount: number;
  completedCount: number;
  avgRating?: number;
  updatedAt: string;
}

export type Candidate =
  | { type: "ITEM"; data: Item }
  | { type: "COLLECTION"; data: Collection };

export interface HistoryEntry {
  id: string;
  selectedAt: string;
  title: string;
  categoryId: string;
  statusAtTime: Status;
  currentStatus: Status;
  type: "ITEM" | "COLLECTION";
  itemId?: string;
  collectionId?: string;
}

export interface TMDBResult {
  id: number;
  title: string;
  originalTitle: string;
  type: "MOVIE" | "TV";
  releaseDate: string;
  country: string;
  rating: number;
  genres: string[];
  overview: string;
  poster?: string;
  cast?: string[];
  runtime?: number;
  seasons?: number;
  alreadyAdded?: boolean;
}

export interface MockFileMeta {
  filename: string;
  size: string;
  exportedAt: string;
  appVersion: string;
  schemaVersion: string;
  user: string;
  categories: number;
  collections: number;
  items: number;
  history: number;
  status: "ok";
}
