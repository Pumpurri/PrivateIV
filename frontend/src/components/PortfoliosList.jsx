import React from 'react';
import { useNavigate } from 'react-router-dom';
import CreatePortfolio from './CreatePortfolio';

const PortfoliosList = () => {
  const navigate = useNavigate();

  const handlePortfolioCreated = () => {
    navigate('/dashboard');
  };

  return (
    <div style={{ 
      display: 'flex', 
      alignItems: 'flex-start', 
      justifyContent: 'center', 
      minHeight: '100vh', 
      padding: '60px 20px',
      background: 'linear-gradient(180deg, rgba(18,26,47,.9), rgba(12,20,39,.9))'
    }}>
      <CreatePortfolio onSuccess={handlePortfolioCreated} />
    </div>
  );
};

export default PortfoliosList;
