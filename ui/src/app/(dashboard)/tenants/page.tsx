'use client';
import { useState, useEffect } from 'react';
import useSWR, { mutate } from 'swr';
import { fetchApi } from '@/lib/api';
import { 
  Plus, X, Shield, Activity, HardDrive, 
  RefreshCcw, Globe, AlertTriangle, CheckCircle2,
  TrendingUp, Users, Cpu, Trash2, Edit3
} from 'lucide-react';

export default function TenantsPage() {
  const { data: rawData, error, isLoading } = useSWR('/admin/api/tenants', fetchApi, { refreshInterval: 10000 });
  const { data: statsData } = useSWR('/admin/api/analytics/system-stats', fetchApi, { refreshInterval: 15000 });
  
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [rotatedKey, setRotatedKey] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{message: string, type: 'success' | 'error'} | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  
  const [newTenant, setNewTenant] = useState({
    id: '',
    name: '',
    buffer_window: 60,
    rate_limit: 100,
    is_active: true
  });

  const formatNumber = (num: number) => {
    if (num === undefined || num === null) return '0';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
  };

  if (isLoading) return <div className="text-omni-neon animate-pulse text-lg p-5 font-mono">📡 Sincronizando com a malha central...</div>;
  if (error) return <div className="text-omni-accent font-mono p-5">🚨 Falha na comunicação: {error.message}</div>;

  const tenants = rawData?.data || [];
  const systemStats = statsData?.data || { total_tenants: 0, active_sessions: 0, total_tokens: 0 };

  const stats = {
    total: systemStats.total_tenants || tenants.length,
    activeSessions: systemStats.active_sessions || 0,
    totalTokens: systemStats.total_tokens || 0
  };

  const filtered = tenants.filter((t: any) => 
    t.id.toLowerCase().includes(searchTerm.toLowerCase()) || 
    t.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleCreateOrUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFeedback(null);
    try {
      if (isEditing) {
        await fetchApi(`/admin/api/tenants/${newTenant.id}`, {
          method: 'PATCH',
          body: JSON.stringify({
            name: newTenant.name,
            is_active: newTenant.is_active,
            settings: {
              buffer_window_seconds: newTenant.buffer_window,
              rate_limit_rpm: newTenant.rate_limit
            }
          })
        });
        setFeedback({ message: `Tenant ${newTenant.id} atualizado com sucesso.`, type: 'success' });
      } else {
        const res = await fetchApi('/admin/api/tenants', {
          method: 'POST',
          body: JSON.stringify({
            id: newTenant.id,
            name: newTenant.name,
            settings: {
              buffer_window_seconds: newTenant.buffer_window,
              rate_limit_rpm: newTenant.rate_limit
            }
          })
        });
        if (res?.data?.api_key) setRotatedKey(res.data.api_key);
        setFeedback({ message: `Tenant ${newTenant.id} criado com sucesso.`, type: 'success' });
      }
      mutate('/admin/api/tenants');
      setIsModalOpen(false);
      resetForm();
    } catch (err: any) {
      setFeedback({ message: `Erro ao ${isEditing ? 'atualizar' : 'criar'} tenant: ` + err.message, type: 'error' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    const adminKey = prompt(`Para deletar ${id}, digite a Chave de Super Admin:`);
    if (!adminKey) return;
    
    if (!confirm(`TEM CERTEZA? Esta ação é irreversível e todos os dados de ${id} serão perdidos.`)) return;
    
    setFeedback(null);
    try {
      await fetchApi(`/admin/api/tenants/${id}`, {
        method: 'DELETE',
        headers: { 'X-Super-Admin-Key': adminKey }
      });
      setFeedback({ message: `Tenant ${id} removido da malha.`, type: 'success' });
      mutate('/admin/api/tenants');
    } catch (err: any) {
      setFeedback({ message: 'Erro ao deletar tenant: ' + err.message, type: 'error' });
    }
  };

  const openEdit = (tenant: any) => {
    setNewTenant({
      id: tenant.id,
      name: tenant.name,
      buffer_window: tenant.settings?.buffer_window_seconds || 60,
      rate_limit: tenant.settings?.rate_limit_rpm || 100,
      is_active: tenant.is_active
    });
    setIsEditing(true);
    setIsModalOpen(true);
  };

  const resetForm = () => {
    setNewTenant({ id: '', name: '', buffer_window: 60, rate_limit: 100, is_active: true });
    setIsEditing(false);
  };

  const rotateKey = async (id: string) => {
    const adminKey = prompt(`Digite a Chave de Super Admin para rotacionar a chave de ${id}:`);
    if (!adminKey) return;

    if (!confirm(`Deseja REALMENTE rotacionar a chave de ${id}? A chave antiga será invalidada imediatamente.`)) return;
    try {
      const res = await fetchApi(`/admin/api/tenants/${id}/rotate-key`, { 
        method: 'POST',
        headers: { 'X-Super-Admin-Key': adminKey }
      });
      setRotatedKey(res.data.api_key);
      mutate('/admin/api/tenants');
      setFeedback({ message: 'Chave rotacionada com sucesso.', type: 'success' });
    } catch (err: any) {
      setFeedback({ message: 'Erro ao rotacionar chave: ' + err.message, type: 'error' });
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

      {feedback && (
        <div className={`alert ${feedback.type === 'success' ? 'alert-success bg-success bg-opacity-10 border-success' : 'alert-danger bg-danger bg-opacity-10 border-danger'} text-white mb-4 animate-in slide-in-from-top duration-300`} style={{fontSize: '0.8rem', borderRadius: '8px'}}>
          {feedback.message}
        </div>
      )}

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
            <div className="kpi-label">SESSÕES ATIVAS</div>
            <div className="d-flex align-items-baseline">
              <span className="kpi-value text-omni-neon">{stats.activeSessions}</span>
              <span className="kpi-perc text-white-50 ms-2" style={{fontSize: '0.7rem'}}>Live</span>
            </div>
          </div>
        </div>
        <div className="col-md-4">
          <div className="glass-panel h-100">
            <div className="kpi-label">CONSUMO TOTAL (TOKENS)</div>
            <div className="d-flex align-items-baseline">
              <span className="kpi-value" style={{fontSize: '1.8rem'}}>{formatNumber(stats.totalTokens)}</span>
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
                <tr key={tenant.id}>
                  <td>
                    <div className="fw-bold text-white mb-0">{tenant.id}</div>
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
                      <button onClick={() => openEdit(tenant)} className="btn btn-sm btn-outline-info border-white-10 opacity-50 hover-opacity-100 p-1 px-2"><Edit3 size={14} /></button>
                      <button onClick={() => syncWebhook(tenant.id)} className="btn btn-sm btn-outline-light border-white-10 opacity-50 hover-opacity-100 p-1 px-2"><Globe size={14} /></button>
                      <button onClick={() => rotateKey(tenant.id)} className="btn btn-sm btn-outline-warning border-white-10 opacity-50 hover-opacity-100 p-1 px-2"><RefreshCcw size={14} /></button>
                      <button onClick={() => handleDelete(tenant.id)} className="btn btn-sm btn-outline-danger border-white-10 opacity-50 hover-opacity-100 p-1 px-2"><Trash2 size={14} /></button>
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

      {/* MODAL: NOVO/EDITAR TENANT */}
      {isModalOpen && (
        <div className="position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center z-3" style={{backgroundColor: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)'}}>
          <div className="glass-panel" style={{maxWidth: '500px', width: '90%'}}>
            <div className="d-flex justify-content-between align-items-center mb-4">
              <h5 className="mb-0 text-white font-bold">{isEditing ? 'EDITAR REGISTRO' : 'NOVO REGISTRO'}</h5>
              <button onClick={() => { setIsModalOpen(false); resetForm(); }} className="btn text-white-50 p-0"><X size={20} /></button>
            </div>
            <form onSubmit={handleCreateOrUpdate}>
              <div className="mb-3">
                <label className="kpi-label mb-1">ID do Tenant (Slug)</label>
                <input 
                  required 
                  disabled={isEditing}
                  value={newTenant.id} 
                  onChange={e => setNewTenant({...newTenant, id: e.target.value.toLowerCase().replace(/\s+/g, '_')})} 
                  className={`form-control bg-transparent border-white-10 text-white py-2 ${isEditing ? 'opacity-50' : ''}`} 
                  style={{borderRadius: '8px'}} 
                  placeholder="ex: michel_vereador" 
                />
              </div>
              <div className="mb-3">
                <label className="kpi-label mb-1">Nome Comercial</label>
                <input required value={newTenant.name} onChange={e => setNewTenant({...newTenant, name: e.target.value})} className="form-control bg-transparent border-white-10 text-white py-2" style={{borderRadius: '8px'}} placeholder="Ex: Gabinete Michel" />
              </div>
              <div className="row mb-3">
                <div className="col-6">
                  <label className="kpi-label mb-1">Buffer (Seg)</label>
                  <input type="number" value={newTenant.buffer_window} onChange={e => setNewTenant({...newTenant, buffer_window: parseInt(e.target.value)})} className="form-control bg-transparent border-white-10 text-white py-2" style={{borderRadius: '8px'}} />
                </div>
                <div className="col-6">
                  <label className="kpi-label mb-1">Limites (RPM)</label>
                  <input type="number" value={newTenant.rate_limit} onChange={e => setNewTenant({...newTenant, rate_limit: parseInt(e.target.value)})} className="form-control bg-transparent border-white-10 text-white py-2" style={{borderRadius: '8px'}} />
                </div>
              </div>

              {isEditing && (
                <div className="mb-4 d-flex align-items-center gap-2">
                  <input 
                    type="checkbox" 
                    id="is_active"
                    checked={newTenant.is_active} 
                    onChange={e => setNewTenant({...newTenant, is_active: e.target.checked})}
                    className="form-check-input bg-transparent border-white-10"
                  />
                  <label htmlFor="is_active" className="kpi-label mb-0 cursor-pointer">Instância Ativa</label>
                </div>
              )}

              <button type="submit" disabled={isSubmitting} className="btn w-100 py-2 font-bold" style={{backgroundColor: '#00f0ff', color: '#000', borderRadius: '8px'}}>
                {isSubmitting ? 'PROCESSANDO...' : (isEditing ? 'SALVAR ALTERAÇÕES' : 'CONFIRMAR REGISTRO')}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
