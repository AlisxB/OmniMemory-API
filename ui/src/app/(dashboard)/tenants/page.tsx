'use client';
import { useState, useEffect } from 'react';
import useSWR, { mutate } from 'swr';
import { fetchApi } from '@/lib/api';
import { 
  Plus, X, Shield, Activity, HardDrive, 
  RefreshCcw, Globe, AlertTriangle, CheckCircle2,
  TrendingUp, Users, Cpu
} from 'lucide-react';

export default function TenantsPage() {
  const { data, error, isLoading } = useSWR('/admin/api/tenants', fetchApi, { refreshInterval: 10000 });
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [rotatedKey, setRotatedKey] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [newTenant, setNewTenant] = useState({
    tenant_id: '',
    name: '',
    buffer_window: 60,
    rate_limit: 100
  });

  if (isLoading) return <div className="text-omni-neon animate-pulse text-lg p-5 font-mono">📡 Sincronizando com a malha central...</div>;
  if (error) return <div className="text-omni-accent font-mono p-5">🚨 Falha na comunicação: {error.message}</div>;

  const tenants = data?.tenants || [];
  const stats = {
    total: tenants.length,
    active: tenants.filter((t: any) => t.is_active).length,
    totalTokens: tenants.reduce((acc: number, t: any) => acc + (t.stats?.tokens || 0), 0)
  };

  const filtered = tenants.filter((t: any) => 
    t.tenant_id.toLowerCase().includes(searchTerm.toLowerCase()) || 
    t.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      const res = await fetchApi('/admin/api/tenants', {
        method: 'POST',
        body: JSON.stringify({
          id: newTenant.tenant_id,
          name: newTenant.name,
          settings: {
            buffer_window_seconds: newTenant.buffer_window,
            rate_limit_rpm: newTenant.rate_limit
          }
        })
      });
      mutate('/admin/api/tenants');
      setIsModalOpen(false);
      if (res?.data?.api_key) setRotatedKey(res.data.api_key);
      setNewTenant({ tenant_id: '', name: '', buffer_window: 60, rate_limit: 100 });
    } catch (err: any) {
      alert('Erro ao criar tenant: ' + err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const rotateKey = async (id: string) => {
    if (!confirm(`Deseja REALMENTE rotacionar a chave de ${id}? A chave antiga será invalidada imediatamente.`)) return;
    try {
      const res = await fetchApi(`/admin/api/tenants/${id}/rotate-key`, { method: 'POST' });
      setRotatedKey(res.data.api_key);
      mutate('/admin/api/tenants');
    } catch (err: any) {
      alert('Erro ao rotacionar chave: ' + err.message);
    }
  };

  const syncWebhook = async (id: string) => {
    const url = prompt("Digite a URL do Webhook (n8n/Endpoint):");
    if (!url) return;
    try {
      await fetchApi(`/admin/api/tenants/${id}/webhooks/sync`, {
        method: 'POST',
        body: JSON.stringify({ webhook_url: url })
      });
      alert('Webhook sincronizado com sucesso!');
      mutate('/admin/api/tenants');
    } catch (err: any) {
      alert('Erro na sincronização: ' + err.message);
    }
  };

  return (
    <div className="container-fluid p-0 animate-in fade-in duration-700 pb-5">
      
      {/* HEADER */}
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h1 className="dash-title mb-0">CENTRAL DE TENANTS</h1>
          <div className="dash-subtitle mt-1">Gerencie chaves, limites e instâncias da rede OmniMemory.</div>
        </div>
        <button 
          onClick={() => setIsModalOpen(true)}
          className="btn btn-sm px-4 py-2 font-bold flex align-items-center gap-2"
          style={{backgroundColor: '#00f0ff', color: '#000', borderRadius: '8px', border: 'none'}}
        >
          <Plus size={16} /> NOVO TENANT
        </button>
      </div>

      {/* KPI ROW */}
      <div className="row mb-4">
        <div className="col-md-4">
          <div className="glass-panel h-100">
            <div className="kpi-label">TOTAL DE CLIENTES</div>
            <div className="d-flex align-items-baseline">
              <span className="kpi-value">{stats.total}</span>
              <span className="kpi-perc">+0%</span>
            </div>
          </div>
        </div>
        <div className="col-md-4">
          <div className="glass-panel h-100">
            <div className="kpi-label">INSTÂNCIAS ATIVAS</div>
            <div className="d-flex align-items-baseline">
              <span className="kpi-value text-success">{stats.active}</span>
              <span className="kpi-perc">+0%</span>
            </div>
          </div>
        </div>
        <div className="col-md-4">
          <div className="glass-panel h-100">
            <div className="kpi-label">CONSUMO TOTAL (TOKENS)</div>
            <div className="d-flex align-items-baseline">
              <span className="kpi-value" style={{fontSize: '1.8rem'}}>{(stats.totalTokens / 1000).toFixed(1)}k</span>
              <span className="ms-2 text-white-50" style={{fontSize: '0.8rem'}}>TKS</span>
            </div>
          </div>
        </div>
      </div>

      {/* MAIN DATA ROW */}
      <div className="glass-panel p-0 overflow-hidden">
        <div className="p-3 d-flex justify-content-between align-items-center border-bottom border-white-10 bg-white-5">
          <div className="position-relative" style={{width: '300px'}}>
            <input 
              type="text" 
              placeholder="🔍 Filtrar ID ou nome..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="form-control form-control-sm bg-transparent border-white-10 text-white"
              style={{borderRadius: '8px'}}
            />
          </div>
          <div className="text-omni-label opacity-50 m-0">Sincronizado via Rede Neural</div>
        </div>

        <div className="table-responsive">
          <table className="omni-table mb-0">
            <thead>
              <tr>
                <th>Identificação</th>
                <th>Status / Saúde</th>
                <th>Configurações</th>
                <th>API Key (Sufixo)</th>
                <th className="text-end">Comandos</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((tenant: any) => (
                <tr key={tenant.tenant_id}>
                  <td>
                    <div className="fw-bold text-white mb-0">{tenant.tenant_id}</div>
                    <div style={{fontSize: '0.7rem', color: 'rgba(255,255,255,0.4)'}}>{tenant.name}</div>
                  </td>
                  <td>
                    {tenant.is_active ? 
                      <span className="badge-status-green">Ativo</span> : 
                      <span className="badge bg-danger bg-opacity-10 text-danger border border-danger border-opacity-20" style={{fontSize: '0.65rem'}}>Inativo</span>
                    }
                  </td>
                  <td>
                    <div className="d-flex gap-3 font-mono" style={{fontSize: '0.75rem'}}>
                      <span className="text-white-50"><Activity size={12} className="me-1 text-omni-neon" />{tenant.settings?.buffer_window_seconds ?? 0}s</span>
                      <span className="text-white-50"><HardDrive size={12} className="me-1 text-omni-purple" />{tenant.settings?.rate_limit_rpm ?? '∞'} <span style={{fontSize: '0.6rem'}}>RPM</span></span>
                    </div>
                  </td>
                  <td>
                    <code style={{fontSize: '0.7rem', color: '#00f0ff', opacity: 0.7}}>••••{tenant.api_key_info?.suffix || '????'}</code>
                    <div style={{fontSize: '0.65rem', color: 'rgba(255,255,255,0.3)'}}>{tenant.api_key_info?.age_days ?? '?'} dias</div>
                  </td>
                  <td className="text-end">
                    <div className="d-flex gap-2 justify-content-end">
                      <button onClick={() => syncWebhook(tenant.tenant_id)} className="btn btn-sm btn-outline-light border-white-10 opacity-50 hover-opacity-100 p-1 px-2"><Globe size={14} /></button>
                      <button onClick={() => rotateKey(tenant.tenant_id)} className="btn btn-sm btn-outline-warning border-white-10 opacity-50 hover-opacity-100 p-1 px-2"><RefreshCcw size={14} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* MODAL: EXIBIÇÃO DE CHAVE */}
      {rotatedKey && (
        <div className="position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center z-3" style={{backgroundColor: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(8px)'}}>
          <div className="glass-panel" style={{maxWidth: '400px', width: '90%'}}>
            <h5 className="text-omni-neon mb-3 flex items-center gap-2"><Shield size={20} /> CHAVE GERADA</h5>
            <p style={{fontSize: '0.8rem', color: 'rgba(255,255,255,0.7)'}}>Copie agora. Por segurança, esta chave **não será exibida novamente**.</p>
            <div className="bg-black bg-opacity-50 p-3 rounded mb-4 font-mono text-omni-neon" style={{fontSize: '0.8rem', wordBreak: 'break-all'}}>
              {rotatedKey}
            </div>
            <button onClick={() => setRotatedKey(null)} className="btn w-100 py-2 font-bold" style={{backgroundColor: '#00f0ff', color: '#000', borderRadius: '8px'}}>SALVEI COM SEGURANÇA</button>
          </div>
        </div>
      )}

      {/* MODAL: NOVO TENANT */}
      {isModalOpen && (
        <div className="position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center z-3" style={{backgroundColor: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)'}}>
          <div className="glass-panel" style={{maxWidth: '500px', width: '90%'}}>
            <div className="d-flex justify-content-between align-items-center mb-4">
              <h5 className="mb-0 text-white font-bold">NOVO REGISTRO</h5>
              <button onClick={() => setIsModalOpen(false)} className="btn text-white-50 p-0"><X size={20} /></button>
            </div>
            <form onSubmit={handleCreate}>
              <div className="mb-3">
                <label className="kpi-label mb-1">ID do Tenant (Slug)</label>
                <input required value={newTenant.tenant_id} onChange={e => setNewTenant({...newTenant, tenant_id: e.target.value.toLowerCase().replace(/\s+/g, '_')})} className="form-control bg-transparent border-white-10 text-white py-2" style={{borderRadius: '8px'}} placeholder="ex: michel_vereador" />
              </div>
              <div className="mb-3">
                <label className="kpi-label mb-1">Nome Comercial</label>
                <input required value={newTenant.name} onChange={e => setNewTenant({...newTenant, name: e.target.value})} className="form-control bg-transparent border-white-10 text-white py-2" style={{borderRadius: '8px'}} placeholder="Ex: Gabinete Michel" />
              </div>
              <div className="row mb-4">
                <div className="col-6">
                  <label className="kpi-label mb-1">Buffer (Seg)</label>
                  <input type="number" value={newTenant.buffer_window} onChange={e => setNewTenant({...newTenant, buffer_window: parseInt(e.target.value)})} className="form-control bg-transparent border-white-10 text-white py-2" style={{borderRadius: '8px'}} />
                </div>
                <div className="col-6">
                  <label className="kpi-label mb-1">Limites (RPM)</label>
                  <input type="number" value={newTenant.rate_limit} onChange={e => setNewTenant({...newTenant, rate_limit: parseInt(e.target.value)})} className="form-control bg-transparent border-white-10 text-white py-2" style={{borderRadius: '8px'}} />
                </div>
              </div>
              <button type="submit" disabled={isSubmitting} className="btn w-100 py-2 font-bold" style={{backgroundColor: '#00f0ff', color: '#000', borderRadius: '8px'}}>CONFIRMAR REGISTRO</button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
