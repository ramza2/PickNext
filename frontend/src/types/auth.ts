export interface AuthUser {
  id: string;
  login_id: string | null;
  email: string;
}

export interface LoginRequest {
  login_id: string;
  password: string;
  remember_me: boolean;
}

export interface SignupRequestCode {
  login_id: string;
  email: string;
}

export interface SignupComplete {
  login_id: string;
  email: string;
  verification_code: string;
  password: string;
  password_confirm: string;
}

export interface FindIdRequest {
  email: string;
}

export interface FindIdVerify {
  email: string;
  verification_code: string;
}

export interface PasswordResetRequest {
  login_id: string;
  email: string;
}

export interface PasswordResetConfirm {
  login_id: string;
  email: string;
  verification_code: string;
  new_password: string;
  new_password_confirm: string;
}

export interface AuthErrorBody {
  code: string;
  message: string;
}

export interface MessageResponse {
  message: string;
}

export interface FindIdVerifyResponse {
  login_id: string;
}
