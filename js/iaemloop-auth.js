/* IA em Loop private-area auth.
 * Requires Supabase project config in js/iaemloop-auth-config.js.
 * Security model: public teaser pages never contain real custody data. Real private
 * pages must be served only after approved session, or from authenticated storage.
 */
(function () {
  const cfg = window.IAEMLOOP_AUTH_CONFIG || {};
  const ACTIVITY_KEY = 'iaemloop:last_activity_at';
  const DEFAULT_IDLE_MINUTES = 5; // Sliding session: 5 min of inactivity requires login again.
  let lastActivityWrite = 0;

  const statusEl = () => document.querySelector('[data-auth-status]') || document.getElementById('notice');
  const setStatus = (message, kind = 'info') => {
    const el = statusEl();
    if (!el) return;
    el.textContent = message;
    el.dataset.kind = kind;
  };

  function hasConfig() {
    return Boolean(cfg.supabaseUrl && cfg.supabaseAnonKey && window.supabase);
  }

  function client() {
    if (!hasConfig()) return null;
    if (!window.__iaemloopSupabase) {
      window.__iaemloopSupabase = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseAnonKey, {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
          detectSessionInUrl: true,
          storageKey: 'iaemloop-auth-token'
        }
      });
    }
    return window.__iaemloopSupabase;
  }

  function idleLimitMs() {
    const minutes = Number(cfg.sessionIdleMinutes || DEFAULT_IDLE_MINUTES);
    return Math.max(1, minutes) * 60 * 1000;
  }

  function markActivity(force = false) {
    const now = Date.now();
    if (!force) {
      try {
        const raw = localStorage.getItem(ACTIVITY_KEY);
        if (!raw) return;
        const last = Number(raw);
        if (Number.isFinite(last) && now - last > idleLimitMs()) return;
      } catch (_) {}
      if (now - lastActivityWrite < 60000) return;
    }
    lastActivityWrite = now;
    try { localStorage.setItem(ACTIVITY_KEY, String(now)); } catch (_) {}
  }

  function isIdleExpired() {
    try {
      const raw = localStorage.getItem(ACTIVITY_KEY);
      if (!raw) return false;
      const last = Number(raw);
      return Number.isFinite(last) && Date.now() - last > idleLimitMs();
    } catch (_) {
      return false;
    }
  }

  function installActivityTracking() {
    ['click', 'keydown', 'scroll', 'touchstart', 'mousemove'].forEach((eventName) => {
      window.addEventListener(eventName, () => markActivity(false), { passive: true });
    });
    // Do not mark activity on page load. Only real user movement keeps the
    // 5-minute sliding session alive; once expired, a new login is required.
  }

  function normalizeRedirect(target) {
    const fallback = cfg.defaultRedirect || '/privado/index.html';
    const requested = target || fallback;
    try {
      const url = new URL(requested, window.location.origin);
      if (url.origin !== window.location.origin) return fallback;
      return url.pathname + url.search + url.hash;
    } catch (_) {
      return fallback;
    }
  }

  async function getApprovedProfile(sb, userId) {
    const { data, error } = await sb
      .from('access_requests')
      .select('id,email,full_name,status,approved_at')
      .eq('user_id', userId)
      .maybeSingle();
    if (error) throw error;
    return data;
  }

  async function getApprovedSession(sb) {
    if (isIdleExpired()) {
      await sb.auth.signOut();
      try { localStorage.removeItem(ACTIVITY_KEY); } catch (_) {}
      return { user: null, profile: null, expired: true };
    }
    const { data } = await sb.auth.getUser();
    if (!data.user) return { user: null, profile: null, expired: false };
    const profile = await getApprovedProfile(sb, data.user.id);
    if (profile && profile.status === 'approved') {
      try {
        if (!localStorage.getItem(ACTIVITY_KEY)) markActivity(true);
        else markActivity(false);
      } catch (_) {
        markActivity(false);
      }
      return { user: data.user, profile, expired: false };
    }
    return { user: data.user, profile, expired: false };
  }

  function notifyApprovalEmail(payload) {
    // Free/static notification path. FormSubmit may request one-time activation
    // on equipeiaemloop@gmail.com the first time it receives a submission.
    const iframeName = 'iaemloop-formsubmit-silent';
    let iframe = document.querySelector(`iframe[name="${iframeName}"]`);
    if (!iframe) {
      iframe = document.createElement('iframe');
      iframe.name = iframeName;
      iframe.style.display = 'none';
      document.body.appendChild(iframe);
    }
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = `https://formsubmit.co/${encodeURIComponent(cfg.approvalEmail || 'equipeiaemloop@gmail.com')}`;
    form.target = iframeName;
    const fields = {
      _subject: 'Novo pedido de acesso — IA em Loop',
      _captcha: 'false',
      tipo: 'pedido_cadastro_area_privada',
      nome: payload.fullName || '',
      email: payload.email || '',
      status: 'pending',
      observacao: 'Aprovar manualmente no Supabase SQL Editor ou Dashboard.'
    };
    for (const [name, value] of Object.entries(fields)) {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = name;
      input.value = value;
      form.appendChild(input);
    }
    document.body.appendChild(form);
    form.submit();
    setTimeout(() => form.remove(), 5000);
  }

  async function autoOpenIfAlreadyApproved() {
    const form = document.querySelector('form[data-redirect], form#login');
    if (!form || document.querySelector('[data-requires-approved-user]')) return;
    const sb = client();
    if (!sb) return;
    try {
      const session = await getApprovedSession(sb);
      if (session.profile && session.profile.status === 'approved') {
        const paramsRedirect = new URLSearchParams(location.search).get('redirect');
        const target = normalizeRedirect(form.dataset.redirect || paramsRedirect || cfg.defaultRedirect || '/privado/index.html');
        setStatus('Sessão ativa. Abrindo área privada...', 'ok');
        window.location.assign(target);
      } else if (session.expired) {
        setStatus('Sessão expirada por inatividade. Faça login novamente.', 'warn');
      }
    } catch (_) {
      // Keep the login form usable if the silent check fails.
    }
  }

  async function signup(event) {
    event.preventDefault();
    const sb = client();
    if (!sb) {
      setStatus('Cadastro real ainda não configurado: falta preencher Supabase URL e anon key.', 'warn');
      return false;
    }
    const form = event.currentTarget;
    const email = form.email.value.trim();
    const password = form.password?.value || form.senha?.value || '';
    const fullName = form.nome?.value?.trim() || form.full_name?.value?.trim() || '';
    if (!email || !password) {
      setStatus('Informe e-mail e senha para solicitar acesso.', 'warn');
      return false;
    }
    setStatus('Criando pedido de acesso...', 'info');
    const redirectTo = new URL('area_privada.html', window.location.origin).toString();
    const { error } = await sb.auth.signUp({
      email,
      password,
      options: { emailRedirectTo: redirectTo, data: { full_name: fullName } }
    });
    if (error) {
      setStatus('Erro no cadastro: ' + error.message, 'error');
      return false;
    }
    notifyApprovalEmail({ email, fullName });
    setStatus(`Cadastro criado. Confirme o e-mail do Supabase. O pedido de aprovação será registrado no Supabase e enviado para ${cfg.approvalEmail || 'equipeiaemloop@gmail.com'}; o acesso só será liberado após aprovação manual.`, 'ok');
    return false;
  }

  async function login(event) {
    event.preventDefault();
    const sb = client();
    if (!sb) {
      setStatus('Login real ainda não configurado: falta preencher Supabase URL e anon key.', 'warn');
      return false;
    }
    const form = event.currentTarget;
    const email = form.email.value.trim();
    const password = form.password.value;
    setStatus('Verificando login...', 'info');
    const { data, error } = await sb.auth.signInWithPassword({ email, password });
    if (error) {
      setStatus('Login negado: ' + error.message, 'error');
      return false;
    }
    const profile = await getApprovedProfile(sb, data.user.id);
    if (!profile || profile.status !== 'approved') {
      await sb.auth.signOut();
      setStatus('Cadastro recebido, mas ainda não aprovado pelo IA em Loop.', 'warn');
      return false;
    }
    markActivity(true);
    setStatus('Acesso aprovado. Abrindo carteiras em custódia...', 'ok');
    const paramsRedirect = new URLSearchParams(location.search).get('redirect');
    const target = normalizeRedirect(form.dataset.redirect || paramsRedirect || cfg.defaultRedirect || '/privado/index.html');
    window.location.assign(target);
    return false;
  }

  async function recover(event) {
    event.preventDefault();
    const sb = client();
    if (!sb) {
      setStatus('Recuperação real ainda não configurada: falta preencher Supabase URL e anon key.', 'warn');
      return false;
    }
    const email = event.currentTarget.email.value.trim();
    const redirectTo = new URL('area_privada.html', window.location.origin).toString();
    const { error } = await sb.auth.resetPasswordForEmail(email, { redirectTo });
    if (error) {
      setStatus('Erro ao solicitar recuperação: ' + error.message, 'error');
      return false;
    }
    setStatus('Se o e-mail estiver cadastrado, a recuperação será enviada.', 'ok');
    return false;
  }

  async function logout() {
    const sb = client();
    try { localStorage.removeItem(ACTIVITY_KEY); } catch (_) {}
    if (sb) await sb.auth.signOut();
    window.location.assign('/area_privada.html');
  }

  async function loadPrivatePage(sb) {
    const container = document.querySelector('[data-private-page]');
    if (!container) return;
    const slug = container.dataset.privatePage;
    const frame = document.querySelector('[data-private-frame]');
    if (!slug || !frame) return;
    setStatus('Carregando custódia privada...', 'info');
    const { data, error } = await sb
      .from('private_pages')
      .select('html,updated_at')
      .eq('slug', slug)
      .maybeSingle();
    if (error) throw error;
    if (!data || !data.html) {
      setStatus('Custódia privada ainda não foi publicada no Supabase para esta carteira.', 'warn');
      return;
    }
    const html = data.html.replace(/<head(.*?)>/i, '<head$1><base href="/">');
    frame.srcdoc = html;
    frame.addEventListener('load', () => {
      try {
        const doc = frame.contentWindow?.document;
        ['click', 'keydown', 'scroll', 'touchstart', 'mousemove'].forEach((eventName) => {
          doc?.addEventListener(eventName, () => markActivity(false), { passive: true });
        });
      } catch (_) {}
    }, { once: true });
    setStatus('Custódia privada carregada.', 'ok');
  }

  async function protectPage() {
    const gate = document.querySelector('[data-requires-approved-user]');
    if (!gate) return;
    const sb = client();
    if (!sb) {
      gate.hidden = false;
      setStatus('Área privada ainda não configurada. Nenhum dado real foi carregado.', 'warn');
      return;
    }
    try {
      const session = await getApprovedSession(sb);
      if (!session.user) {
        gate.hidden = false;
        setStatus(session.expired ? 'Sessão expirada por inatividade. Faça login novamente.' : 'Faça login para desbloquear esta página.', 'warn');
        return;
      }
      if (session.profile && session.profile.status === 'approved') {
        document.documentElement.dataset.auth = 'approved';
        gate.hidden = true;
        setStatus('Acesso aprovado.', 'ok');
        await loadPrivatePage(sb);
      } else {
        gate.hidden = false;
        setStatus('Usuário autenticado, mas ainda pendente de aprovação.', 'warn');
      }
    } catch (err) {
      gate.hidden = false;
      setStatus('Não foi possível validar aprovação: ' + err.message, 'error');
    }
  }

  installActivityTracking();
  window.IAEMLOOPAuth = { signup, login, recover, logout, protectPage, client };
  document.addEventListener('DOMContentLoaded', () => {
    protectPage();
    autoOpenIfAlreadyApproved();
  });
})();
