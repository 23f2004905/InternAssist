import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Register from "./pages/Register";
import ForgotPassword from "./pages/ForgotPassword";
import StudentDashboard from "./pages/StudentDashboard";
import FacultyDashboard from "./pages/FacultyDashboard";
import AdminDashboard from "./pages/AdminDashboard";
import Documents from "./pages/Documents";
import Users from "./pages/Users";
import Conversations from "./pages/Conversations";
import AskAssistant from "./pages/AskAssistant";

function LoadingScreen() {
  return <div className="loading-screen" role="status">Loading InternAssist…</div>;
}

function ProtectedRoute({ children, roles }) {
  const { currentUser, loading } = useAuth();
  if (loading) return <LoadingScreen />;
  if (!currentUser) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(currentUser.role)) return <Navigate to="/dashboard" replace />;
  return children;
}

function DashboardRouter() {
  const { currentUser } = useAuth();
  if (currentUser?.role === "admin") return <AdminDashboard />;
  if (currentUser?.role === "faculty") return <FacultyDashboard />;
  return <StudentDashboard />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/dashboard" element={<ProtectedRoute><DashboardRouter /></ProtectedRoute>} />
      <Route path="/admin" element={<ProtectedRoute roles={["admin"]}><AdminDashboard /></ProtectedRoute>} />
      <Route path="/faculty" element={<ProtectedRoute roles={["faculty"]}><FacultyDashboard /></ProtectedRoute>} />
      <Route path="/student" element={<ProtectedRoute roles={["student"]}><StudentDashboard /></ProtectedRoute>} />
      <Route path="/assistant" element={<ProtectedRoute><AskAssistant /></ProtectedRoute>} />
      <Route path="/ask" element={<Navigate to="/assistant" replace />} />
      <Route path="/documents" element={<ProtectedRoute><Documents /></ProtectedRoute>} />
      <Route path="/conversations" element={<ProtectedRoute><Conversations /></ProtectedRoute>} />
      <Route path="/conversations/:conversationId" element={<ProtectedRoute><AskAssistant /></ProtectedRoute>} />
      <Route path="/users" element={<ProtectedRoute roles={["admin"]}><Users /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default function App() {
  return <AuthProvider><BrowserRouter><AppRoutes /></BrowserRouter></AuthProvider>;
}
