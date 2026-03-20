import React from 'react';

export default function GlassCard({ children, className = '', style }: { children: React.ReactNode, className?: string, style?: React.CSSProperties }) {
  return (
    <div 
      className={`bg-omni-card border border-white/10 backdrop-blur-xl rounded-2xl p-6 hover:border-omni-neon/50 transition-all duration-300 shadow-[0_0_20px_rgba(0,0,0,0.3)] ${className}`}
      style={style}
    >
      {children}
    </div>
  );
}
