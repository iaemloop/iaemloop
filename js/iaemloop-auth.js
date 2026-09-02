/* IA em Loop private-area auth.
 * Requires Supabase project config in js/iaemloop-auth-config.js.
 * Security model: public teaser pages never contain real custody data. Real private
 * pages must be served only after approved session, or from authenticated storage.
 */
(function () {
  const cfg = window.IAEMLOOP_AUTH_CONFIG || {};
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
      window.__iaemloopSupabase = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseAnonKey);
    }
    return window.__iaemloopSupabase;
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
    const redirectTo = new URL('area_privada.html', window.location.href).toString();
    const { data, error } = await sb.auth.signUp({
      email,
      password,
      options: { emailRedirectTo: redirectTo, data: { full_name: fullName } }
    });
    if (error) {
      setStatus('Erro no cadastro: ' + error.message, 'error');
      return false;
    }
    // O pedido em access_requests é criado por trigger seguro no Supabase
    // quando auth.users recebe o novo usuário. O front não tenta inserir aqui,
    // porque antes da confirmação de e-mail a sessão pode não existir e o RLS
    // bloqueia corretamente a escrita direta.
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
    setStatus('Acesso aprovado. Abrindo área privada...', 'ok');
    const target = form.dataset.redirect || new URLSearchParams(location.search).get('redirect') || cfg.defaultRedirect || 'area_privada.html';
    window.location.href = target;
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
    const redirectTo = new URL('area_privada.html', window.location.href).toString();
    const { error } = await sb.auth.resetPasswordForEmail(email, { redirectTo });
    if (error) {
      setStatus('Erro ao solicitar recuperação: ' + error.message, 'error');
      return false;
    }
    setStatus('Se o e-mail estiver cadastrado, a recuperação será enviada.', 'ok');
    return false;
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
    const { data } = await sb.auth.getUser();
    if (!data.user) {
      gate.hidden = false;
      setStatus('Faça login para desbloquear esta página.', 'warn');
      return;
    }
    try {
      const profile = await getApprovedProfile(sb, data.user.id);
      if (profile && profile.status === 'approved') {
        document.documentElement.dataset.auth = 'approved';
        gate.hidden = true;
        setStatus('Acesso aprovado.', 'ok');
      } else {
        gate.hidden = false;
        setStatus('Usuário autenticado, mas ainda pendente de aprovação.', 'warn');
      }
    } catch (err) {
      gate.hidden = false;
      setStatus('Não foi possível validar aprovação: ' + err.message, 'error');
    }
  }

  window.IAEMLOOPAuth = { signup, login, recover, protectPage, client };
  document.addEventListener('DOMContentLoaded', protectPage);
})();
