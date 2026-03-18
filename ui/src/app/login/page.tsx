'use client';
import { useState } from 'react';
import { useAuth } from '@/components/AuthProvider';
import GlassCard from '@/components/GlassCard';
import { Lock, User } from 'lucide-react';
import { API_BASE } from '@/lib/api';

export default function LoginPage() {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { login } = useAuth();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const form = new URLSearchParams();
      form.append('username', username);
      form.append('password', password);

      const res = await fetch(`${API_BASE}/admin/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: form,
      });

      if (!res.ok) throw new Error('Credenciais inválidas');
      
      const data = await res.json();
      login(data.access_token);
    } catch (err: any) {
      setError(err.message || 'Erro de conexão');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-black overflow-hidden relative">
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-omni-neon/20 rounded-full blur-[100px] -z-10" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/4 -translate-y-3/4 w-[400px] h-[400px] bg-omni-purple/30 rounded-full blur-[100px] -z-10" />

      <GlassCard className="w-full max-w-md mx-4 animate-in fade-in slide-in-from-bottom-8 duration-700">
        <div className="text-center mb-8">
          <div className="text-4xl mb-4 text-omni-neon">🧠</div>
          <h1 className="text-2xl font-bold tracking-tight text-white">OmniMemory</h1>
          <p className="text-white/50 text-sm mt-1">Sistemas Cognitivos API</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-4">
          <div className="space-y-1">
            <label className="text-xs font-medium text-white/70 uppercase tracking-wider">Usuário Administrador</label>
            <div className="relative">
              <User className="absolute left-3 top-3 h-4 w-4 text-white/40" />
              <input 
                type="text" 
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-lg py-2.5 pl-10 pr-4 text-white placeholder-white/20 focus:outline-none focus:ring-2 focus:ring-omni-neon/50 focus:border-omni-neon transition-all"
                placeholder="admin"
              />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-white/70 uppercase tracking-wider">Palavra-passe</label>
            <div className="relative">
              <Lock className="absolute left-3 top-3 h-4 w-4 text-white/40" />
              <input 
                type="password" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-lg py-2.5 pl-10 pr-4 text-white placeholder-white/20 focus:outline-none focus:ring-2 focus:ring-omni-neon/50 focus:border-omni-neon transition-all"
                placeholder="••••••••"
              />
            </div>
          </div>

          {error && (
            <div className="bg-omni-accent/10 border border-omni-accent/30 text-omni-accent text-sm p-3 rounded-lg text-center animate-in shake">
              {error}
            </div>
          )}

          <button 
            type="submit" 
            disabled={loading}
            className="w-full bg-white text-black font-semibold py-2.5 rounded-lg hover:bg-omni-neon transition-colors duration-300 disabled:opacity-50 mt-4 shadow-[0_0_15px_rgba(255,255,255,0.3)] hover:shadow-[0_0_20px_rgba(0,245,255,0.5)]"
          >
            {loading ? 'Validando...' : 'Acessar Core'}
          </button>
        </form>
      </GlassCard>
    </div>
  );
}
