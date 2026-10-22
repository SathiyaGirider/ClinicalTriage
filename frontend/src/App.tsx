import { Navigate, Route, Routes } from "react-router-dom";
import Login from "./auth/Login";
import Register from "./auth/Register";
import DoctorApp from "./doctor/DoctorApp";
import NurseApp from "./nurse/NurseApp";
import PatientApp from "./patient/PatientApp";
import { homeFor, useAuth } from "./shared/auth";
import Forbidden from "./shared/Forbidden";
import { RequireRole } from "./shared/guards";
import NotFound from "./shared/NotFound";
import { Loading } from "./shared/ui";
import { ToastProvider } from "./shared/ui/Toast";

function Root() {
  const { me, loading } = useAuth();
  if (loading) return <Loading />;
  return <Navigate to={me ? homeFor(me.role) : "/login"} replace />;
}

export default function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route path="/" element={<Root />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forbidden" element={<Forbidden />} />
        <Route path="/patient/*" element={<RequireRole role="patient"><PatientApp /></RequireRole>} />
        <Route path="/staff/nurse/*" element={<RequireRole role="nurse"><NurseApp /></RequireRole>} />
        <Route path="/staff/doctor/*" element={<RequireRole role="doctor"><DoctorApp /></RequireRole>} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </ToastProvider>
  );
}

