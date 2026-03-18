'use client';

import React, { useEffect, useState } from 'react';
import useSWR from 'swr';
import { fetchApi } from '@/lib/api';

export default function EnhancedDashboard() {
  const [date, setDate] = useState('');

  useEffect(() => {
    const now = new Date();
    setDate(now.toLocaleDateString('pt-BR', { month: 'short', day: 'numeric', year: 'numeric' }) + ' | ' + 
            now.toLocaleTimeString('pt-BR', { hour: 'numeric', minute: '2-digit' }) + ' BRT');
  }, []);

  return (
    <div className="container-fluid p-0 animate-in fade-in duration-700">
      
      {/* HEADER */}
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h1 className="dash-title mb-0">PAINEL DE VISÃO GERAL</h1>
          <div className="dash-subtitle mt-1">{date || '26 Out, 2023 | 10:15 AM BRT'}</div>
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
          <div className="glass-panel h-100">
            <div className="kpi-label">1. TOTAL DE MEMÓRIAS</div>
            <div className="d-flex align-items-baseline">
              <span className="kpi-value">7.2M</span>
              <span className="kpi-perc">+12.4%</span>
            </div>
          </div>
        </div>
        <div className="col-md-4">
          <div className="glass-panel h-100">
            <div className="kpi-label">2. AGENTES DE IA ATIVOS</div>
            <div className="d-flex align-items-baseline">
              <span className="kpi-value">458</span>
              <span className="kpi-perc">+3%</span>
            </div>
          </div>
        </div>
        <div className="col-md-4">
          <div className="glass-panel h-100">
            <div className="kpi-label">3. SESSÕES SIMULTÂNEAS</div>
            <div className="d-flex align-items-baseline">
              <span className="kpi-value">1.894</span>
              <span className="kpi-perc">+8%</span>
            </div>
          </div>
        </div>
      </div>

      {/* MAIN DATA ROW */}
      <div className="row">
        
        {/* LEFT COLUMN: Line Chart + Top Agents Table */}
        <div className="col-lg-8">
          
          {/* GRADIENT BORDERED CHART CARD */}
          <div className="glass-panel neon-bordered mb-4" style={{ minHeight: '340px' }}>
            <div className="d-flex justify-content-between mb-2">
              <div className="fw-semibold text-white d-flex align-items-center gap-2">
                <span style={{color: '#00f0ff'}}>📈</span> CRESCIMENTO DA MEMÓRIA
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
                {[100, 250, 400, 550, 700, 850].map((x, i) => (
                  <line key={i} x1={x} y1="0" x2={x} y2="250" stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
                ))}
                
                {/* The Path */}
                <path d="M 50,220 C 150,150 200,200 350,180 C 450,170 480,80 550,110 C 650,150 780,40 850,50 L 850,250 L 50,250 Z" fill="url(#areaGlow)" />
                <path d="M 50,220 C 150,150 200,200 350,180 C 450,170 480,80 550,110 C 650,150 780,40 850,50" fill="none" stroke="url(#glowLine)" strokeWidth="4" filter="drop-shadow(0px 4px 6px rgba(0,240,255,0.4))" />
                
                {/* Active Point */}
                <circle cx="850" cy="50" r="6" fill="#fff" stroke="#b300ff" strokeWidth="3" filter="drop-shadow(0px 0px 8px #b300ff)" />
                
                {/* Labels Y */}
                <text x="40" y="10" fill="rgba(255,255,255,0.5)" fontSize="12" textAnchor="end">7.2M</text>
                <text x="40" y="90" fill="rgba(255,255,255,0.5)" fontSize="12" textAnchor="end">1.2M</text>
                <text x="40" y="170" fill="rgba(255,255,255,0.5)" fontSize="12" textAnchor="end">5M</text>
                <text x="40" y="250" fill="rgba(255,255,255,0.5)" fontSize="12" textAnchor="end">3M</text>
                <text x="40" y="290" fill="rgba(255,255,255,0.5)" fontSize="12" textAnchor="end">0</text>
                {/* Labels X */}
                <text x="80" y="280" fill="rgba(255,255,255,0.5)" fontSize="12">26 Out</text>
                <text x="230" y="280" fill="rgba(255,255,255,0.5)" fontSize="12">18 Out</text>
                <text x="380" y="280" fill="rgba(255,255,255,0.5)" fontSize="12">20 Out</text>
                <text x="530" y="280" fill="rgba(255,255,255,0.5)" fontSize="12">22 Out</text>
                <text x="680" y="280" fill="rgba(255,255,255,0.5)" fontSize="12">24 Out</text>
                <text x="830" y="280" fill="rgba(255,255,255,0.5)" fontSize="12">26 Out</text>
                <text x="960" y="280" fill="rgba(255,255,255,0.5)" fontSize="12">28 Out</text>

                {/* Tooltip Overlay */}
                <g transform="translate(760, 20)">
                  <rect width="90" height="24" rx="4" fill="rgba(30,30,30,0.8)" strokeWidth="1" stroke="rgba(255,255,255,0.2)"/>
                  <text x="45" y="16" fill="white" fontSize="11" textAnchor="middle">7.2M | 26 Out</text>
                </g>
              </svg>
            </div>
          </div>

          {/* TABLE CARD */}
          <div className="glass-panel mb-4 mb-lg-0">
            <div className="d-flex justify-content-between align-items-center mb-3">
              <h6 className="fw-semibold text-white mb-0 text-uppercase" style={{fontSize: '0.85rem', letterSpacing: '0.05em'}}>Desempenho dos Principais Agentes</h6>
              <div className="text-white-50">...</div>
            </div>
            
            <table className="omni-table">
              <thead>
                <tr>
                  <th>Agente</th>
                  <th>Requisições</th>
                  <th>Latência</th>
                  <th>Memória</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="text-white">Nova</td>
                  <td>37</td>
                  <td>45s</td>
                  <td>12.7 MB</td>
                  <td><span className="badge-status-green">Ativo</span></td>
                </tr>
                <tr>
                  <td className="text-white">Astra</td>
                  <td>23</td>
                  <td>30s</td>
                  <td>29.3 MB</td>
                  <td><span className="badge-status-green">Ativo</span></td>
                </tr>
                <tr>
                  <td className="text-white">Kai</td>
                  <td>10</td>
                  <td>20s</td>
                  <td>12.0 MB</td>
                  <td><span className="badge-status-green">Ativo</span></td>
                </tr>
                <tr>
                  <td className="text-white">Nexus</td>
                  <td>9</td>
                  <td>20s</td>
                  <td>32.9 MB</td>
                  <td><span className="badge-status-green">Ativo</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* RIGHT COLUMN: Feed & Donut Chart */}
        <div className="col-lg-4">
          
          {/* FEED CARD */}
          <div className="glass-panel mb-4" style={{minHeight: '260px'}}>
            <div className="d-flex justify-content-between mb-3">
              <h6 className="fw-semibold text-white mb-0 text-uppercase" style={{fontSize: '0.85rem', letterSpacing: '0.05em'}}>Atividades em Tempo Real</h6>
              <div className="text-white-50">...</div>
            </div>
            
            <div className="omni-timeline mt-4">
              <div className="timeline-item">
                <div className="timeline-icon icon-blue">🧠</div>
                <div style={{fontSize: '0.8rem', color: '#e2e8f0'}}>Memória de IA Armazenada:</div>
                <div style={{fontSize: '0.8rem', color: '#e2e8f0'}}>Sessão #A408</div>
                <div style={{fontSize: '0.65rem', color: 'rgba(255,255,255,0.4)', marginTop: 2}}>12s atrás</div>
              </div>
              
              <div className="timeline-item">
                <div className="timeline-icon icon-cyan">💬</div>
                <div style={{fontSize: '0.8rem', color: '#e2e8f0'}}>Sessão Iniciada:</div>
                <div style={{fontSize: '0.8rem', color: '#e2e8f0'}}>Agente Nova</div>
                <div style={{fontSize: '0.65rem', color: 'rgba(255,255,255,0.4)', marginTop: 2}}>21s atrás</div>
              </div>

              <div className="timeline-item">
                <div className="timeline-icon icon-purple">🧠</div>
                <div style={{fontSize: '0.8rem', color: '#e2e8f0'}}>Contexto Atualizado:</div>
                <div style={{fontSize: '0.8rem', color: '#e2e8f0'}}>Agente Kai</div>
                <div style={{fontSize: '0.65rem', color: 'rgba(255,255,255,0.4)', marginTop: 2}}>35s atrás</div>
              </div>
            </div>
          </div>

          {/* DONUT CHART CARD */}
          <div className="glass-panel">
            <h6 className="fw-semibold text-white mb-4 text-uppercase" style={{fontSize: '0.85rem', letterSpacing: '0.05em'}}>Uso de Memória por Tipo</h6>
            
            <div className="d-flex align-items-center mb-2">
              <div className="me-4 position-relative" style={{width: '90px', height: '90px'}}>
                <svg width="100%" height="100%" viewBox="0 0 42 42">
                  <circle cx="21" cy="21" r="15.9" fill="transparent" stroke="#1c1f2b" strokeWidth="6"></circle>
                  <circle cx="21" cy="21" r="15.9" fill="transparent" stroke="#00f0ff" strokeWidth="6" strokeDasharray="30 70" strokeDashoffset="25"></circle>
                  <circle cx="21" cy="21" r="15.9" fill="transparent" stroke="#4facfe" strokeWidth="6" strokeDasharray="20 80" strokeDashoffset="-5"></circle>
                  <circle cx="21" cy="21" r="15.9" fill="transparent" stroke="#b300ff" strokeWidth="6" strokeDasharray="40 60" strokeDashoffset="-25"></circle>
                </svg>
              </div>
              
              <div>
                <div className="d-flex align-items-center gap-2 mb-2">
                  <div style={{width: 8, height: 8, borderRadius: '50%', background: '#00f0ff'}}></div>
                  <span style={{fontSize: '0.75rem', color: 'rgba(255,255,255,0.6)'}}>Curto Prazo</span>
                </div>
                <div className="d-flex align-items-center gap-2 mb-2">
                  <div style={{width: 8, height: 8, borderRadius: '50%', background: '#4facfe'}}></div>
                  <span style={{fontSize: '0.75rem', color: 'rgba(255,255,255,0.6)'}}>Longo Prazo</span>
                </div>
                <div className="d-flex align-items-center gap-2 mb-2">
                  <div style={{width: 8, height: 8, borderRadius: '50%', background: '#b300ff'}}></div>
                  <span style={{fontSize: '0.75rem', color: 'rgba(255,255,255,0.6)'}}>Semântica</span>
                </div>
                <div className="d-flex align-items-center gap-2">
                  <div style={{width: 8, height: 8, borderRadius: '50%', background: '#9c27b0'}}></div>
                  <span style={{fontSize: '0.75rem', color: 'rgba(255,255,255,0.6)'}}>Contexto</span>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
