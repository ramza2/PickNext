import { apiRequest } from "./client";
import type {
  AuthUser,
  FindIdRequest,
  FindIdVerify,
  FindIdVerifyResponse,
  LoginRequest,
  MessageResponse,
  PasswordResetConfirm,
  PasswordResetRequest,
  SignupComplete,
  SignupRequestCode,
} from "../types/auth";

export function fetchAuthMe(signal?: AbortSignal): Promise<AuthUser> {
  return apiRequest<AuthUser>("/auth/me", { method: "GET", signal });
}

export function login(body: LoginRequest): Promise<AuthUser> {
  return apiRequest<AuthUser>("/auth/login", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function logout(): Promise<MessageResponse> {
  return apiRequest<MessageResponse>("/auth/logout", { method: "POST" });
}

export function signupRequestCode(body: SignupRequestCode): Promise<MessageResponse> {
  return apiRequest<MessageResponse>("/auth/signup/request-code", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function signupComplete(body: SignupComplete): Promise<AuthUser> {
  return apiRequest<AuthUser>("/auth/signup/complete", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function findIdRequestCode(body: FindIdRequest): Promise<MessageResponse> {
  return apiRequest<MessageResponse>("/auth/find-id/request-code", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function findIdVerify(body: FindIdVerify): Promise<FindIdVerifyResponse> {
  return apiRequest<FindIdVerifyResponse>("/auth/find-id/verify", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function passwordResetRequestCode(
  body: PasswordResetRequest,
): Promise<MessageResponse> {
  return apiRequest<MessageResponse>("/auth/password-reset/request-code", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function passwordResetConfirm(
  body: PasswordResetConfirm,
): Promise<MessageResponse> {
  return apiRequest<MessageResponse>("/auth/password-reset/confirm", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
