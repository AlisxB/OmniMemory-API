'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Users, BrainCircuit, Webhook, ChevronLeft, ChevronRight } from 'lucide-react';

interface SidebarProps {
  isPinned: boolean;
  onTogglePin: () => void;
  onHoverChange: (hovered: boolean) => void;
}

export default function Sidebar({ isPinned, onTogglePin, onHoverChange }: SidebarProps) {
  const pathname = usePathname();

  const isActive = (path: string) => {
    if (path === '/' && pathname === '/') return true;
    if (path !== '/' && pathname.startsWith(path)) return true;
    return false;
  };

  return (
    <aside 
      className={`sidebar-modern ${isPinned ? 'pinned' : ''}`}
      onMouseEnter={() => onHoverChange(true)}
      onMouseLeave={() => onHoverChange(false)}
    >
      <div className="sidebar-header p-4 position-relative">
        <div className="d-flex align-items-center gap-3 overflow-hidden">
          <div className="sidebar-logo-icon" style={{ color: '#00f0ff', fontSize: '1.8rem', minWidth: '32px' }}>🧠</div>
          <div className="sidebar-text-content">
            <h5 className="mb-0 text-white fw-bold tracking-wider">OMNIMEMORY</h5>
            <div style={{ fontSize: '0.7rem', color: 'rgba(0, 240, 255, 0.8)' }}>Admin v2.0</div>
          </div>
        </div>
        
        <button 
          onClick={onTogglePin}
          className="sidebar-pin-btn"
          title={isPinned ? "Recolher Menu" : "Expandir Menu"}
        >
          {isPinned ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
        </button>
      </div>

      <nav className="d-flex flex-column px-2 mt-3 gap-2">
        <Link href="/" className={`sidebar-link ${isActive('/') ? 'active' : ''} d-flex align-items-center gap-3`}>
          <div className="sidebar-icon-wrapper"><LayoutDashboard size={20} /></div>
          <span className="sidebar-text-content">Visão Geral</span>
        </Link>
        <Link href="/tenants" className={`sidebar-link ${isActive('/tenants') ? 'active' : ''} d-flex align-items-center gap-3`}>
          <div className="sidebar-icon-wrapper"><Users size={20} /></div>
          <span className="sidebar-text-content">Tenants</span>
        </Link>
        <Link href="/memory" className={`sidebar-link ${isActive('/memory') ? 'active' : ''} d-flex align-items-center gap-3`}>
          <div className="sidebar-icon-wrapper"><BrainCircuit size={20} /></div>
          <span className="sidebar-text-content">Memória</span>
        </Link>
        <Link href="/webhooks" className={`sidebar-link ${isActive('/webhooks') ? 'active' : ''} d-flex align-items-center gap-3`}>
          <div className="sidebar-icon-wrapper"><Webhook size={20} /></div>
          <span className="sidebar-text-content">Webhooks</span>
        </Link>
      </nav>

      <style jsx global>{`
        .sidebar-modern {
          width: 80px;
          border-right: 1px solid rgba(255,255,255,0.05);
          background-color: rgba(11, 12, 16, 0.98);
          position: fixed;
          left: 0;
          top: 0;
          height: 100vh;
          z-index: 1000;
          transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          overflow: hidden;
          white-space: nowrap;
        }

        .sidebar-modern:hover, .sidebar-modern.pinned {
          width: 260px;
        }

        .sidebar-modern:hover {
          box-shadow: 10px 0 30px rgba(0,0,0,0.5);
        }

        .sidebar-modern.pinned {
          box-shadow: none;
        }

        .sidebar-text-content {
          opacity: 0;
          transition: opacity 0.2s ease;
          pointer-events: none;
        }

        .sidebar-modern:hover .sidebar-text-content,
        .sidebar-modern.pinned .sidebar-text-content {
          opacity: 1;
          pointer-events: auto;
        }

        .sidebar-pin-btn {
          position: absolute;
          right: 10px;
          top: 50%;
          transform: translateY(-50%);
          background: rgba(255,255,255,0.05);
          border: 1px solid rgba(255,255,255,0.1);
          color: rgba(255,255,255,0.4);
          width: 28px;
          height: 28px;
          border-radius: 6px;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          opacity: 0;
          transition: all 0.2s ease;
        }

        .sidebar-modern:hover .sidebar-pin-btn,
        .sidebar-modern.pinned .sidebar-pin-btn {
          opacity: 1;
        }

        .sidebar-pin-btn:hover {
          background: rgba(0, 240, 255, 0.1);
          color: #00f0ff;
        }

        .sidebar-icon-wrapper {
          min-width: 40px;
          display: flex;
          justify-content: center;
          align-items: center;
        }

        .sidebar-link {
          padding: 0.75rem 1rem;
          border-radius: 12px;
          color: rgba(255,255,255,0.6);
          text-decoration: none;
          transition: all 0.2s ease;
          margin: 0 4px;
        }

        .sidebar-link:hover {
          background: rgba(0, 240, 255, 0.05);
          color: #00f0ff;
        }

        .sidebar-link.active {
          background: rgba(0, 240, 255, 0.1);
          color: #00f0ff;
          border: 1px solid rgba(0, 240, 255, 0.2);
        }
      `}</style>
    </aside>
  );
}
