'use client';

import React, { useState } from 'react';
import Sidebar from '@/components/Sidebar';

export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const [isPinned, setIsPinned] = useState(true);
  const [isHovered, setIsHovered] = useState(false);

  const isExpanded = isPinned || isHovered;

  return (
    <div className="app-container d-flex">
      <Sidebar 
        isPinned={isPinned} 
        onTogglePin={() => setIsPinned(!isPinned)}
        onHoverChange={setIsHovered}
      />
      <main 
        className="main-content" 
        style={{ 
          marginLeft: isExpanded ? '260px' : '80px', 
          padding: '2rem', 
          flex: 1, 
          transition: 'margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          minWidth: 0, // Garante que o conteúdo possa encolher se necessário
          width: '100%'
        }}
      >
        <div className="container-fluid p-0">
          {children}
        </div>
      </main>
    </div>
  );
}
