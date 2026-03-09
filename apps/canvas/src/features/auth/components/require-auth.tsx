import { Navigate, Outlet, useLocation } from "react-router-dom";
import { isAuthenticated } from "@features/auth/lib/auth-session";

const isValidHttpUrl = (value: unknown): boolean => {
  if (!value || typeof value !== "string") return false;
  try {
    const url = new URL(value.trim());
    return url.protocol === "https:" || url.protocol === "http:";
  } catch {
    return false;
  }
};

const authEnabled = isValidHttpUrl(import.meta.env.VITE_ORCHEO_AUTH_ISSUER);

export default function RequireAuth() {
  const location = useLocation();
  const redirectTo = `${location.pathname}${location.search}${location.hash}`;

  if (!authEnabled || isAuthenticated()) {
    return <Outlet />;
  }

  return <Navigate to="/login" replace state={{ from: redirectTo }} />;
}
