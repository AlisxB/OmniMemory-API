'use client';
import { useState } from 'react';
import useSWR from 'swr';
import { fetchApi } from '@/lib/api';
import GlassCard from '@/components/GlassCard';

export default function MemoryExplorerPage() {
  const [tenantId, setTenantId] = useState('');
  const [userId, setUserId] = useState('');
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  // Busca lista de tenants para o select
  const { data: tenantsData } = useSWR('/admin/tenants', fetchApi);
  const tenants = tenantsData?.tenants || [];

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tenantId || !userId || !query) return;
    
    setIsSearching(true);
    try {
      const qs = new URLSearchParams({
        tenant_id: tenantId,
        external_user_id: userId,
        query: query,
        limit: '5'
      });
      const res = await fetchApi(`/v1/context/search?${qs.toString()}`);
      setSearchResults(res.data || []);
    } catch (err) {
      console.error(err);
      alert('Erro na busca semântica');
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Explorador de Memória</h1>
          <p className="text-white/60 mt-1">Busca Semântica & Análise de Vetores (RAG). Procure pelos fatos persistidos do usuário.</p>
        </div>
        <div className="text-omni-purple font-mono border border-omni-purple/30 bg-omni-purple/10 px-4 py-2 rounded-full flex gap-2 items-center">
          <div className="w-2 h-2 bg-omni-purple rounded-full animate-pulse flex-shrink-0" />
          <span className="text-xs">Database Conectada</span>
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <GlassCard className="md:col-span-1 space-y-6">
          <h2 className="text-lg font-bold border-b border-white/10 pb-2">Parâmetros de Busca</h2>
          <form onSubmit={handleSearch} className="space-y-4">
            
            <div className="space-y-1">
              <label className="text-xs font-medium text-white/50 uppercase tracking-wider">Tenant (Base)</label>
              <select 
                value={tenantId}
                onChange={(e) => setTenantId(e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-lg py-2.5 px-3 text-white appearance-none focus:outline-none focus:ring-2 focus:ring-omni-neon/50 focus:border-omni-neon transition-all"
              >
                <option value="" className="bg-black">Selecione o Tenant</option>
                {tenants.map((t: any) => (
                  <option key={t.tenant_id} value={t.tenant_id} className="bg-black">{t.name} ({t.tenant_id})</option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-white/50 uppercase tracking-wider">User ID (WhatsApp / Doc)</label>
              <input 
                type="text" 
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                placeholder="Ex: 558599..."
                className="w-full bg-white/5 border border-white/10 rounded-lg py-2.5 px-4 text-white placeholder-white/20 focus:outline-none focus:ring-2 focus:ring-omni-neon/50 focus:border-omni-neon transition-all"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-white/50 uppercase tracking-wider">Busca Neural (Pergunta)</label>
              <textarea 
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                rows={3}
                placeholder="Qual o nome do cachorro deste usuário?"
                className="w-full bg-white/5 border border-white/10 rounded-lg py-2.5 px-4 text-white placeholder-white/20 focus:outline-none focus:ring-2 focus:ring-omni-neon/50 focus:border-omni-neon transition-all resize-none"
              />
            </div>

            <button 
              type="submit" 
              disabled={isSearching || !tenantId || !userId || !query}
              className="w-full bg-omni-neon text-black font-semibold py-3 rounded-lg hover:shadow-[0_0_20px_rgba(0,245,255,0.4)] transition-all duration-300 disabled:opacity-50 mt-4 flex items-center justify-center gap-2"
            >
              {isSearching ? 'Calculando Embeddings...' : '🔎 Sondar Rede Neural'}
            </button>
          </form>
        </GlassCard>

        <GlassCard className="md:col-span-2 min-h-[500px]">
          <h2 className="text-lg font-bold border-b border-white/10 pb-2 mb-6">Mapeamento Retornado</h2>
          
          {searchResults.length === 0 && !isSearching && (
            <div className="flex w-full h-full items-center justify-center -mt-10 opacity-30">
              <div className="text-center">
                <div className="text-4xl mb-4 text-omni-purple">🌌</div>
                <p>Nenhuma memória em contexto.</p>
                <p className="text-sm">Selecione os parâmetros e pesquise.</p>
              </div>
            </div>
          )}

          {searchResults.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {searchResults.map((mem: any, i: number) => (
                <div key={i} className="bg-white/5 border border-white/10 rounded-xl p-4 hover:border-omni-neon/50 transition-colors relative group">
                  <div className="absolute -top-2 -right-2 bg-omni-bg text-omni-neon text-xs border border-omni-neon px-2 py-0.5 rounded-full z-10 font-mono">
                    {(mem.score * 100).toFixed(1)}% Similaridade
                  </div>
                  <div className="text-xs text-omni-purple uppercase tracking-widest font-bold mb-1">
                    [Fact ID: {mem.key.slice(0, 8)}]
                  </div>
                  <p className="text-white/90 text-sm leading-relaxed mt-2">{mem.value}</p>
                </div>
              ))}
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  );
}
