'use client';

import React, { useEffect, useState } from 'react';
import useSWR from 'swr';
import { fetchApi } from '@/lib/api';
import GlassCard from '@/components/GlassCard';
import { Brain, Users, Activity, BarChart3, TrendingUp } from 'lucide-react';

export default function EnhancedDashboard() {
  const [date, setDate] = useState('');

  const { data: statsData, isLoading: statsLoading } = useSWR('/admin/api/analytics/system-stats', fetchApi);
  const { data: distData, isLoading: distLoading } = useSWR('/admin/api/analytics/tenant-distribution', fetchApi);
  const { data: growthData, isLoading: growthLoading } = useSWR('/admin/api/analytics/memory-growth', fetchApi);
  const { data: feedData, isLoading: feedLoading } = useSWR('/admin/api/analytics/recent-activity', fetchApi, { refreshInterval: 5000 });

  const stats = statsData?.data || {
    total_tenants: 0,
    total_users: 0,
    total_messages: 0,
    total_memories: 0
  };

  const distribution = distData?.data?.top_tenants_by_usage || [];
  const growth = growthData?.data || [];
  const feed = feedData?.data || [];

  // Função para gerar o caminho do SVG dinamicamente
  const generateChartPath = (data: any[]) => {
    if (!data || data.length < 2) return { line: "", area: "" };
    
    const width = 930;
    const height = 200;
    const maxVal = Math.max(...data.map(d => d.count), 10); // Evitar divisão por zero
    
    const points = data.map((d, i) => ({
      x: 50 + (i * (width / (data.length - 1))),
      y: 250 - (d.count / maxVal * height)
    }));
    
    const linePath = `M ${points.map(p => `${p.x},${p.y}`).join(' L ')}`;
    const areaPath = `${linePath} L ${points[points.length-1].x},250 L 50,250 Z`;
    
    return { line: linePath, area: areaPath, lastPoint: points[points.length-1], maxVal };
  };

  const chart = generateChartPath(growth);

  useEffect(() => {
    const now = new Date();
    setDate(now.toLocaleDateString('pt-BR', { month: 'short', day: 'numeric', year: 'numeric' }) + ' | ' + 
            now.toLocaleTimeString('pt-BR', { hour: 'numeric', minute: '2-digit' }) + ' BRT');
  }, []);

  const formatNumber = (num: number) => {
    if (num === undefined || num === null) return '0';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
  };

  return (
    <div className="container-fluid p-0 animate-in fade-in duration-700">
      
      {/* HEADER */}
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h1 className="dash-title mb-0">PAINEL DE VISÃO GERAL</h1>
          <div className="dash-subtitle mt-1">{date || 'Carregando...'}</div>
        </div>
        
        {/* Top right mockup icons */}
        <div className="d-flex gap-2">
          <div className="glass-panel py-1 px-2 d-flex align-items-center justify-content-center" style={{ width: 40, height: 40, padding: 0 }}>
            <span style={{color: 'rgba(255,255,255,0.6)', fontSize: '1rem'}}>💬</span>
          </div>
          <div className="glass-panel py-1 px-2 d-flex align-items-center justify-content-center" style={{ width: 40, height: 40, padding: 0 }}>
            <span style={{color: 'rgba(255,255,255,0.6)', fontSize: '1rem'}}>🔔</span>
          </div>
          <div className="glass-panel py-1 px-2 d-flex align-items-center justify-content-center" style={{ width: 40, height: 40, padding: 0 }}>
            <span style={{color: 'rgba(255,255,255,0.6)', fontSize: '1rem'}}>⚙️</span>
          </div>
        </div>
      </div>

      {/* KPI ROW */}
      <div className="row mb-4">
        <div className="col-md-4">
          <GlassCard className="h-100">
            <div className="kpi-label d-flex align-items-center gap-2">
              <Brain size={14} className="text-omni-neon" /> 1. TOTAL DE MEMÓRIAS
            </div>
            <div className="d-flex align-items-baseline">
              <span className="kpi-value">{statsLoading ? '...' : formatNumber(stats.total_memories)}</span>
              <span className="kpi-perc">+12.4%</span>
            </div>
          </GlassCard>
        </div>
        <div className="col-md-4">
          <GlassCard className="h-100">
            <div className="kpi-label d-flex align-items-center gap-2">
              <Users size={14} className="text-omni-purple" /> 2. CLIENTES (TENANTS)
            </div>
            <div className="d-flex align-items-baseline">
              <span className="kpi-value">{statsLoading ? '...' : formatNumber(stats.total_tenants)}</span>
              <span className="kpi-perc">+3%</span>
            </div>
          </GlassCard>
        </div>
        <div className="col-md-4">
          <GlassCard className="h-100">
            <div className="kpi-label d-flex align-items-center gap-2">
              <Activity size={14} className="text-omni-accent" /> 3. TOTAL DE MENSAGENS
            </div>
            <div className="d-flex align-items-baseline">
              <span className="kpi-value">{statsLoading ? '...' : formatNumber(stats.total_messages)}</span>
              <span className="kpi-perc">+8%</span>
            </div>
          </GlassCard>
        </div>
      </div>

      {/* MAIN DATA ROW */}
      <div className="row">
        
        {/* LEFT COLUMN: Line Chart + Top Agents Table */}
        <div className="col-lg-8">
          
          {/* GRADIENT BORDERED CHART CARD */}
          <GlassCard className="neon-bordered mb-4" style={{ minHeight: '340px' }}>
            <div className="d-flex justify-content-between mb-2">
              <div className="fw-semibold text-white d-flex align-items-center gap-2">
                <TrendingUp size={18} className="text-omni-neon" /> CRESCIMENTO DA MEMÓRIA
              </div>
              <div className="text-white-50">...</div>
            </div>
            
            <div className="w-100 position-relative mt-4" style={{ height: '230px' }}>
              <svg width="100%" height="100%" preserveAspectRatio="none" viewBox="0 0 1000 300">
                <defs>
                   <linearGradient id="glowLine" x1="0%" y1="0%" x2="100%" y2="0%">
                      <stop offset="0%" stopColor="#00f0ff" />
                      <stop offset="100%" stopColor="#b300ff" />
                   </linearGradient>
                   <linearGradient id="areaGlow" x1="0%" y1="0%" x2="0%" y2="100%">
                      <stop offset="0%" stopColor="#00f0ff" stopOpacity="0.2" />
                      <stop offset="100%" stopColor="#b300ff" stopOpacity="0" />
                   </linearGradient>
                </defs>
                {/* Grid Lines */}
                {[0, 25, 50, 75, 100].map((y, i) => (
                  <line key={i} x1="50" y1={`${(y/100)*250}`} x2="980" y2={`${(y/100)*250}`} stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
                ))}
                
                {growthLoading ? (
                  <text x="500" y="150" fill="rgba(255,255,255,0.3)" textAnchor="middle">Sincronizando dados neurais...</text>
                ) : (
                  <>
                    {/* The Path */}
                    <path d={chart.area} fill="url(#areaGlow)" />
                    <path d={chart.line} fill="none" stroke="url(#glowLine)" strokeWidth="4" filter="drop-shadow(0px 4px 6px rgba(0,240,255,0.4))" />
                    
                    {/* Active Point */}
                    {chart.lastPoint && (
                      <circle cx={chart.lastPoint.x} cy={chart.lastPoint.y} r="6" fill="#fff" stroke="#b300ff" strokeWidth="3" filter="drop-shadow(0px 0px 8px #b300ff)" />
                    )}
                    
                    {/* Labels Y */}
                    <text x="40" y="50" fill="rgba(255,255,255,0.5)" fontSize="12" textAnchor="end">{formatNumber(chart.maxVal)}</text>
                    <text x="40" y="150" fill="rgba(255,255,255,0.5)" fontSize="12" textAnchor="end">{formatNumber(chart.maxVal / 2)}</text>
                    <text x="40" y="250" fill="rgba(255,255,255,0.5)" fontSize="12" textAnchor="end">0</text>
                    
                    {/* Labels X */}
                    {growth.map((d: any, i: number) => {
                      const x = 50 + (i * (930 / (growth.length - 1)));
                      return (
                        <text key={i} x={x} y="280" fill="rgba(255,255,255,0.5)" fontSize="11" textAnchor="middle">{d.date}</text>
                      );
                    })}

                    {/* Tooltip Overlay (Last Data) */}
                    {chart.lastPoint && (
                      <g transform={`translate(${chart.lastPoint.x - 45}, ${chart.lastPoint.y - 35})`}>
                        <rect width="90" height="24" rx="4" fill="rgba(30,30,30,0.8)" strokeWidth="1" stroke="rgba(255,255,255,0.2)"/>
                        <text x="45" y="16" fill="white" fontSize="11" textAnchor="middle">{formatNumber(growth[growth.length-1].count)} | Hoje</text>
                      </g>
                    )}
                  </>
                )}
              </svg>
            </div>
          </GlassCard>

          {/* TABLE CARD */}
          <GlassCard className="mb-4 mb-lg-0">
            <div className="d-flex justify-content-between align-items-center mb-3">
              <h6 className="fw-semibold text-white mb-0 text-uppercase" style={{fontSize: '0.85rem', letterSpacing: '0.05em'}}>Tenants Mais Ativos (Requisições)</h6>
              <div className="text-white-50">...</div>
            </div>
            
            <table className="omni-table">
              <thead>
                <tr>
                  <th>Tenant</th>
                  <th>Requisições</th>
                  <th>Tokens Usados</th>
                  <th>ID</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {distLoading ? (
                  <tr><td colSpan={5} className="text-center py-4 text-white-50">Carregando métricas...</td></tr>
                ) : (distribution.length > 0 ? (
                  distribution.map((item: any) => (
                    <tr key={item.tenant_id}>
                      <td className="text-white">{item.name}</td>
                      <td>{formatNumber(item.requests)}</td>
                      <td>{formatNumber(item.tokens)}</td>
                      <td style={{fontSize: '0.7rem', opacity: 0.6}}>{item.tenant_id}</td>
                      <td><span className="badge-status-green">Ativo</span></td>
                    </tr>
                  ))
                ) : (
                  <tr><td colSpan={5} className="text-center py-4 text-white-50">Nenhuma atividade registrada.</td></tr>
                ))}
              </tbody>
            </table>
          </GlassCard>
        </div>

        {/* RIGHT COLUMN: Feed & Donut Chart */}
        <div className="col-lg-4">
          
          {/* FEED CARD */}
          <GlassCard className="mb-4" style={{minHeight: '260px'}}>
            <div className="d-flex justify-content-between mb-3">
              <h6 className="fw-semibold text-white mb-0 text-uppercase" style={{fontSize: '0.85rem', letterSpacing: '0.05em'}}>Atividades em Tempo Real</h6>
              <div className="text-white-50">...</div>
            </div>
            
            <div className="omni-timeline mt-4">
              {feedLoading ? (
                <div className="text-center py-4 text-white-50 small">Monitorando eventos...</div>
              ) : (feed.length > 0 ? (
                feed.map((item: any) => {
                  const timeDiff = Math.floor((new Date().getTime() - new Date(item.timestamp).getTime()) / 1000);
                  const timeStr = timeDiff < 60 ? `${timeDiff}s atrás` : `${Math.floor(timeDiff/60)}m atrás`;
                  
                  return (
                    <div key={item.id} className="timeline-item">
                      <div className="timeline-icon" style={{ background: item.type === 'memory' ? 'rgba(0, 240, 255, 0.1)' : 'rgba(179, 0, 255, 0.1)' }}>
                        {item.icon}
                      </div>
                      <div style={{fontSize: '0.8rem', color: '#e2e8f0', fontWeight: 600}}>{item.title}</div>
                      <div style={{fontSize: '0.75rem', color: 'rgba(255,255,255,0.6)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
                        {item.detail}
                      </div>
                      <div style={{fontSize: '0.65rem', color: 'rgba(0, 240, 255, 0.5)', marginTop: 2}}>{timeStr}</div>
                    </div>
                  );
                })
              ) : (
                <div className="text-center py-4 text-white-50 small">Nenhuma atividade recente.</div>
              ))}
            </div>
          </GlassCard>

          {/* DONUT CHART CARD */}
          <GlassCard>
            <h6 className="fw-semibold text-white mb-4 text-uppercase" style={{fontSize: '0.85rem', letterSpacing: '0.05em'}}>
              <BarChart3 size={14} className="text-omni-purple me-2 inline" />
              Uso por Tenant (Mensagens)
            </h6>
            
            <div className="d-flex align-items-center mb-2">
              <div className="me-4 position-relative" style={{width: '90px', height: '90px'}}>
                <svg width="100%" height="100%" viewBox="0 0 42 42">
                  <circle cx="21" cy="21" r="15.9" fill="transparent" stroke="#1c1f2b" strokeWidth="6"></circle>
                  {distribution.length > 0 ? (() => {
                    const total = distribution.reduce((acc: number, cur: any) => acc + (cur.requests || 0), 0);
                    let currentOffset = 25; // Começa no topo (25%)
                    
                    return distribution.map((item: any, idx: number) => {
                      const count = item.requests || 0;
                      if (count === 0 || total === 0) return null;
                      
                      const percentage = (count / total) * 100;
                      const strokeOffset = currentOffset;
                      currentOffset -= percentage; // Deduz para o próximo segmento
                      
                      const colors = ['#00f0ff', '#4facfe', '#b300ff', '#9c27b0', '#f44336'];
                      return (
                        <circle 
                          key={item.tenant_id}
                          cx="21" cy="21" r="15.9" 
                          fill="transparent" 
                          stroke={colors[idx % colors.length]} 
                          strokeWidth="6" 
                          strokeDasharray={`${percentage} ${100 - percentage}`} 
                          strokeDashoffset={strokeOffset}
                        ></circle>
                      );
                    });
                  })() : (
                    <circle cx="21" cy="21" r="15.9" fill="transparent" stroke="rgba(255,255,255,0.1)" strokeWidth="6"></circle>
                  )}
                </svg>
              </div>
              
              <div className="flex-grow-1">
                {distribution.length > 0 ? (
                  distribution.slice(0, 4).map((item: any, idx: number) => {
                    const colors = ['#00f0ff', '#4facfe', '#b300ff', '#9c27b0', '#f44336'];
                    return (
                      <div key={item.tenant_id} className="d-flex align-items-center justify-content-between gap-2 mb-2">
                        <div className="d-flex align-items-center gap-2">
                          <div style={{width: 8, height: 8, borderRadius: '50%', background: colors[idx % colors.length]}}></div>
                          <span style={{fontSize: '0.7rem', color: 'rgba(255,255,255,0.6)', maxWidth: '80px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
                            {item.name}
                          </span>
                        </div>
                        <span className="font-mono" style={{fontSize: '0.7rem', color: '#fff'}}>{item.requests}</span>
                      </div>
                    );
                  })
                ) : (
                  <div className="text-white-50 small">Nenhum dado disponível</div>
                )}
              </div>
            </div>
          </GlassCard>

        </div>
      </div>
    </div>
  );
}
