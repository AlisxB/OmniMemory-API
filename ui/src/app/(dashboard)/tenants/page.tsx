'use client';
import { useState } from 'react';
import useSWR, { mutate } from 'swr';
import { fetchApi } from '@/lib/api';
import GlassCard from '@/components/GlassCard';
import { Plus, X, Shield, Activity, HardDrive } from 'lucide-react';

export default function TenantsPage() {
  const { data, error, isLoading } = useSWR('/admin/tenants', fetchApi, { refreshInterval: 5000 });
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  
  // Form State
  const [newTenant, setNewTenant] = useState({
    tenant_id: '',
    name: '',
    buffer_window: 60,
    rate_limit: 100
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (isLoading) return <div className="text-omni-neon animate-pulse text-lg p-5">Iniciando varredura na DB...</div>;
  if (error) return <div className="text-omni-accent font-mono p-5">Erro ao recuperar malha: {error.message}</div>;

  const tenants = data?.tenants || [];
  const filtered = tenants.filter((t: any) => 
    t.tenant_id.toLowerCase().includes(searchTerm.toLowerCase()) || 
    t.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await fetchApi('/admin/tenants', {
        method: 'POST',
        body: JSON.stringify({
          tenant_id: newTenant.tenant_id,
          name: newTenant.name,
          settings: {
            buffer_window_seconds: newTenant.buffer_window,
            rate_limit_rpm: newTenant.rate_limit
          }
        })
      });
      mutate('/admin/tenants');
      setIsModalOpen(false);
      setNewTenant({ tenant_id: '', name: '', buffer_window: 60, rate_limit: 100 });
    } catch (err: any) {
      alert('Erro ao criar tenant: ' + err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 relative">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Gerenciar Tenants</h1>
          <p className="text-white/60 mt-1">Malha central de clientes e limites de IA.</p>
        </div>
        <button 
          onClick={() => setIsModalOpen(true)}
          className="bg-omni-neon text-black font-semibold px-6 py-2 rounded-full hover:shadow-[0_0_20px_rgba(0,245,255,0.4)] transition-all flex items-center gap-2"
        >
          <Plus size={18} /> Criar Tenant
        </button>
      </header>

      <GlassCard>
        <div className="flex justify-between items-center mb-6">
          <div className="relative">
            <input 
              type="text" 
              placeholder="🔍 Buscar por ID ou nome..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-80 bg-white/5 border border-white/10 rounded-lg py-2 pl-4 pr-4 text-white placeholder-white/20 focus:outline-none focus:ring-2 focus:ring-omni-neon/50 focus:border-omni-neon transition-all"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="omni-table">
            <thead>
              <tr className="border-b border-white/10 text-white/50 text-sm uppercase tracking-wider">
                <th className="pb-4 pt-2 font-medium">Tenant ID / Nome</th>
                <th className="pb-4 pt-2 font-medium">Status</th>
                <th className="pb-4 pt-2 font-medium">Buffer</th>
                <th className="pb-4 pt-2 font-medium">RP Minuto</th>
                <th className="pb-4 pt-2 font-medium text-right">Ações</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((tenant: any) => (
                <tr key={tenant.tenant_id} className="border-b border-white/5 hover:bg-white/[0.02] transition-colors group">
                  <td className="py-4 px-3">
                    <div className="font-medium text-white group-hover:text-omni-neon transition-colors">{tenant.tenant_id}</div>
                    <div className="text-xs text-white/40">{tenant.name}</div>
                  </td>
                  <td className="py-4 px-3">
                    {tenant.is_active ? 
                      <span className="badge-status-green">Ativo</span> : 
                      <span className="text-omni-accent bg-omni-accent/10 px-2 py-1 rounded text-xs border border-omni-accent/20">Inativo</span>
                    }
                  </td>
                  <td className="py-4 px-3 text-white/70 font-mono">
                    <Activity size={14} className="inline mr-2 text-omni-neon/50" />
                    {tenant.settings?.buffer_window_seconds ?? 0}s
                  </td>
                  <td className="py-4 px-3 text-white/70 font-mono">
                    <HardDrive size={14} className="inline mr-2 text-omni-purple/50" />
                    {tenant.settings?.rate_limit_rpm ?? 'Inf.'}
                  </td>
                  <td className="py-4 px-3 text-right">
                    <button className="text-xs border border-white/20 rounded px-3 py-1 text-white hover:border-omni-neon hover:text-omni-neon transition-colors">
                      <Shield size={12} className="inline mr-1" /> Chaves
                    </button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-white/40 italic">Nenhum tenant mapeado nesta malha.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </GlassCard>

      {/* MODAL OVERLAY */}
      {isModalOpen && (
        <div className="fixed inset-0 z-[2000] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-300">
          <GlassCard className="w-full max-w-lg border-omni-neon/30 !bg-omni-bg shadow-[0_0_50px_rgba(0,245,255,0.1)] relative">
            <button 
              onClick={() => setIsModalOpen(false)}
              className="absolute top-4 right-4 text-white/40 hover:text-white transition-colors"
            >
              <X size={24} />
            </button>
            
            <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
              <Plus className="text-omni-neon" /> Novo Tenant
            </h2>

            <form onSubmit={handleCreate} className="space-y-5">
              <div className="space-y-1">
                <label className="text-xs font-bold text-white/50 uppercase tracking-widest">Identificador único (ID)</label>
                <input 
                  required
                  value={newTenant.tenant_id}
                  onChange={e => setNewTenant({...newTenant, tenant_id: e.target.value})}
                  className="w-full bg-white/5 border border-white/10 rounded-lg py-2.5 px-4 text-white focus:ring-2 focus:ring-omni-neon/40 focus:outline-none transition-all"
                  placeholder="ex: clinica_saude_01"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-bold text-white/50 uppercase tracking-widest">Nome de Exibição</label>
                <input 
                  required
                  value={newTenant.name}
                  onChange={e => setNewTenant({...newTenant, name: e.target.value})}
                  className="w-full bg-white/5 border border-white/10 rounded-lg py-2.5 px-4 text-white focus:ring-2 focus:ring-omni-neon/40 focus:outline-none transition-all"
                  placeholder="Ex: Clínica Saúde Matriz"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-bold text-white/50 uppercase tracking-widest">Buffer (Segundos)</label>
                  <input 
                    type="number"
                    value={newTenant.buffer_window}
                    onChange={e => setNewTenant({...newTenant, buffer_window: parseInt(e.target.value)})}
                    className="w-full bg-white/5 border border-white/10 rounded-lg py-2.5 px-4 text-white focus:ring-2 focus:ring-omni-neon/40 focus:outline-none transition-all"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-bold text-white/50 uppercase tracking-widest">Rate Limit (RPM)</label>
                  <input 
                    type="number"
                    value={newTenant.rate_limit}
                    onChange={e => setNewTenant({...newTenant, rate_limit: parseInt(e.target.value)})}
                    className="w-full bg-white/5 border border-white/10 rounded-lg py-2.5 px-4 text-white focus:ring-2 focus:ring-omni-neon/40 focus:outline-none transition-all"
                  />
                </div>
              </div>

              <div className="pt-4 flex gap-3">
                <button 
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="flex-1 py-3 border border-white/10 rounded-lg text-white/70 hover:bg-white/5 transition-all"
                >
                  Cancelar
                </button>
                <button 
                  type="submit"
                  disabled={isSubmitting}
                  className="flex-1 py-3 bg-omni-neon text-black font-bold rounded-lg hover:shadow-[0_0_20px_rgba(0,245,255,0.4)] transition-all disabled:opacity-50"
                >
                  {isSubmitting ? 'Provisionando...' : 'Confirmar Registro'}
                </button>
              </div>
            </form>
          </GlassCard>
        </div>
      )}
    </div>
  );
}
