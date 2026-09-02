window.IAEMLOOP_AUTH_CONFIG = {
  // Supabase project URL and anon public key.
  // A anon key is public by design. Never put the service_role key in GitHub Pages.
  supabaseUrl: "https://nfhhjqgyuvwhaorkyfhq.supabase.co",
  supabaseAnonKey: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5maGhqcWd5dXZ3aGFvcmt5ZmhxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODgzNjE1NTgsImV4cCI6MjEwMzkzNzU1OH0.zmFI38b80ZNztZdbU978K3WQgLuLFcw4tYuCqLCBndc",
  approvalEmail: "equipeiaemloop@gmail.com",
  // Sessão deslizante: mantém o login enquanto houver atividade na página.
  // Após 5 minutos sem cliques/toques/teclas/rolagem, força novo login.
  sessionIdleMinutes: 5,
  defaultRedirect: "/privado/index.html",
  pages: {
    hub: "/privado/index.html",
    besstB3: "/privado/carteira_besst.html",
    magicB3: "/privado/carteira_magic_formula.html",
    besstUsd: "/privado/carteira_besst_dolarizada.html",
    magicUsd: "/privado/carteira_magic_formula_dolarizada.html"
  }
};
