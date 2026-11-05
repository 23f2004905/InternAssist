
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";

import {
  AuthProvider,
  useAuth,
} from "./context/AuthContext";

import Login from "./pages/Login";
import Register from "./pages/Register";
import ForgotPassword from "./pages/ForgotPassword";

import StudentDashboard from "./pages/StudentDashboard";
import FacultyDashboard from "./pages/FacultyDashboard";
import AdminDashboard from "./pages/AdminDashboard";

import Documents from "./pages/Documents";
import Users from "./pages/Users";
import Conversations from "./pages/Conversations";
import ConversationDetail from "./pages/ConversationDetail";
import AskAssistant from "./pages/AskAssistant";

function ProtectedRoute({ children }) {
  const { currentUser, loading } = useAuth();

  if (loading) {
    return <div className="loading-screen">Loading...</div>;
  }

  if (!currentUser) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

function RoleRoute({ allowedRoles, children }) {
  const { currentUser, loading } = useAuth();

  if (loading) {
    return <div className="loading-screen">Loading...</div>;
  }

  if (!currentUser) {
    return <Navigate to="/login" replace />;
  }

  if (!allowedRoles.includes(currentUser.role)) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
}

function DashboardRouter() {
  const { currentUser } = useAuth();

  if (!currentUser) {
    return <Navigate to="/login" replace />;
  }

  if (currentUser.role === "admin") {
    return <AdminDashboard />;
  }

  if (currentUser.role === "faculty") {
    return <FacultyDashboard />;
  }

  return <StudentDashboard />;
}

function AppRoutes() {
  return (
    <Routes>
      {/* Public pages */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />

      {/* Dashboard */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardRouter />
          </ProtectedRoute>
        }
      />

      {/* Role-specific dashboards */}
      <Route
        path="/admin"
        element={
          <RoleRoute allowedRoles={["admin"]}>
            <AdminDashboard />
          </RoleRoute>
        }
      />

      <Route
        path="/faculty"
        element={
          <RoleRoute allowedRoles={["faculty"]}>
            <FacultyDashboard />
          </RoleRoute>
        }
      />

      <Route
        path="/student"
        element={
          <RoleRoute allowedRoles={["student"]}>
            <StudentDashboard />
          </RoleRoute>
        }
      />

      {/* Assistant */}
      <Route
        path="/assistant"
        element={
          <ProtectedRoute>
            <AskAssistant />
          </ProtectedRoute>
        }
      />

      <Route
        path="/ask"
        element={
          <ProtectedRoute>
            <AskAssistant />
          </ProtectedRoute>
        }
      />

      {/* Documents */}
      <Route
        path="/documents"
        element={
          <ProtectedRoute>
            <Documents />
          </ProtectedRoute>
        }
      />

      {/* Conversations list */}
      <Route
        path="/conversations"
        element={
          <ProtectedRoute>
            <Conversations />
          </ProtectedRoute>
        }
      />

      {/* Individual conversation — IMPORTANT */}
      <Route
        path="/conversations/:id"
        element={
          <ProtectedRoute>
            <ConversationDetail />
          </ProtectedRoute>
        }
      />

      {/* Users */}
      <Route
        path="/users"
        element={
          <ProtectedRoute>
            <Users />
          </ProtectedRoute>
        }
      />

      {/* Unknown routes */}
      <Route
        path="*"
        element={<Navigate to="/login" replace />}
      />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}
