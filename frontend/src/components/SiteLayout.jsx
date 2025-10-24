import React from 'react';
import { Outlet } from 'react-router-dom';
import Header from './Header';

const SiteLayout = () => {
  return (
    <div className="min-h-screen">
      <Header />
      <Outlet />
    </div>
  );
};

export default SiteLayout;

