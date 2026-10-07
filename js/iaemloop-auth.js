/* IA em Loop private-area auth.
 * Requires Supabase project config in js/iaemloop-auth-config.js.
 * Security model: public teaser pages never contain real custody data. Real private
 * pages must be served only after an approved session and fetched under RLS.
 */
(function () {
  'use strict';

  const cfg = window.IAEMLOOP_AUTH_CONFIG || {};
  const ACTIVITY_KEY = 'iaemloop:last_activity_at';
  const DEFAULT_IDLE_MINUTES = 5;
  const ACTIVITY_WRITE_INTERVAL_MS = 5000;
  let lastActivityWrite = 0;
  let lastActivityMemory = null;
  let idleTimer = null;
  let invalidatingSession = false;
  let recoveryMode = false;
  let authSubscription = null;
  let approvedSessionPromise = null;
  let signupPending = false;
  let signupCooldownTimer = null;

  const statusEl = () => document.querySelector('[data-auth-status]') || document.getElementById('notice');
  const setStatus = (message, kind = 'info') => {
    const el = statusEl();
    if (!el) return;
    el.textContent = message;
    el.dataset.kind = kind;
  };

  function decodeJwtPayload(token) {
    try {
      const encoded = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      return JSON.parse(window.atob(encoded.padEnd(Math.ceil(encoded.length / 4) * 4, '=')));
    } catch (_) {
      return null;
    }
  }

  function configIssue() {
    const url = String(cfg.supabaseUrl || '').trim();
    const key = String(cfg.supabaseAnonKey || '').trim();
    if (!window.supabase) return 'biblioteca Supabase indisponível';
    if (!/^https:\/\/[a-z0-9]{20}\.supabase\.co\/?$/i.test(url)) return 'URL pública do projeto ausente ou inválida';
    if (!key) return 'chave pública do navegador ausente';
    if (/\.\.\.|placeholder|sua[_ -]?(anon|publishable)|seu[_ -]?projeto|example/i.test(key)) {
      return 'chave pública do navegador incompleta ou de exemplo';
    }
    if (key.startsWith('sb_secret_') || /service[_-]?role/i.test(key)) {
      return 'chave privilegiada não pode ser usada no navegador';
    }
    if (key.startsWith('eyJ')) {
      if (key.length < 80 || key.split('.').length !== 3) return 'chave pública do navegador incompleta ou de exemplo';
      const payload = decodeJwtPayload(key);
      if (!payload || !['anon', 'publishable'].includes(payload.role)) return 'a chave configurada não é pública';
      const projectRef = new URL(url).hostname.split('.')[0];
      if (payload.ref && payload.ref !== projectRef) return 'a chave pública pertence a outro projeto';
    } else if (key.startsWith('sb_publishable_')) {
      if (key.length < 30) return 'chave pública do navegador incompleta ou de exemplo';
    } else {
      return 'formato de chave pública não reconhecido';
    }
    return '';
  }

  function hasConfig() {
    return !configIssue();
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

  function clearActivity() {
    try { localStorage.removeItem(ACTIVITY_KEY); } catch (_) {}
    lastActivityMemory = null;
    lastActivityWrite = 0;
    if (idleTimer) window.clearTimeout(idleTimer);
    idleTimer = null;
  }

  function lastActivityAt() {
    let stored = null;
    try {
      const last = Number(localStorage.getItem(ACTIVITY_KEY));
      stored = Number.isFinite(last) && last > 0 ? last : null;
    } catch (_) {}
    return Math.max(stored || 0, lastActivityMemory || 0) || null;
  }

  function clearApprovedUi() {
    delete document.documentElement.dataset.auth;
    const gate = document.querySelector('[data-requires-approved-user]');
    if (gate) gate.hidden = false;
    document.dispatchEvent(new CustomEvent('iaemloop:session-invalidated'));
  }


  async function invalidateSession(message, options = {}) {
    if (invalidatingSession) return;
    invalidatingSession = true;
    clearActivity();
    clearApprovedUi();
    setStatus(message, options.kind || 'warn');
    const sb = window.__iaemloopSupabase;
    try { if (sb) await sb.auth.signOut(); } catch (_) {}
    if (options.redirect && document.querySelector('[data-requires-approved-user]')) {
      const loginUrl = new URL('/area_privada.html', window.location.origin);
      loginUrl.searchParams.set('redirect', window.location.pathname);
      loginUrl.searchParams.set('reason', options.reason || 'expired');
      window.location.replace(loginUrl.pathname + loginUrl.search);
    }
  }

  function scheduleIdleExpiry() {
    if (idleTimer) window.clearTimeout(idleTimer);
    idleTimer = null;
    const last = lastActivityAt();
    if (!last) return;
    const remaining = idleLimitMs() - (Date.now() - last);
    if (remaining <= 0) {
      void invalidateSession('Sessão expirada por inatividade. Faça login novamente.', {
        redirect: true, reason: 'idle'
      });
      return;
    }
    idleTimer = window.setTimeout(() => {
      void invalidateSession('Sessão expirada por inatividade. Faça login novamente.', {
        redirect: true, reason: 'idle'
      });
    }, remaining + 50);
  }

  function markActivity(force = false) {
    const now = Date.now();
    if (!force) {
      const last = lastActivityAt();
      if (last === null || now - last >= idleLimitMs()) return;
    }
    lastActivityMemory = now;
    if (force || now - lastActivityWrite >= ACTIVITY_WRITE_INTERVAL_MS) {
      lastActivityWrite = now;
      try { localStorage.setItem(ACTIVITY_KEY, String(now)); } catch (_) {}
    }
    scheduleIdleExpiry();
  }

  function isIdleExpired() {
    const last = lastActivityAt();
    return last !== null && Date.now() - last >= idleLimitMs();
  }

  function installActivityTracking() {
    ['click', 'keydown', 'scroll', 'touchstart', 'mousemove'].forEach((eventName) => {
      window.addEventListener(eventName, () => markActivity(false), { passive: true });
    });
    window.addEventListener('storage', (event) => {
      if (event.key !== ACTIVITY_KEY) return;
      if (event.newValue === null) {
        void invalidateSession('Sua sessão foi encerrada em outra aba. Faça login novamente.', {
          redirect: true, reason: 'signed-out'
        });
        return;
      }
      const observed = Number(event.newValue);
      if (Number.isFinite(observed) && observed > 0) lastActivityMemory = observed;
      scheduleIdleExpiry();
    });
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) scheduleIdleExpiry();
    });
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

  function callbackParams() {
    const query = new URLSearchParams(window.location.search);
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    return { query, hash };
  }

  function hasAuthCallbackHint() {
    const { query, hash } = callbackParams();
    return query.has('code') || query.has('token_hash') || query.has('error')
      || hash.has('access_token') || hash.has('error') || hash.get('type') === 'recovery';
  }

  function clearAuthCallbackUrl() {
    if (!window.history?.replaceState) return;
    window.history.replaceState({}, document.title, window.location.pathname);
  }

  function showAuthForm(formId) {
    document.querySelectorAll('.form').forEach((form) => {
      const active = form.id === formId;
      form.classList.toggle('active', active);
      form.hidden = !active;
    });
    document.querySelectorAll('.tab').forEach((tab) => {
      const active = tab.dataset.tab === formId;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', String(active));
    });
  }

  function setRecoveryUi(active) {
    recoveryMode = active;
    const tabs = document.querySelector('[data-auth-tabs]');
    if (tabs) tabs.hidden = active;
    if (active) {
      clearActivity();
      clearApprovedUi();
      showAuthForm('nova-senha');
      window.setTimeout(() => document.getElementById('new-password')?.focus(), 0);
      return;
    }
    showAuthForm('login');
  }

  function recoveryCallbackError() {
    const { query, hash } = callbackParams();
    const error = query.get('error') || hash.get('error');
    if (!error) return '';
    return query.get('error_description') || hash.get('error_description') || error;
  }

  function handleRecoveryCallbackError() {
    if (!recoveryCallbackError()) return false;
    recoveryMode = true;
    clearActivity();
    clearApprovedUi();
    clearAuthCallbackUrl();
    setRecoveryUi(false);
    showAuthForm('senha');
    setStatus('O link de recuperação é inválido ou expirou. Solicite um novo na aba Senha.', 'error');
    return true;
  }

  function enterRecoveryMode() {
    setRecoveryUi(true);
    setStatus('Link confirmado. Digite e confirme sua nova senha.', 'info');
  }

  function installAuthStateListener(sb) {
    if (!sb || authSubscription) return;
    const { data } = sb.auth.onAuthStateChange((event) => {
      if (event === 'PASSWORD_RECOVERY') {
        recoveryMode = true;
        window.setTimeout(enterRecoveryMode, 0);
      }
    });
    authSubscription = data?.subscription || true;
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
      await invalidateSession('Sessão expirada por inatividade. Faça login novamente.', {
        redirect: true, reason: 'idle'
      });
      return { user: null, profile: null, expired: true };
    }
    const { data, error } = await sb.auth.getUser();
    if (error) throw error;
    if (!data.user) return { user: null, profile: null, expired: false };
    const profile = await getApprovedProfile(sb, data.user.id);
    if (profile && profile.status === 'approved') {
      if (lastActivityAt() === null) markActivity(true);
      scheduleIdleExpiry();
    }
    return { user: data.user, profile, expired: false };
  }

  function getApprovedSessionShared(sb) {
    if (!approvedSessionPromise) {
      approvedSessionPromise = getApprovedSession(sb).finally(() => {
        approvedSessionPromise = null;
      });
    }
    return approvedSessionPromise;
  }

  async function requireApprovedSession() {
    const sb = client();
    if (!sb) throw new Error(`Configuração incompleta: ${configIssue()}.`);
    try {
      const session = await getApprovedSessionShared(sb);
      if (!session.user || !session.profile || session.profile.status !== 'approved') {
        await invalidateSession(
          session.expired ? 'Sessão expirada por inatividade. Faça login novamente.' : 'Sua sessão não está aprovada. Faça login novamente.',
          { redirect: true, reason: session.expired ? 'idle' : 'approval' }
        );
        throw new Error(session.expired ? 'Sessão expirada por inatividade.' : 'Sessão aprovada necessária.');
      }
      return { client: sb, ...session };
    } catch (error) {
      if (!invalidatingSession) {
        await invalidateSession('Não foi possível confirmar sua sessão e aprovação. Faça login novamente.', {
          kind: 'error', redirect: true, reason: 'validation'
        });
      }
      throw error;
    }
  }

  function notifyApprovalEmail(payload) {
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
      observacao: 'Revisar e decidir no painel administrativo de acessos.'
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
    window.setTimeout(() => form.remove(), 5000);
  }

  async function autoOpenIfAlreadyApproved() {
    if (recoveryMode) return;
    const form = document.querySelector('form[data-redirect], form#login');
    if (!form || document.querySelector('[data-requires-approved-user]')) return;
    const sb = client();
    if (!sb) {
      setStatus(`Acesso privado indisponível: ${configIssue()}.`, 'warn');
      return;
    }
    try {
      const session = await getApprovedSessionShared(sb);
      if (session.profile && session.profile.status === 'approved') {
        const paramsRedirect = new URLSearchParams(location.search).get('redirect');
        const target = normalizeRedirect(form.dataset.redirect || paramsRedirect || cfg.defaultRedirect);
        setStatus('Sessão ativa. Abrindo área privada...', 'ok');
        window.location.assign(target);
      } else if (session.expired) {
        setStatus('Sessão expirada por inatividade. Faça login novamente.', 'warn');
      }
    } catch (_) {
      await invalidateSession('Não foi possível confirmar uma sessão existente. Entre novamente.', { kind: 'error' });
    }
  }

  function signupRetrySeconds(error) {
    const message = String(error?.message || '');
    const match = message.match(/after\s+(\d+)\s+seconds?/i)
      || message.match(/(\d+)\s+seconds?/i);
    if (match) return Math.max(1, Number(match[1]));
    if (error?.status === 429 || /rate.?limit|security purposes/i.test(message)) return 60;
    return 0;
  }

  function startSignupCooldown(form, seconds) {
    const button = form.querySelector('button[type="submit"]');
    if (!button) return;
    if (signupCooldownTimer) window.clearInterval(signupCooldownTimer);
    const readyAt = Date.now() + Math.max(1, seconds) * 1000;
    const update = () => {
      const remaining = Math.max(0, Math.ceil((readyAt - Date.now()) / 1000));
      if (remaining > 0) {
        button.disabled = true;
        button.textContent = `Aguarde ${remaining}s`;
        return;
      }
      window.clearInterval(signupCooldownTimer);
      signupCooldownTimer = null;
      button.disabled = false;
      button.textContent = 'Solicitar cadastro';
      setStatus('Você já pode tentar o cadastro novamente.', 'info');
    };
    update();
    signupCooldownTimer = window.setInterval(update, 1000);
  }

  async function signup(event) {
    event.preventDefault();
    const sb = client();
    if (!sb) {
      setStatus(`Cadastro indisponível: ${configIssue()}.`, 'warn');
      return false;
    }
    const form = event.currentTarget;
    const submitButton = form.querySelector('button[type="submit"]');
    if (signupPending || submitButton?.disabled) return false;
    const email = form.email.value.trim();
    const password = form.password?.value || form.senha?.value || '';
    const fullName = form.nome?.value?.trim() || form.full_name?.value?.trim() || '';
    if (!email || !password) {
      setStatus('Informe e-mail e senha para solicitar acesso.', 'warn');
      return false;
    }
    signupPending = true;
    if (submitButton) submitButton.disabled = true;
    setStatus('Criando pedido de acesso...', 'info');
    try {
      const redirectTo = new URL('area_privada.html', window.location.origin).toString();
      const { error } = await sb.auth.signUp({
        email,
        password,
        options: { emailRedirectTo: redirectTo, data: { full_name: fullName } }
      });
      if (error) {
        const retrySeconds = signupRetrySeconds(error);
        if (retrySeconds) {
          setStatus(`O Supabase limitou novas tentativas por segurança. Aguarde ${retrySeconds} segundos e tente novamente. Se você já enviou o cadastro, confira também a caixa de entrada e o spam.`, 'warn');
          startSignupCooldown(form, retrySeconds);
        } else {
          setStatus('Não foi possível concluir o cadastro agora. Confira os dados e tente novamente.', 'error');
        }
        return false;
      }
      notifyApprovalEmail({ email, fullName });
      setStatus(`Cadastro criado. Confirme o e-mail do Supabase. O pedido será enviado para ${cfg.approvalEmail || 'equipeiaemloop@gmail.com'} e só será liberado após aprovação manual.`, 'ok');
    } catch (_) {
      setStatus('Não foi possível conectar ao serviço de cadastro. Tente novamente em instantes.', 'error');
    } finally {
      signupPending = false;
      if (submitButton && !signupCooldownTimer) submitButton.disabled = false;
    }
    return false;
  }

  async function login(event) {
    event.preventDefault();
    invalidatingSession = false;
    const sb = client();
    if (!sb) {
      setStatus(`Login indisponível: ${configIssue()}.`, 'warn');
      return false;
    }
    const form = event.currentTarget;
    const email = form.email.value.trim();
    const password = form.password.value;
    setStatus('Verificando login...', 'info');
    const { data, error } = await sb.auth.signInWithPassword({ email, password });
    if (error) {
      const invalidCredentials = error.code === 'invalid_credentials'
        || /invalid login credentials/i.test(error.message || '');
      setStatus(
        invalidCredentials
          ? 'Não foi possível entrar com esses dados. Confira e-mail e senha ou use a aba Senha para redefinir o acesso.'
          : 'Não foi possível entrar agora. Tente novamente em instantes.',
        'error'
      );
      return false;
    }
    let profile;
    try {
      profile = await getApprovedProfile(sb, data.user.id);
    } catch (_) {
      await sb.auth.signOut();
      clearActivity();
      clearApprovedUi();
      setStatus('Login confirmado, mas não foi possível validar a aprovação. Entre novamente quando a conexão estiver disponível.', 'error');
      return false;
    }
    if (!profile || profile.status !== 'approved') {
      await sb.auth.signOut();
      clearActivity();
      clearApprovedUi();
      setStatus('Cadastro recebido, mas ainda não aprovado pelo IA em Loop.', 'warn');
      return false;
    }
    markActivity(true);
    setStatus('Acesso aprovado. Abrindo Minha Carteira...', 'ok');
    const paramsRedirect = new URLSearchParams(location.search).get('redirect');
    const target = normalizeRedirect(form.dataset.redirect || paramsRedirect || cfg.defaultRedirect);
    window.location.assign(target);
    return false;
  }

  async function recover(event) {
    event.preventDefault();
    const sb = client();
    if (!sb) {
      setStatus(`Recuperação indisponível: ${configIssue()}.`, 'warn');
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

  async function updateRecoveredPassword(event) {
    event.preventDefault();
    if (!recoveryMode) {
      setStatus('Abra novamente o link enviado por e-mail para redefinir a senha.', 'warn');
      return false;
    }
    const sb = client();
    if (!sb) {
      setStatus(`Não foi possível redefinir a senha: ${configIssue()}.`, 'error');
      return false;
    }
    const form = event.currentTarget;
    const password = form.password.value;
    const confirmation = form.password_confirmation.value;
    if (password.length < 8) {
      setStatus('A nova senha deve ter pelo menos 8 caracteres.', 'warn');
      form.password.focus();
      return false;
    }
    if (password !== confirmation) {
      setStatus('As senhas não coincidem. Digite novamente.', 'warn');
      form.password_confirmation.focus();
      return false;
    }
    const submit = form.querySelector('[type="submit"]');
    if (submit) submit.disabled = true;
    setStatus('Salvando a nova senha...', 'info');
    const { error } = await sb.auth.updateUser({ password });
    if (error) {
      if (submit) submit.disabled = false;
      const expired = /expired|invalid|session|token/i.test(`${error.code || ''} ${error.message || ''}`);
      setStatus(
        expired
          ? 'O link de recuperação expirou ou já foi usado. Solicite um novo na aba Senha.'
          : 'Não foi possível salvar a nova senha. Tente novamente.',
        'error'
      );
      if (expired) {
        clearActivity();
        try { await sb.auth.signOut({ scope: 'local' }); } catch (_) {}
        clearAuthCallbackUrl();
        setRecoveryUi(false);
        showAuthForm('senha');
      }
      return false;
    }
    clearActivity();
    clearApprovedUi();
    try { await sb.auth.signOut({ scope: 'local' }); } catch (_) {}
    clearAuthCallbackUrl();
    form.reset();
    if (submit) submit.disabled = false;
    setRecoveryUi(false);
    setStatus('Senha atualizada. Entre com a nova senha para testar o acesso.', 'ok');
    window.setTimeout(() => document.getElementById('login-email')?.focus(), 0);
    return false;
  }

  async function logout() {
    const sb = client();
    clearActivity();
    clearApprovedUi();
    if (sb) await sb.auth.signOut();
    window.location.assign('/area_privada.html');
  }


  async function protectPage() {
    const gate = document.querySelector('[data-requires-approved-user]');
    if (!gate) return;
    invalidatingSession = false;
    const sb = client();
    if (!sb) {
      gate.hidden = false;
      clearApprovedUi();
      setStatus(`Área privada indisponível: ${configIssue()}. Nenhum dado real foi carregado.`, 'warn');
      return;
    }
    try {
      const session = await getApprovedSessionShared(sb);
      if (!session.user) {
        gate.hidden = false;
        setStatus(session.expired ? 'Sessão expirada por inatividade. Faça login novamente.' : 'Faça login para desbloquear esta página.', 'warn');
        return;
      }
      if (session.profile && session.profile.status === 'approved') {
        document.documentElement.dataset.auth = 'approved';
        gate.hidden = true;
        setStatus('Acesso aprovado.', 'ok');
        scheduleIdleExpiry();
      } else {
        await invalidateSession('Usuário autenticado, mas sem aprovação ativa.', { redirect: true, reason: 'approval' });
      }
    } catch (error) {
      await invalidateSession('Não foi possível validar sua aprovação. Faça login novamente.', {
        kind: 'error', redirect: true, reason: 'validation'
      });
      setStatus('Não foi possível validar aprovação: ' + error.message, 'error');
    }
  }

  async function approvedSession() {
    const sb = client();
    if (!sb) return { client: null, user: null, profile: null, expired: false };
    const session = await getApprovedSessionShared(sb);
    return { client: sb, ...session };
  }

  installActivityTracking();
  window.IAEMLOOPAuth = {
    signup, login, recover, updateRecoveredPassword, logout, protectPage, client, approvedSession,
    requireApprovedSession, hasConfig, configIssue, idleLimitMs
  };
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.tab').forEach((tab) => {
      tab.addEventListener('click', () => {
        if (!recoveryMode) showAuthForm(tab.dataset.tab);
      });
    });
    if (handleRecoveryCallbackError()) return;
    const sb = client();
    installAuthStateListener(sb);
    protectPage();
    if (!hasAuthCallbackHint()) autoOpenIfAlreadyApproved();
  });
})();
