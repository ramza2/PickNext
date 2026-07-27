import { apiRequest } from "./client";
import type {
  RandomRecommendationRequest,
  RandomRecommendationResponse,
} from "../types/recommendation";

export function getRandomRecommendation(
  body: RandomRecommendationRequest,
  signal?: AbortSignal,
): Promise<RandomRecommendationResponse> {
  return apiRequest<RandomRecommendationResponse>("/recommendations/random", {
    method: "POST",
    body: JSON.stringify(body),
    signal,
  });
}
