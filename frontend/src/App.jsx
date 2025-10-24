import React from 'react';
import { BrowserRouter as Router, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./routes/ProtectedRoute";
import PublicRoute from "./routes/PublicRoute";
import Landing from "./components/Landing";
import Login from "./components/Login";
import Register from "./components/Register";
import UserDashboard from "./components/UserDashboard";
import AppLayout from "./components/AppLayout";
import SiteLayout from "./components/SiteLayout";
import SimpleLayout from "./components/SimpleLayout";
import PortfoliosList from "./components/PortfoliosList";
import PortfolioDetail from "./components/PortfolioDetail";
import Transactions from "./components/Transactions";
import { StockPriceProvider } from "./contexts/StockPriceContext";
import { AuthProvider } from "./contexts/AuthContext";

function App() {
    return (
        <Router>
            <AuthProvider>
                <StockPriceProvider>
                    <Routes>
                        <Route element={<SiteLayout />}>
                            <Route element={<PublicRoute />}>
                                <Route path="/" element={<Landing />} />
                                <Route path="/login" element={<Login />} />
                                <Route path="/register" element={<Register />} />
                            </Route>
                            <Route element={<ProtectedRoute />}>
                                <Route path="/dashboard" element={<UserDashboard />} />
                                <Route path="/app" element={<SimpleLayout />}>
                                    <Route path="portfolios" element={<PortfoliosList />} />
                                    <Route path="portfolios/:id" element={<PortfolioDetail />} />
                                    <Route path="portfolios/:id/:tab" element={<PortfolioDetail />} />
                                </Route>
                                <Route path="/app" element={<AppLayout />}>
                                    <Route path="transactions" element={<Transactions />} />
                                </Route>
                            </Route>
                        </Route>
                    </Routes>
                </StockPriceProvider>
            </AuthProvider>
        </Router>
    );
}

export default App;
