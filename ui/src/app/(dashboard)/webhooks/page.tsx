'use client';
import { useState } from 'react';
import useSWR, { mutate } from 'swr';
import { fetchApi } from '@/lib/api';
import { 
  Webhook, Plus, Globe, Shield, Trash2, 
  Activity, Zap, Info, CheckCircle2, AlertTriangle,
  RefreshCcw, Link2, Key, X
} from 'lucide-react';

export default function WebhooksPage() {
  const [tenantId, setTenantId] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  
  const { data: tenantsData } = useSWR('/admin/api/tenants', fetchApi);
  const tenants = tenantsData?.tenants || [];

  const { data: webhooksData, error, isLoading } = useSWR(
    tenantId ? `/admin/api/tenants/${tenantId}/webhooks` : null, 
    fetchApi
  );

  const webhooks = webhooksData?.webhooks || [];

  const handleDelete = async (webhookId: string) => {
    if (!confirm('Deseja remover esta rota de webhook permanentemente?')) return;
    try {
      await fetchApi(`/admin/api/tenants/${tenantId}/webhooks/${webhookId}`, { method: 'DELETE' });
      mutate(`/admin/api/tenants/${tenantId}/webhooks`);
    } catch (err: any) {
      alert('Erro ao remover webhook: ' + err.message);
    }
  };

  return (
    <div className="container-fluid p-0 animate-in fade-in duration-700 pb-5">
      
      {/* HEADER */}
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h1 className="dash-title mb-0">GERENCIADOR DE WEBHOOKS</h1>
          <div className="dash-subtitle mt-1">Configure N8N e integrações externas em tempo real.</div>
        </div>
        <button 
          disabled={!tenantId}
          onClick={() => setIsModalOpen(true)}
          className="btn btn-sm px-4 py-2 font-bold flex align-items-center gap-2"
          style={{backgroundColor: '#00f0ff', color: '#000', borderRadius: '8px', border: 'none', opacity: !tenantId ? 0.3 : 1}}
        >
          <Plus size={16} /> NOVA ROTA
        </button>
      </div>

      {/* FILTER ROW */}
      <div className="glass-panel mb-4 py-3">
        <div className="row align-items-center">
          <div className="col-auto">
            <div className="kpi-label mb-0 d-flex align-items-center gap-2">
              <Globe size={14} className="text-omni-neon" /> FILTRAR POR CLIENTE:
            </div>
          </div>
          <div className="col">
            <select 
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              className="form-control bg-transparent border-white-10 text-white font-bold"
              style={{borderRadius: '8px', appearance: 'none', maxWidth: '400px'}}
            >
              <option value="" className="bg-omni-bg">Selecione o Tenant para ver Webhooks</option>
              {tenants.map((t: any) => (
                <option key={t.tenant_id} value={t.tenant_id} className="bg-omni-bg">{t.name} ({t.tenant_id})</option>
              ))}
            </select>
          </div>
          {!tenantId && (
            <div className="col-auto ms-auto d-none d-md-block">
              <div className="text-omni-purple opacity-75 font-bold" style={{fontSize: '0.65rem', letterSpacing: '0.1em'}}>
                <Zap size={14} className="me-1 animate-pulse" /> SELECIONE UM TENANT PARA GERENCIAR
              </div>
            </div>
          )}
        </div>
      </div>

      {/* DATA LIST */}
      <div className="glass-panel p-0 overflow-hidden min-h-[400px]">
        {!tenantId ? (
          <div className="d-flex flex-column align-items-center justify-content-center h-100 py-5 opacity-25">
            <Webhook size={64} className="mb-4" />
            <h5 className="font-bold">Aguardando Seleção</h5>
            <p className="small">Escolha um cliente acima para visualizar as rotas de integração.</p>
          </div>
        ) : isLoading ? (
          <div className="d-flex flex-column align-items-center justify-content-center h-100 py-5 gap-3">
            <RefreshCcw size={32} className="animate-spin text-omni-neon" />
            <div className="text-omni-label animate-pulse">Varrendo Malha Neural...</div>
          </div>
        ) : error ? (
          <div className="d-flex flex-column align-items-center justify-content-center h-100 py-5 text-omni-accent gap-2">
            <AlertTriangle size={48} />
            <div className="fw-bold">Falha na Sincronização</div>
            <div className="small opacity-60">{error.message}</div>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="omni-table mb-0">
              <thead>
                <tr>
                  <th>Endpoint (URL)</th>
                  <th>Status / Pulso</th>
                  <th>Eventos de Gatilho</th>
                  <th>Segredo</th>
                  <th className="text-end">Ações</th>
                </tr>
              </thead>
              <tbody>
                {webhooks.map((wh: any) => (
                  <tr key={wh.id} className="align-middle">
                    <td>
                      <div className="d-flex align-items-center gap-3">
                        <div className="p-2 rounded bg-white-5 text-omni-neon"><Link2 size={16} /></div>
                        <div>
                          <div className="fw-bold text-white truncate mb-0" style={{maxWidth: '250px'}}>{wh.url}</div>
                          <div style={{fontSize: '0.6rem', color: 'rgba(255,255,255,0.3)'}} className="font-mono">ID: {wh.id.slice(0, 8)}</div>
                        </div>
                      </div>
                    </td>
                    <td>
                      {wh.is_active ? 
                        <span className="badge-status-green">Escutando</span> : 
                        <span className="badge bg-danger bg-opacity-10 text-danger border border-danger border-opacity-20" style={{fontSize: '0.65rem'}}>Pausado</span>
                      }
                    </td>
                    <td>
                      <div className="d-flex flex-wrap gap-1">
                        {wh.events.map((e: string) => (
                          <span key={e} className="badge bg-purple bg-opacity-10 text-omni-purple border border-purple border-opacity-20" style={{fontSize: '0.6rem', color: '#b300ff'}}>
                            {e.split('.')[0]}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>
                      <div className="d-flex align-items-center gap-2 font-mono" style={{fontSize: '0.7rem', color: 'rgba(255,255,255,0.4)'}}>
                        <Key size={12} className="opacity-50" />
                        <code>{wh.secret ? `omni_sec_${wh.secret.substring(0, 4)}***` : '---'}</code>
                      </div>
                    </td>
                    <td className="text-end">
                      <div className="d-flex gap-2 justify-content-end">
                        <button className="btn btn-sm btn-outline-light border-white-10 opacity-50 hover-opacity-100 p-1 px-2"><Activity size={14} /></button>
                        <button onClick={() => handleDelete(wh.id)} className="btn btn-sm btn-outline-danger border-white-10 opacity-50 hover-opacity-100 p-1 px-2"><Trash2 size={14} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
                {webhooks.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-5 text-center text-white-50 italic" style={{fontSize: '0.8rem'}}>Nenhuma rota de disparo conectada para este cliente.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* INFO PANEL */}
      <div className="glass-panel mt-4 py-3 px-4 d-flex align-items-start gap-3">
        <div className="p-2 rounded-circle bg-purple bg-opacity-10 text-omni-purple mt-1"><Info size={18} /></div>
        <div>
          <h6 className="text-white fw-bold mb-1" style={{fontSize: '0.85rem'}}>Segurança de Webhooks</h6>
          <p className="mb-0 text-white-50" style={{fontSize: '0.75rem', lineHeight: 1.5}}>
            Cada disparo inclui o header `X-Omni-Signature`. Recomendamos validar esta assinatura no seu sistema para garantir que a requisição partiu da malha OmniMemory.
          </p>
        </div>
      </div>
    </div>
  );
}
