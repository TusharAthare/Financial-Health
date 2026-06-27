import { apiFetch, setTokens, clearTokens } from "@/lib/api-client";
import type {
  Account,
  AuthTokens,
  LoginPayload,
  RegisterPayload,
  User,
} from "@/types/api";

interface RegisterResponse extends AuthTokens {
  user: User;
}

interface LoginResponse extends AuthTokens {}

export async function registerUser(payload: RegisterPayload): Promise<User> {
  const data = await apiFetch<RegisterResponse>("/api/auth/register/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  setTokens(data.access, data.refresh);
  return data.user;
}

export async function loginUser(payload: LoginPayload): Promise<AuthTokens> {
  const data = await apiFetch<LoginResponse>("/api/auth/login/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  setTokens(data.access, data.refresh);
  return data;
}

export async function logoutUser(): Promise<void> {
  const refresh = localStorage.getItem("fh_refresh_token");
  try {
    if (refresh) {
      await apiFetch<void>("/api/logout/", {
        method: "POST",
        body: JSON.stringify({ refresh }),
      });
    }
  } finally {
    clearTokens();
  }
}

export async function fetchCurrentUser(): Promise<User> {
  return apiFetch<User>("/api/core/me/");
}

export async function fetchAccounts(): Promise<Account[]> {
  return apiFetch<Account[]>("/api/statements/accounts/");
}

export async function createAccount(payload: {
  bank_name: string;
  masked_number: string;
  currency?: string;
}): Promise<Account> {
  return apiFetch<Account>("/api/statements/accounts/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
