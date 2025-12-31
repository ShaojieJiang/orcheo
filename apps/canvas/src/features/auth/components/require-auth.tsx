import { Navigate, Outlet, useLocation } from "react-router-dom";
import { isAuthenticated } from "@features/auth/lib/auth-session";

export default function RequireAuth() {
  const location = useLocation();
  const redirectTo = `${location.pathname}${location.search}${location.hash}`;

  if (isAuthenticated()) {
    return <Outlet />;
  }

  return <Navigate to="/login" replace state={{ from: redirectTo }} />;
}
