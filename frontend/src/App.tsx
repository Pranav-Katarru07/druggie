import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import PatientsProvider from "./data/PatientsProvider";
import AppLayout from "./layout/AppLayout";
import DrugsPage from "./pages/DrugsPage";
import InsightsPage from "./pages/InsightsPage";
import PatientsPage from "./pages/PatientsPage";
import ReviewPage from "./pages/ReviewPage";

export default function App() {
  return (
    <PatientsProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<Navigate to="/review" replace />} />
            <Route path="review" element={<DrugsPage />} />
            <Route path="review/:drugKey" element={<ReviewPage />} />
            <Route path="patients" element={<PatientsPage />} />
            <Route path="patients/:personId" element={<PatientsPage />} />
            <Route path="insights" element={<InsightsPage />} />
            <Route path="*" element={<Navigate to="/review" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </PatientsProvider>
  );
}
